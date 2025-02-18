#!/usr/bin/env python3
#
# MIT License
# Copyright (c) 2025 Nick Brook
# See LICENSE file for details.
#
import sys
import re
import argparse
from collections import defaultdict
import os

# ANSI escape codes for colors
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

# Section classifications
ROM_SECTIONS = {'text', 'rodata'}
RAM_SECTIONS = {'data', 'bss', 'noinit'}

def parse_map_file(filename):
    """
    Parse a map file and extract symbol sizes grouped by object file and section type.
    Returns a hierarchical dictionary:
    {
        'object_path': {
            'section_type': {
                'symbol_name': size,
                ...
            },
            ...
        },
        ...
    }
    """
    objects = defaultdict(lambda: defaultdict(dict))
    
    # Regular expressions for parsing
    # For lines that have section and symbol split across lines
    section_symbol_regex = re.compile(r'^\s*\.(\w+)\.(\S+)\s*$')
    # For continuation lines with address, size, and object
    continuation_regex = re.compile(r'^\s*0x[0-9a-f]+\s+0x([0-9a-f]+)\s+(.+)$')
    # For single-line entries
    single_line_regex = re.compile(r'^\s*\.(\w+)(?:\.(\S+))?\s+0x[0-9a-f]+\s+0x([0-9a-f]+)\s+(.+)$')
    
    with open(filename, 'r') as f:
        in_linker_section = False
        current_section = None
        current_symbol = None
        
        for line in f:
            line = line.rstrip()
            
            # Look for the start of the linker script section
            if "Linker script and memory map" in line:
                in_linker_section = True
                continue
            
            if not in_linker_section:
                continue
            
            # Skip empty lines and memory configuration lines
            if not line:
                continue
                
            # Try to match a single-line entry first
            single_match = single_line_regex.match(line)
            if single_match:
                section_type = single_match.group(1)
                symbol_name = single_match.group(2) if single_match.group(2) else section_type
                size = int(single_match.group(3), 16)
                object_path = single_match.group(4)
                
                if not object_path.startswith("0x") and size > 0:
                    objects[object_path][section_type][symbol_name] = size
                continue
            
            # Try to match a section.symbol line
            section_match = section_symbol_regex.match(line)
            if section_match:
                current_section = section_match.group(1)
                current_symbol = section_match.group(2)
                continue
            
            # Try to match a continuation line if we have a current section and symbol
            if current_section and current_symbol:
                cont_match = continuation_regex.match(line)
                if cont_match:
                    size = int(cont_match.group(1), 16)
                    object_path = cont_match.group(2)
                    
                    if not object_path.startswith("0x") and size > 0:
                        objects[object_path][current_section][current_symbol] = size
                    
                    current_section = None
                    current_symbol = None
    
    return objects

def filter_sections(differences, section_totals, mode):
    """
    Filter differences and totals to only include relevant sections for ROM or RAM analysis.
    """
    if mode is None:
        return differences, section_totals
        
    relevant_sections = ROM_SECTIONS if mode == 'rom' else RAM_SECTIONS
    
    # Filter section totals
    filtered_totals = {
        section: diff for section, diff in section_totals.items()
        if any(s in section for s in relevant_sections)
    }
    
    # Filter differences
    filtered_differences = {}
    for obj_path, sections in differences.items():
        filtered_sections = {
            section: symbols for section, symbols in sections.items()
            if any(s in section for s in relevant_sections)
        }
        if filtered_sections:
            filtered_differences[obj_path] = filtered_sections
            
    return filtered_differences, filtered_totals

def get_object_total_diff(sections):
    """
    Calculate total difference for an object across all its sections.
    """
    return sum(
        sum(info['diff'] for info in symbols.values())
        for symbols in sections.values()
    )

def get_section_total_diff(symbols):
    """
    Calculate total difference for a section.
    """
    return sum(info['diff'] for info in symbols.values())

def group_by_directory(differences):
    """
    Reorganize differences to group by directory first.
    """
    grouped = {}
    for obj_path, sections in differences.items():
        # Split path into directory and filename
        dirname = os.path.dirname(obj_path)
        if not dirname:
            dirname = "/"
        
        if dirname not in grouped:
            grouped[dirname] = {}
        grouped[dirname][obj_path] = sections
    
    return grouped

def print_tree(differences, section_totals, show_unchanged=False, mode=None):
    """
    Print the differences in a tree structure, similar to the ROM tree output.
    """
    # Filter sections based on mode
    differences, section_totals = filter_sections(differences, section_totals, mode)
    
    # First print section totals
    print("\nSection Totals:")
    print("-" * 80)
    total_diff = 0
    
    # Sort sections by absolute difference
    sorted_sections = sorted(
        section_totals.items(),
        key=lambda x: abs(x[1]),
        reverse=True
    )
    
    for section, diff in sorted_sections:
        total_diff += diff
        color = GREEN if diff > 0 else RED if diff < 0 else ""
        print(f".{section:20} {color}{diff:+d}{RESET} bytes")
    print("-" * 80)
    
    memory_type = "ROM" if mode == 'rom' else "RAM" if mode == 'ram' else "total"
    print(f"Total {memory_type} size difference: {total_diff:+d} bytes\n")
    
    if mode:
        print(f"Showing only {mode.upper()} sections. Sorted by impact (largest changes first).\n")
    
    # Group differences by directory
    grouped_differences = group_by_directory(differences)
    
    # Sort directories by total impact
    dir_impacts = {
        dirname: sum(get_object_total_diff(sections) for sections in dir_objects.values())
        for dirname, dir_objects in grouped_differences.items()
    }
    
    sorted_dirs = sorted(
        grouped_differences.items(),
        key=lambda x: abs(dir_impacts[x[0]]),
        reverse=True
    )
    
    # Print the tree
    for dir_idx, (dirname, dir_objects) in enumerate(sorted_dirs):
        is_last_dir = dir_idx == len(sorted_dirs) - 1
        dir_branch = "└── " if is_last_dir else "├── "
        dir_impact = dir_impacts[dirname]
        color = GREEN if dir_impact > 0 else RED if dir_impact < 0 else ""
        print(f"{dir_branch}{dirname}/ {color}({dir_impact:+d} bytes){RESET}")
        
        # Sort objects by total impact
        sorted_objects = sorted(
            dir_objects.items(),
            key=lambda x: abs(get_object_total_diff(x[1])),
            reverse=True
        )
        
        dir_prefix = "    " if is_last_dir else "│   "
        for obj_idx, (obj_path, sections) in enumerate(sorted_objects):
            is_last_obj = obj_idx == len(sorted_objects) - 1
            obj_branch = "└── " if is_last_obj else "├── "
            obj_impact = get_object_total_diff(sections)
            color = GREEN if obj_impact > 0 else RED if obj_impact < 0 else ""
            print(f"{dir_prefix}{obj_branch}{os.path.basename(obj_path)} {color}({obj_impact:+d} bytes){RESET}")
            
            # Sort sections by total impact
            sorted_sections = sorted(
                sections.items(),
                key=lambda x: abs(get_section_total_diff(x[1])),
                reverse=True
            )
            
            # Print sections
            obj_prefix = dir_prefix + ("    " if is_last_obj else "│   ")
            for section_idx, (section, symbols) in enumerate(sorted_sections):
                is_last_section = section_idx == len(sorted_sections) - 1
                section_branch = "└── " if is_last_section else "├── "
                section_diff = get_section_total_diff(symbols)
                
                color = GREEN if section_diff > 0 else RED if section_diff < 0 else ""
                print(f"{obj_prefix}{section_branch}.{section} {color}({section_diff:+d} bytes){RESET}")
                
                # Sort symbols by impact
                sorted_symbols = sorted(
                    symbols.items(),
                    key=lambda x: abs(x[1]['diff']),
                    reverse=True
                )
                
                # Print symbols
                section_prefix = obj_prefix + ("    " if is_last_section else "│   ")
                for symbol_idx, (symbol, info) in enumerate(sorted_symbols):
                    is_last_symbol = symbol_idx == len(sorted_symbols) - 1
                    symbol_branch = "└── " if is_last_symbol else "├── "
                    
                    if info['old_size'] == 0:
                        color = GREEN
                        status = "ADDED"
                    elif info['new_size'] == 0:
                        color = RED
                        status = "REMOVED"
                    else:
                        color = GREEN if info['diff'] > 0 else RED
                        status = "CHANGED"
                    
                    print(f"{section_prefix}{symbol_branch}{symbol:40} [{status}] ", end='')
                    if info['old_size'] > 0:
                        print(f"Old: {info['old_size']:6d}", end='')
                    if info['new_size'] > 0:
                        print(f" New: {info['new_size']:6d}", end='')
                    print(f" Diff: {color}{info['diff']:+d}{RESET}")

def compare_objects(old_objects, new_objects):
    """
    Compare two object dictionaries and return the differences.
    """
    differences = {}
    section_totals = defaultdict(int)
    
    # Get all unique object paths
    all_objects = set(old_objects.keys()) | set(new_objects.keys())
    
    for obj_path in all_objects:
        old_sections = old_objects.get(obj_path, {})
        new_sections = new_objects.get(obj_path, {})
        
        # Get all unique section types
        all_sections = set(old_sections.keys()) | set(new_sections.keys())
        
        object_diffs = {}
        for section in all_sections:
            old_symbols = old_sections.get(section, {})
            new_symbols = new_sections.get(section, {})
            
            # Get all unique symbols in this section
            all_symbols = set(old_symbols.keys()) | set(new_symbols.keys())
            
            section_diffs = {}
            for symbol in all_symbols:
                old_size = old_symbols.get(symbol, 0)
                new_size = new_symbols.get(symbol, 0)
                
                if old_size != new_size:
                    diff = new_size - old_size
                    section_diffs[symbol] = {
                        'old_size': old_size,
                        'new_size': new_size,
                        'diff': diff
                    }
                    section_totals[section] += diff
            
            if section_diffs:
                object_diffs[section] = section_diffs
        
        if object_diffs:
            differences[obj_path] = object_diffs
    
    return differences, section_totals

def main():
    parser = argparse.ArgumentParser(description='Compare symbol sizes between two map files.')
    parser.add_argument('old_map', help='Path to the old map file')
    parser.add_argument('new_map', help='Path to the new map file')
    parser.add_argument('--show-unchanged', action='store_true',
                      help='Show unchanged symbols in the output')
    parser.add_argument('--mode', choices=['rom', 'ram'],
                      help='Analysis mode: rom shows flash usage (.text, .rodata), '
                           'ram shows RAM usage (.data, .bss, .noinit)')
    args = parser.parse_args()

    try:
        old_objects = parse_map_file(args.old_map)
        new_objects = parse_map_file(args.new_map)
        
        differences, section_totals = compare_objects(old_objects, new_objects)
        
        if not differences:
            print("No differences found.")
        else:
            print_tree(differences, section_totals, args.show_unchanged, args.mode)
            
    except FileNotFoundError as e:
        print(f"Error: Could not find file {e.filename}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 