#!/usr/bin/env python3
"""Generate an HTML report from a map file."""
#
# MIT License
# Copyright (c) 2025 Nick Brook
# See LICENSE file for details.
#
import html
import json
import os
from collections import defaultdict

from jinja2 import Template


def prepare_treemap_data(
    objects, by_symbol=False, get_section_total=None, get_object_total=None, group_by_directory=None
):
    """
    Prepare data for plotly treemap visualization.

    Args:
        objects: A dictionary of objects and their sections.
        by_symbol: Whether to group identical symbols across all objects.
        get_section_total: A function to get the total size of a section.
        get_object_total: A function to get the total size of an object.
        group_by_directory: A function to group objects by directory.

    Returns:
        A list of dictionaries containing the data for the treemap.
    """
    if by_symbol:
        # Group by symbol name
        symbol_sizes = defaultdict(int)
        for obj_sections in objects.values():
            for section_symbols in obj_sections.values():
                for symbol, size in section_symbols.items():
                    symbol_sizes[symbol] += size

        # Create treemap data
        return [
            {
                "type": "treemap",
                "labels": ["Total"]
                + [
                    f"{symbol} ({size:,d} bytes)"
                    for symbol, size in sorted(symbol_sizes.items(), key=lambda x: x[1], reverse=True)
                ],
                "parents": [""] + ["Total"] * len(symbol_sizes),
                "values": [sum(symbol_sizes.values())]
                + list(dict(sorted(symbol_sizes.items(), key=lambda x: x[1], reverse=True)).values()),
                "textinfo": "label",
                "hoverongaps": False,
                "maxdepth": 2,
                "branchvalues": "total",
            }
        ]
    else:
        # Prepare hierarchical data
        labels = ["Total"]
        parents = [""]
        values = [sum(get_object_total(sections) for sections in objects.values())]

        # Group by directory
        grouped = group_by_directory(objects)
        for dirname, dir_objects in sorted(
            grouped.items(), key=lambda x: sum(get_object_total(sections) for sections in x[1].values()), reverse=True
        ):
            dir_total = sum(get_object_total(sections) for sections in dir_objects.values())
            dir_label = f"{dirname}/ ({dir_total:,d} bytes)"
            labels.append(dir_label)
            parents.append("Total")
            values.append(dir_total)

            # Add objects
            for obj_path, sections in sorted(dir_objects.items(), key=lambda x: get_object_total(x[1]), reverse=True):
                obj_name = os.path.basename(obj_path)
                obj_total = get_object_total(sections)
                obj_label = f"{obj_name} ({obj_total:,d} bytes)"
                labels.append(obj_label)
                parents.append(dir_label)
                values.append(obj_total)

                # Add sections
                for section, symbols in sorted(sections.items(), key=lambda x: get_section_total(x[1]), reverse=True):
                    section_total = get_section_total(symbols)
                    # Make section labels unique by including object name
                    section_label = f"{obj_name}: .{section} ({section_total:,d} bytes)"
                    labels.append(section_label)
                    parents.append(obj_label)
                    values.append(section_total)

                    # Add symbols
                    for symbol, size in sorted(symbols.items(), key=lambda x: x[1], reverse=True):
                        safe_symbol = html.escape(symbol)
                        # Make symbol labels unique by including section and object context
                        symbol_label = f"{obj_name}: .{section}: {safe_symbol} ({size:,d} bytes)"
                        labels.append(symbol_label)
                        parents.append(section_label)
                        values.append(size)

        # Create treemap data
        return [
            {
                "type": "treemap",
                "labels": labels,
                "parents": parents,
                "values": values,
                "textinfo": "label",
                "hoverongaps": False,
                "maxdepth": 4,
                "branchvalues": "total",
            }
        ]


def generate_html_report(
    objects,
    mode=None,
    by_symbol=False,
    output_file=None,
    get_section_total=None,
    get_object_total=None,
    group_by_directory=None,
):
    """
    Generate an HTML report with interactive visualizations.

    Args:
        objects: A dictionary of objects and their sections.
        mode: The mode to filter the sections by.
        by_symbol: Whether to group identical symbols across all objects.
        output_file: The file to write the report to.
        get_section_total: A function to get the total size of a section.
        get_object_total: A function to get the total size of an object.
        group_by_directory: A function to group objects by directory.
    """
    # Define section explanations
    section_explanations = {
        "text": "Executable code.",
        "rodata": "Read-only data (constants, string literals).",
        "data": "Initialized global and static variables.",
        "bss": "Uninitialized global and static variables (zero-initialized at runtime).",
        "noinit": "Uninitialized data that is not zero-initialized at runtime.",
        "datas": "Initialized data in RAM.",
        "initlevel": "Initialization functions sorted by priority level.",
        "sw_isr_table": "Software interrupt service routine table.",
        "device_handles": "Device driver instance handles.",
        "k_timer_area": "Kernel timer data.",
        "k_mem_slab_area": "Kernel memory slab allocator data.",
        "k_heap_area": "Kernel heap allocator data.",
        "k_mutex_area": "Kernel mutex data.",
        "k_msgq_area": "Kernel message queue data.",
        "k_sem_area": "Kernel semaphore data.",
        "k_queue_area": "Kernel queue data.",
        "app_shmem_regions": "Application shared memory regions.",
        "priv_stacks": "Private thread stacks.",
        "stacks": "Thread stacks.",
    }

    # Calculate section totals
    section_totals = defaultdict(lambda: {"size": 0, "percentage": 0})
    total_size = 0

    for sections in objects.values():
        for section, symbols in sections.items():
            section_size = get_section_total(symbols)
            section_totals[section]["size"] += section_size
            total_size += section_size

    # Calculate percentages
    for section_info in section_totals.values():
        section_info["percentage"] = (section_info["size"] / total_size * 100) if total_size > 0 else 0

    # Sort section totals by size
    section_totals = dict(sorted(section_totals.items(), key=lambda x: x[1]["size"], reverse=True))

    # Filter section explanations to only include sections present in the analysis
    filtered_explanations = {
        section: section_explanations.get(section, "No description available.")
        for section in section_totals.keys()
    }

    # Prepare data for the template
    template_data = {
        "mode": mode,
        "by_symbol": by_symbol,
        "section_totals": section_totals,
        "total_size": total_size,
        "section_explanations": filtered_explanations,
        "treemap_data": json.dumps(
            prepare_treemap_data(
                objects,
                by_symbol=by_symbol,
                get_section_total=get_section_total,
                get_object_total=get_object_total,
                group_by_directory=group_by_directory,
            )
        ),
    }

    if by_symbol:
        # Prepare symbol list
        symbol_sizes = defaultdict(int)
        for obj_sections in objects.values():
            for section_symbols in obj_sections.values():
                for symbol, size in section_symbols.items():
                    symbol_sizes[symbol] += size

        template_data["symbols"] = [
            {
                "name": html.escape(symbol),
                "size": size,
                "percentage": (size / total_size * 100) if total_size > 0 else 0,
            }
            for symbol, size in sorted(symbol_sizes.items(), key=lambda x: x[1], reverse=True)
        ]
    else:
        # Prepare directory tree
        grouped = group_by_directory(objects)
        template_data["directories"] = []

        # Sort directories by total size
        for dirname, dir_objects in sorted(
            grouped.items(), key=lambda x: sum(get_object_total(sections) for sections in x[1].values()), reverse=True
        ):
            dir_data = {
                "name": dirname,
                "size": sum(get_object_total(sections) for sections in dir_objects.values()),
                "objects": [],
            }

            # Sort objects by total size
            for obj_path, sections in sorted(dir_objects.items(), key=lambda x: get_object_total(x[1]), reverse=True):
                obj_data = {"name": os.path.basename(obj_path), "size": get_object_total(sections), "sections": []}

                # Sort sections by total size
                for section, symbols in sorted(sections.items(), key=lambda x: get_section_total(x[1]), reverse=True):
                    section_total = get_section_total(symbols)
                    section_data = {
                        "name": section,
                        "size": section_total,
                        "symbols": [
                            {
                                "name": html.escape(symbol),
                                "size": size,
                                "percentage": (size / section_total * 100) if section_total > 0 else 0,
                            }
                            for symbol, size in sorted(symbols.items(), key=lambda x: x[1], reverse=True)
                        ],
                    }
                    obj_data["sections"].append(section_data)

                dir_data["objects"].append(obj_data)

            template_data["directories"].append(dir_data)

    # Load and render template
    template_path = os.path.join(os.path.dirname(__file__), "templates", "memory_analysis.html")
    with open(template_path) as f:
        template = Template(f.read())

    html_output = template.render(**template_data)

    if output_file:
        with open(output_file, "w") as f:
            f.write(html_output)
        print(f"HTML report written to: {output_file}")
    else:
        print(html_output)
