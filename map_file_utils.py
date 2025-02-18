#!/usr/bin/env python3
#
# MIT License
# Copyright (c) 2025 Nick Brook
# See LICENSE file for details.
#
import re
from collections import defaultdict
import os

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

def filter_sections(objects, mode=None):
    """
    Filter objects to only include relevant sections for ROM or RAM analysis.
    """
    if mode is None:
        return objects
        
    relevant_sections = ROM_SECTIONS if mode == 'rom' else RAM_SECTIONS
    
    filtered_objects = {}
    for obj_path, sections in objects.items():
        filtered_sections = {
            section: symbols for section, symbols in sections.items()
            if any(s in section for s in relevant_sections)
        }
        if filtered_sections:
            filtered_objects[obj_path] = filtered_sections
            
    return filtered_objects

def group_by_directory(objects):
    """
    Reorganize objects to group by directory first.
    """
    grouped = {}
    for obj_path, sections in objects.items():
        # Split path into directory and filename
        dirname = os.path.dirname(obj_path)
        if not dirname:
            dirname = "/"
        
        if dirname not in grouped:
            grouped[dirname] = {}
        grouped[dirname][obj_path] = sections
    
    return grouped

def get_section_total(symbols):
    """
    Calculate total size for a section.
    """
    return sum(size for size in symbols.values())

def get_object_total(sections):
    """
    Calculate total size for an object across all its sections.
    """
    return sum(get_section_total(symbols) for symbols in sections.values()) 