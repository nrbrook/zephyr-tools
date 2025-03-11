#!/usr/bin/env python3
"""Analyse a map file to show the size of each section and symbol."""

#
# MIT License
# Copyright (c) 2025 Nick Brook
# See LICENSE file for details.
#
import argparse
import os
import sys
from collections import defaultdict

from map_file_utils import (
    filter_sections,
    get_object_total,
    get_section_total,
    group_by_directory,
    parse_map_file,
)

# ANSI escape codes for colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def print_section_totals(objects, mode=None):
    """
    Print total sizes for each section type.

    Args:
        objects: A dictionary of objects and their sections.
        mode: The mode to filter the sections by.
    """
    section_totals = defaultdict(int)

    # Calculate totals for each section
    for sections in objects.values():
        for section, symbols in sections.items():
            section_totals[section] += get_section_total(symbols)

    # Sort sections by size
    sorted_sections = sorted(section_totals.items(), key=lambda x: x[1], reverse=True)

    # Print totals
    print("\nSection Totals:")
    print("-" * 80)
    total_size = sum(size for _, size in sorted_sections)

    for section, size in sorted_sections:
        percentage = (size / total_size) * 100 if total_size > 0 else 0
        print(f".{section:20} {size:8d} bytes  ({percentage:5.1f}%)")

    print("-" * 80)
    memory_type = mode.upper() if mode else "total"
    print(f"Total {memory_type} size: {total_size:,d} bytes")


def print_symbol_analysis(objects, min_size=0, by_symbol=False):
    """
    Print detailed analysis of symbol sizes.

    Args:
        objects: A dictionary of objects and their sections.
        min_size: The minimum size of symbols to show.
        by_symbol: Whether to group identical symbols across all objects.
    """
    # Collect all symbols across all objects and sections
    if by_symbol:
        # Group by symbol name across all objects
        symbol_sizes = defaultdict(int)
        for obj_sections in objects.values():
            for section_symbols in obj_sections.values():
                for symbol, size in section_symbols.items():
                    symbol_sizes[symbol] += size

        # Print largest symbols
        print("\nLargest Symbols (across all objects):")
        print("-" * 80)
        for symbol, size in sorted(symbol_sizes.items(), key=lambda x: x[1], reverse=True):
            if size < min_size:
                break
            percentage = (size / sum(symbol_sizes.values())) * 100
            print(f"{symbol:60} {size:8d} bytes  ({percentage:5.1f}%)")
    else:
        # Print by object and section
        print("\nLargest Symbols by Object and Section:")
        print("-" * 80)

        # Group by directory for better organization
        grouped = group_by_directory(objects)

        for dirname, dir_objects in sorted(grouped.items()):
            dir_total = sum(get_object_total(sections) for sections in dir_objects.values())
            print(f"\n{dirname}/ ({dir_total:,d} bytes)")

            # Sort objects by total size
            sorted_objects = sorted(dir_objects.items(), key=lambda x: get_object_total(x[1]), reverse=True)

            for obj_path, sections in sorted_objects:
                obj_total = get_object_total(sections)
                print(f"\n  {os.path.basename(obj_path)} ({obj_total:,d} bytes)")

                # Sort sections by total size
                sorted_sections = sorted(sections.items(), key=lambda x: get_section_total(x[1]), reverse=True)

                for section, symbols in sorted_sections:
                    section_total = get_section_total(symbols)
                    print(f"    .{section} ({section_total:,d} bytes)")

                    # Sort symbols by size
                    sorted_symbols = sorted(symbols.items(), key=lambda x: x[1], reverse=True)

                    for symbol, size in sorted_symbols:
                        if size < min_size:
                            continue
                        percentage = (size / section_total) * 100
                        print(f"      {symbol:58} {size:8d} bytes  ({percentage:5.1f}%)")


def main():
    """Run the map file analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze symbol sizes in a map file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Show all symbols:
    %(prog)s zephyr.map
  Show ROM symbols over 1KB:
    %(prog)s zephyr.map --mode rom --min-size 1024
  Show largest RAM symbols grouped by name:
    %(prog)s zephyr.map --mode ram --by-symbol
  Generate HTML report:
    %(prog)s zephyr.map --html report.html
        """,
    )
    parser.add_argument("map_file", help="Path to the map file to analyze")
    parser.add_argument(
        "--mode",
        choices=["rom", "ram"],
        help="Analysis mode: rom shows flash usage (.text, .rodata), " "ram shows RAM usage (.data, .bss, .noinit)",
    )
    parser.add_argument("--min-size", type=int, default=0, help="Only show symbols larger than this size in bytes")
    parser.add_argument("--by-symbol", action="store_true", help="Group identical symbols across all objects")
    parser.add_argument("--html", metavar="FILE", help="Generate HTML report with interactive visualizations")
    args = parser.parse_args()

    try:
        # Parse and filter the map file
        objects = parse_map_file(args.map_file)
        if args.mode:
            objects = filter_sections(objects, args.mode)

        if not objects:
            print("No symbols found.")
            return

        if args.html:
            try:
                from analyse_map_file_report import generate_html_report
            except ImportError as e:
                print(f"Error: {e}")
                print("To use HTML output, install required packages:")
                print("pip install -r requirements.txt")
                return

            generate_html_report(
                objects,
                mode=args.mode,
                by_symbol=args.by_symbol,
                output_file=args.html,
                get_section_total=get_section_total,
                get_object_total=get_object_total,
                group_by_directory=group_by_directory,
            )
        else:
            # Print text analysis
            print_section_totals(objects, args.mode)
            print_symbol_analysis(objects, args.min_size, args.by_symbol)

    except FileNotFoundError:
        print(f"Error: Could not find map file: {args.map_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
