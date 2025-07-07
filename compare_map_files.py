#!/usr/bin/env python3
"""Compare two map files to show the differences."""
#
# MIT License
# Copyright (c) 2025 Nick Brook
# See LICENSE file for details.
#
import argparse
import os
from collections import defaultdict

from compare_map_report import generate_html_report
from map_file_utils import group_by_directory, parse_map_file

# ANSI escape codes for colors
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

# Section classifications
ROM_SECTIONS = {"text", "rodata"}
RAM_SECTIONS = {"data", "bss", "noinit"}


def filter_sections_by_mode(objects, mode=None, custom_sections=None):
    """
    Filter objects to only include relevant sections for ROM or RAM analysis, or custom sections.

    Args:
        objects: A dictionary of objects and their sections.
        mode: The mode to filter the sections by ('rom' or 'ram').
        custom_sections: A set of custom section names to filter by.

    Returns:
        A dictionary of objects and their filtered sections.
    """
    if custom_sections:
        relevant_sections = custom_sections
    elif mode == "rom":
        relevant_sections = ROM_SECTIONS
    elif mode == "ram":
        relevant_sections = RAM_SECTIONS
    else:
        return objects

    filtered_objects = {}
    for obj_path, sections in objects.items():
        filtered_sections = {
            section: symbols for section, symbols in sections.items() if any(s in section for s in relevant_sections)
        }
        if filtered_sections:
            filtered_objects[obj_path] = filtered_sections

    return filtered_objects


def filter_differences(differences, section_totals, mode=None, custom_sections=None):
    """
    Filter differences and totals to only include relevant sections for ROM or RAM analysis, or custom sections.

    Args:
        differences: A dictionary of objects and their differences.
        section_totals: A dictionary of section totals.
        mode: The mode to filter the sections by ('rom' or 'ram').
        custom_sections: A set of custom section names to filter by.

    Returns:
        A tuple of the filtered differences and totals.
    """
    if custom_sections:
        relevant_sections = custom_sections
    elif mode == "rom":
        relevant_sections = ROM_SECTIONS
    elif mode == "ram":
        relevant_sections = RAM_SECTIONS
    else:
        return differences, section_totals

    # Filter section totals
    filtered_totals = {
        section: diff for section, diff in section_totals.items() if any(s in section for s in relevant_sections)
    }

    # Filter differences
    filtered_differences = {}
    for obj_path, sections in differences.items():
        filtered_sections = {
            section: symbols for section, symbols in sections.items() if any(s in section for s in relevant_sections)
        }
        if filtered_sections:
            filtered_differences[obj_path] = filtered_sections

    return filtered_differences, filtered_totals


def get_object_total_diff(sections):
    """
    Calculate total difference for an object across all its sections.

    Args:
        sections: A dictionary of sections and their symbols.

    Returns:
        The total difference for the object.
    """
    return sum(sum(info["diff"] for info in symbols.values()) for symbols in sections.values())


def get_section_total_diff(symbols):
    """
    Calculate total difference for a section.

    Args:
        symbols: A dictionary of symbols and their differences.

    Returns:
        The total difference for the section.
    """
    return sum(info["diff"] for info in symbols.values())


def print_tree(differences, section_totals, show_unchanged=False, mode=None, custom_sections=None):
    """
    Print the differences in a tree structure, similar to the ROM tree output.

    Args:
        differences: A dictionary of objects and their differences.
        section_totals: A dictionary of section totals.
        show_unchanged: Whether to show unchanged symbols.
        mode: The mode to filter the sections by ('rom' or 'ram').
        custom_sections: A set of custom section names to filter by.
    """
    # Filter sections based on mode or custom sections
    differences, section_totals = filter_differences(differences, section_totals, mode, custom_sections)

    # First print section totals
    print("\nSection Totals:")
    print("-" * 80)
    total_diff = 0

    # Sort sections by absolute difference
    sorted_sections = sorted(section_totals.items(), key=lambda x: abs(x[1]), reverse=True)

    for section, diff in sorted_sections:
        total_diff += diff
        color = GREEN if diff > 0 else RED if diff < 0 else ""
        print(f".{section:20} {color}{diff:+d}{RESET} bytes")
    print("-" * 80)

    if custom_sections:
        filter_desc = f"custom sections ({', '.join(sorted(custom_sections))})"
    elif mode:
        filter_desc = f"{mode.upper()} sections"
    else:
        filter_desc = "total"
    
    print(f"Total {filter_desc} size difference: {total_diff:+d} bytes\n")

    if mode or custom_sections:
        if custom_sections:
            sections_list = ', '.join(sorted(custom_sections))
            print(f"Showing only custom sections: {sections_list}. Sorted by impact (largest changes first).\n")
        else:
            print(f"Showing only {mode.upper()} sections. Sorted by impact (largest changes first).\n")

    # Group differences by directory
    grouped_differences = group_by_directory(differences)

    # Sort directories by total impact
    dir_impacts = {
        dirname: sum(get_object_total_diff(sections) for sections in dir_objects.values())
        for dirname, dir_objects in grouped_differences.items()
    }

    sorted_dirs = sorted(grouped_differences.items(), key=lambda x: abs(dir_impacts[x[0]]), reverse=True)

    # Print the tree
    for dir_idx, (dirname, dir_objects) in enumerate(sorted_dirs):
        is_last_dir = dir_idx == len(sorted_dirs) - 1
        dir_branch = "└── " if is_last_dir else "├── "
        dir_impact = dir_impacts[dirname]
        color = GREEN if dir_impact > 0 else RED if dir_impact < 0 else ""
        print(f"{dir_branch}{dirname}/ {color}({dir_impact:+d} bytes){RESET}")

        # Sort objects by total impact
        sorted_objects = sorted(dir_objects.items(), key=lambda x: abs(get_object_total_diff(x[1])), reverse=True)

        dir_prefix = "    " if is_last_dir else "│   "
        for obj_idx, (obj_path, sections) in enumerate(sorted_objects):
            is_last_obj = obj_idx == len(sorted_objects) - 1
            obj_branch = "└── " if is_last_obj else "├── "
            obj_impact = get_object_total_diff(sections)
            color = GREEN if obj_impact > 0 else RED if obj_impact < 0 else ""
            print(f"{dir_prefix}{obj_branch}{os.path.basename(obj_path)} {color}({obj_impact:+d} bytes){RESET}")

            # Sort sections by total impact
            sorted_sections = sorted(sections.items(), key=lambda x: abs(get_section_total_diff(x[1])), reverse=True)

            # Print sections
            obj_prefix = dir_prefix + ("    " if is_last_obj else "│   ")
            for section_idx, (section, symbols) in enumerate(sorted_sections):
                is_last_section = section_idx == len(sorted_sections) - 1
                section_branch = "└── " if is_last_section else "├── "
                section_diff = get_section_total_diff(symbols)

                color = GREEN if section_diff > 0 else RED if section_diff < 0 else ""
                print(f"{obj_prefix}{section_branch}.{section} {color}({section_diff:+d} bytes){RESET}")

                # Sort symbols by impact
                sorted_symbols = sorted(symbols.items(), key=lambda x: abs(x[1]["diff"]), reverse=True)

                # Print symbols
                section_prefix = obj_prefix + ("    " if is_last_section else "│   ")
                for symbol_idx, (symbol, info) in enumerate(sorted_symbols):
                    is_last_symbol = symbol_idx == len(sorted_symbols) - 1
                    symbol_branch = "└── " if is_last_symbol else "├── "

                    if info["old_size"] == 0:
                        color = GREEN
                        status = "ADDED"
                    elif info["new_size"] == 0:
                        color = RED
                        status = "REMOVED"
                    else:
                        color = GREEN if info["diff"] > 0 else RED
                        status = "CHANGED"

                    print(f"{section_prefix}{symbol_branch}{symbol:40} [{status}] ", end="")
                    if info["old_size"] > 0:
                        print(f"Old: {info['old_size']:6d}", end="")
                    if info["new_size"] > 0:
                        print(f" New: {info['new_size']:6d}", end="")
                    print(f" Diff: {color}{info['diff']:+d}{RESET}")


def compare_objects(old_objects, new_objects):
    """
    Compare two object dictionaries and return the differences.

    Args:
        old_objects: A dictionary of old objects and their sections.
        new_objects: A dictionary of new objects and their sections.

    Returns:
        A tuple of the differences and section totals.
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
                    section_diffs[symbol] = {"old_size": old_size, "new_size": new_size, "diff": diff}
                    section_totals[section] += diff

            if section_diffs:
                object_diffs[section] = section_diffs

        if object_diffs:
            differences[obj_path] = object_diffs

    return differences, section_totals


def main():
    """Run the map file comparison."""
    parser = argparse.ArgumentParser(description="Compare memory usage between two map files")
    parser.add_argument("old_map", help="Path to the old map file")
    parser.add_argument("new_map", help="Path to the new map file")
    parser.add_argument("--mode", choices=["rom", "ram"], help="Show only ROM or RAM sections")
    parser.add_argument("--sections", nargs="+", help="Show only specified sections (e.g., --sections text rodata)")
    parser.add_argument("--show-unchanged", action="store_true", help="Show symbols that have not changed")
    parser.add_argument("--html", metavar="FILE", help="Generate HTML report")
    args = parser.parse_args()

    # Validate arguments
    if args.mode and args.sections:
        parser.error("Cannot specify both --mode and --sections options")

    # Parse map files
    old_objects = parse_map_file(args.old_map)
    new_objects = parse_map_file(args.new_map)

    # Convert sections list to set for filtering
    custom_sections = set(args.sections) if args.sections else None

    # Filter sections if mode or custom sections specified
    if args.mode or custom_sections:
        old_objects = filter_sections_by_mode(old_objects, args.mode, custom_sections)
        new_objects = filter_sections_by_mode(new_objects, args.mode, custom_sections)

    # Group by directory
    old_by_dir = group_by_directory(old_objects)
    new_by_dir = group_by_directory(new_objects)

    # Calculate differences
    differences = {}
    section_totals = {}

    # Process all directories
    all_dirs = set(old_by_dir.keys()) | set(new_by_dir.keys())
    for dirname in sorted(all_dirs):
        old_dir = old_by_dir.get(dirname, {})
        new_dir = new_by_dir.get(dirname, {})

        # Process all objects in this directory
        all_objects = set(old_dir.keys()) | set(new_dir.keys())
        for obj_path in sorted(all_objects):
            old_obj = old_dir.get(obj_path, {})
            new_obj = new_dir.get(obj_path, {})

            # Process all sections in this object
            all_sections = set(old_obj.keys()) | set(new_obj.keys())
            for section in sorted(all_sections):
                old_section = old_obj.get(section, {})
                new_section = new_dir.get(obj_path, {}).get(section, {})

                # Process all symbols in this section
                all_symbols = set(old_section.keys()) | set(new_section.keys())
                for symbol in sorted(all_symbols):
                    old_size = old_section.get(symbol, 0)
                    new_size = new_section.get(symbol, 0)
                    diff = new_size - old_size

                    # Skip if unchanged and not showing unchanged
                    if not args.show_unchanged and diff == 0:
                        continue

                    # Initialize data structures if needed
                    if dirname not in differences:
                        differences[dirname] = {}
                    if obj_path not in differences[dirname]:
                        differences[dirname][obj_path] = {}
                    if section not in differences[dirname][obj_path]:
                        differences[dirname][obj_path][section] = {}

                    # Store symbol info
                    differences[dirname][obj_path][section][symbol] = {
                        "old_size": old_size,
                        "new_size": new_size,
                        "diff": diff,
                    }

                    # Update section totals
                    if section not in section_totals:
                        section_totals[section] = 0
                    section_totals[section] += diff

    if args.html:
        generate_html_report(differences, section_totals, args.mode, args.html, custom_sections)
    else:
        # Print text report
        print("Section Totals:")
        print("-" * 80)
        total_diff = 0
        for section, diff in sorted(section_totals.items()):
            if diff != 0:
                print(f".{section:<20} {diff:+,d} bytes")
                total_diff += diff
        print("-" * 80)
        print(f"Total size difference: {total_diff:+,d} bytes")
        print()

        if custom_sections:
            print(f"Showing only custom sections: {', '.join(sorted(custom_sections))}. ", end="")
        elif args.mode:
            print(f"Showing only {args.mode.upper()} sections. ", end="")
        print("Sorted by impact (largest changes first).")
        print()

        # Print detailed changes
        for dirname, dir_objects in sorted(
            differences.items(),
            key=lambda x: sum(
                abs(info["diff"]) for obj in x[1].values() for section in obj.values() for info in section.values()
            ),
            reverse=True,
        ):
            dir_total = sum(
                info["diff"] for obj in dir_objects.values() for section in obj.values() for info in section.values()
            )
            if dir_total == 0 and not args.show_unchanged:
                continue

            print(f"├── {dirname}/ ({dir_total:+,d} bytes)")

            for obj_path, sections in sorted(
                dir_objects.items(),
                key=lambda x: sum(abs(info["diff"]) for section in x[1].values() for info in section.values()),
                reverse=True,
            ):
                obj_total = sum(info["diff"] for section in sections.values() for info in section.values())
                if obj_total == 0 and not args.show_unchanged:
                    continue

                obj_name = os.path.basename(obj_path)
                print(f"│   └── {obj_name} ({obj_total:+,d} bytes)")

                for section, symbols in sorted(
                    sections.items(), key=lambda x: sum(abs(info["diff"]) for info in x[1].values()), reverse=True
                ):
                    section_total = sum(info["diff"] for info in symbols.values())
                    if section_total == 0 and not args.show_unchanged:
                        continue

                    print(f"│       └── .{section} ({section_total:+,d} bytes)")

                    for symbol, info in sorted(symbols.items(), key=lambda x: abs(x[1]["diff"]), reverse=True):
                        if info["diff"] == 0 and not args.show_unchanged:
                            continue

                        if info["old_size"] == 0:
                            status = "[ADDED]"
                            size_str = f"New: {info['new_size']:6,d}"
                        elif info["new_size"] == 0:
                            status = "[REMOVED]"
                            size_str = f"Old: {info['old_size']:6,d}"
                        else:
                            status = "[CHANGED]"
                            size_str = f"Old: {info['old_size']:6,d} New: {info['new_size']:6,d}"

                        print(f"│           └── {symbol:40} {status:10} {size_str:25} Diff: {info['diff']:+,d}")


if __name__ == "__main__":
    main()
