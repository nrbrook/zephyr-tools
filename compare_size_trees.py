#!/usr/bin/env python3
"""Compare two memory usage trees and show the differences."""
#
# MIT License
# Copyright (c) 2025 Nick Brook
# See LICENSE file for details.
#
import argparse
import re

# This script compares two memory usage trees and prints the differences.
# The trees are generated by Zephyr's ROM_MAP or RAM_MAP tools.
# These tools are part of the Zephyr SDK and are used to generate hierarchical
# views of memory usage.
#
# The trees are generated by the following commands:
# (after building the project normally)
# For ROM analysis:
#   west build --build-dir <build_dir>/application -t rom_report > rom_report.txt
# For RAM analysis:
#   west build --build-dir <build_dir>/application -t ram_report > ram_report.txt
#
# The trees are then compared using this script.
# The script takes two arguments: the old tree and the new tree.
# The script prints the differences in memory consumption.
#
# Example usage:
# python3 compare_size_trees.py old_report.txt new_report.txt [--show-unchanged] [--type rom|ram]

# ANSI escape codes for colors
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

# Regex to parse a tree line (assumes indent level = 4 characters)
line_regex = re.compile(r"^(?P<indent>(?:[ │]{4})*)(?:[├└]──\s+)?(?P<name>.*?)\s{2,}(?P<size>\d+)\s+[\d.]+%")


def parse_tree_file(filename):
    """
    Parse a tree file into a hierarchical dictionary.

    Args:
        filename: The path to the tree file.

    Returns:
        A hierarchical dictionary of the tree.
        Each node is a dict with:
        - name: the node name (e.g. "intent_handler.c")
        - size: the absolute size (an integer)
        - children: a list of child nodes (in order)
    """
    # Create an artificial root to hold all nodes
    root = {"name": "ROOT", "size": 0, "children": []}
    stack = [root]
    first_node = True

    with open(filename, "r") as f:
        for line in f:
            # Skip header/separator/blank lines.
            if line.startswith("Path") or line.startswith("=") or not line.strip():
                continue

            m = line_regex.match(line)
            if not m:
                continue

            indent = m.group("indent")
            level = len(indent) // 4
            name = m.group("name").strip()
            size = int(m.group("size"))

            # Skip the "Root" node as it's just a total
            if first_node and name == "Root":
                root["size"] = size  # Store the total
                first_node = False
                continue

            node = {"name": name, "size": size, "children": []}
            first_node = False

            # Adjust stack to correct level
            while len(stack) > level + 1:  # +1 because we have an artificial root
                stack.pop()

            # Add node to its parent
            parent = stack[-1]
            parent["children"].append(node)
            stack.append(node)

    return root


def merge_trees(old, new):
    """
    Merge two nodes (from the old and new trees) into one merged node.

    If a node exists only in one tree, that is recorded.
    Children are merged by matching node names (using the new tree order first).

    Args:
        old: The old node.
        new: The new node.

    Returns:
        A merged node.
    """
    if old is None or new is None:
        return {
            "name": new["name"] if new is not None else old["name"],
            "old_size": old["size"] if old is not None else None,
            "new_size": new["size"] if new is not None else None,
            "children": [],
            "has_changes": True,  # Node added or removed means it's changed
        }

    merged = {
        "name": new["name"],
        "old_size": old["size"],
        "new_size": new["size"],
        "children": [],
        "has_changes": False,
    }

    # Mark as changed if sizes are different
    if old["size"] != new["size"]:
        merged["has_changes"] = True

    # Build lookup dictionaries for children
    old_children = {child["name"]: child for child in old["children"]}
    new_children = {child["name"]: child for child in new["children"]}

    # First process all children from the new tree (maintaining their order)
    if new is not None:
        for new_child in new["children"]:
            old_child = old_children.get(new_child["name"])
            merged_child = merge_trees(old_child, new_child)
            merged["children"].append(merged_child)
            if merged_child["has_changes"]:
                merged["has_changes"] = True

    # Then add any children that only exist in the old tree
    if old is not None:
        for old_child in old["children"]:
            if old_child["name"] not in new_children:
                merged_child = merge_trees(old_child, None)
                merged["children"].append(merged_child)
                merged["has_changes"] = True

    return merged


def print_diff_tree(node, show_unchanged=False, prefix="", is_last=True):
    """
    Recursively print the diff tree.

    Annotates nodes that are added, removed, or changed.
    Unchanged nodes are only printed if:
    - show_unchanged is True, or
    - they have changed descendants, or
    - they themselves have changes

    Args:
        node: The node to print.
        show_unchanged: Whether to show unchanged nodes.
        prefix: The prefix to print.
        is_last: Whether the node is the last child of its parent.
    """
    # Get list of children that should be shown
    visible_children = [c for c in node["children"] if show_unchanged or c["has_changes"]]

    # Determine if this node should be shown:
    # - If show_unchanged is True, show everything
    # - If this node has changes, show it
    # - If this node has visible children, show it
    should_show = show_unchanged or node["has_changes"] or len(visible_children) > 0

    # Only show nodes that aren't our artificial root
    if should_show and node["name"] != "ROOT":
        branch = "└── " if is_last else "├── "
        line = prefix + branch + node["name"]
        diff_info = ""
        if node["old_size"] is None and node["new_size"] is not None:
            diff_info = f"(added: Size: {GREEN}{node['new_size']}{RESET})"
        elif node["old_size"] is not None and node["new_size"] is None:
            diff_info = f"(removed: Size: {RED}{node['old_size']}{RESET})"
        elif node["old_size"] is not None and node["new_size"] is not None:
            if node["old_size"] != node["new_size"]:
                diff = node["new_size"] - node["old_size"]
                color = GREEN if diff > 0 else RED
                diff_info = f"(changed: Old: {node['old_size']}, New: {node['new_size']}, Diff: {color}{diff}{RESET})"
            elif show_unchanged:
                diff_info = f"(unchanged: Size: {node['old_size']})"
        if diff_info:
            line += " " + diff_info
        print(line)

    # For the artificial root, don't add any prefix or show it
    if node["name"] == "ROOT":
        new_prefix = ""
    else:
        new_prefix = prefix + ("    " if is_last else "│   ")

    for i, child in enumerate(visible_children):
        print_diff_tree(child, show_unchanged, new_prefix, i == len(visible_children) - 1)


def main():
    """Run the memory usage tree comparison."""
    parser = argparse.ArgumentParser(description="Compare two memory usage trees and show the differences.")
    parser.add_argument("old_tree", help="Path to the old tree file")
    parser.add_argument("new_tree", help="Path to the new tree file")
    parser.add_argument("--show-unchanged", action="store_true", help="Show unchanged nodes in the output")
    args = parser.parse_args()

    old_root = parse_tree_file(args.old_tree)
    new_root = parse_tree_file(args.new_tree)
    merged = merge_trees(old_root, new_root)

    if not merged["has_changes"]:
        print("No differences found.")
    else:
        if old_root["size"] != 0 and new_root["size"] != 0:
            diff = new_root["size"] - old_root["size"]
            diff_percent = (diff / old_root["size"]) * 100
            print(f"Total usage change: {diff:+d} bytes ({diff_percent:+.1f}%)")
            print(f"Old total: {old_root['size']} bytes")
            print(f"New total: {new_root['size']} bytes")
        print("\nDetailed changes:")
        print_diff_tree(merged, args.show_unchanged, "", True)


if __name__ == "__main__":
    main()
