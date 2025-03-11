#!/usr/bin/env python3
"""Generate an HTML report for the map file comparison."""
#
# MIT License
# Copyright (c) 2025 Nick Brook
# See LICENSE file for details.
#
import html
import os

from jinja2 import Template


def generate_html_report(differences, section_totals, mode=None, output_file=None):
    """
    Generate an HTML report for the map file comparison.

    Args:
        differences: A dictionary of objects and their differences.
        section_totals: A dictionary of section totals.
        mode: The mode to filter the sections by.
        output_file: The file to write the report to.
    """
    # Calculate old and new totals
    old_total = 0
    new_total = 0
    section_totals_data = {}

    # First calculate section totals
    for dirname, dir_objects in differences.items():
        for obj_path, sections in dir_objects.items():
            for section, symbols in sections.items():
                if section not in section_totals_data:
                    section_totals_data[section] = {"old_size": 0, "new_size": 0}
                for symbol_info in symbols.values():
                    section_totals_data[section]["old_size"] += symbol_info["old_size"]
                    section_totals_data[section]["new_size"] += symbol_info["new_size"]
                    old_total += symbol_info["old_size"]
                    new_total += symbol_info["new_size"]

    # Prepare directory tree data
    directories = []
    for dirname, dir_objects in sorted(differences.items()):
        dir_diff = 0
        dir_data = {"name": dirname, "objects": [], "diff": 0}

        for obj_path, sections in sorted(dir_objects.items()):
            obj_name = os.path.basename(obj_path)
            obj_diff = 0
            obj_data = {"name": obj_name, "sections": [], "diff": 0}

            for section, symbols in sorted(sections.items()):
                section_diff = 0
                section_node = {"name": section, "symbols": [], "diff": 0}

                for symbol, info in sorted(symbols.items()):
                    diff = info["diff"]
                    section_diff += diff

                    if info["old_size"] == 0:
                        status = "ADDED"
                    elif info["new_size"] == 0:
                        status = "REMOVED"
                    else:
                        status = "CHANGED"

                    symbol_data = {
                        "name": html.escape(symbol),
                        "old_size": info["old_size"],
                        "new_size": info["new_size"],
                        "diff": diff,
                        "status": status,
                    }
                    section_node["symbols"].append(symbol_data)

                section_node["diff"] = section_diff
                obj_diff += section_diff
                if section_diff != 0:  # Only add sections with changes
                    obj_data["sections"].append(section_node)

            obj_data["diff"] = obj_diff
            dir_diff += obj_diff
            if obj_diff != 0:  # Only add objects with changes
                dir_data["objects"].append(obj_data)

        dir_data["diff"] = dir_diff
        if dir_diff != 0:  # Only add directories with changes
            directories.append(dir_data)

    # Sort everything by impact (absolute diff value)
    directories.sort(key=lambda x: abs(x["diff"]), reverse=True)
    for dir_data in directories:
        dir_data["objects"].sort(key=lambda x: abs(x["diff"]), reverse=True)
        for obj_data in dir_data["objects"]:
            obj_data["sections"].sort(key=lambda x: abs(x["diff"]), reverse=True)
            for section_data in obj_data["sections"]:
                section_data["symbols"].sort(key=lambda x: abs(x["diff"]), reverse=True)

    # Prepare template data
    template_data = {
        "mode": mode,
        "old_total": old_total,
        "new_total": new_total,
        "section_totals": section_totals_data,
        "directories": directories,
    }

    # Load and render template
    template_path = os.path.join(os.path.dirname(__file__), "templates", "map_comparison.html")
    with open(template_path) as f:
        template = Template(f.read())

    html_output = template.render(**template_data)

    if output_file:
        with open(output_file, "w") as f:
            f.write(html_output)
        print(f"HTML report written to: {output_file}")
    else:
        print(html_output)
