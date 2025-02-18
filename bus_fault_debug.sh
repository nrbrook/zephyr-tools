#!/bin/bash
#
# MIT License
# Copyright (c) 2025 Nick Brook
# See LICENSE file for details.
#
# bus_fault_debug.sh
#
# This script helps debug bus faults and hard faults in embedded systems by converting
# fault addresses to source code locations. It uses addr2line to convert addresses to
# source locations.
#
# Usage: ./bus_fault_debug.sh [path/to/zephyr.elf]
# If no ELF file is provided, the script will search build directories.
#
# Then follow the prompts to:
# 1. Select a build directory (if no ELF file provided and multiple builds exist)
# 2. Enter the fault address (in hex with 0x prefix)
#
# The script will show the source file and line number where the fault occurred.

# Check if addr2line is available
if ! command -v arm-none-eabi-addr2line &> /dev/null; then
    echo "Error: arm-none-eabi-addr2line not found."
    echo "To fix this, either:"
    echo "1. Add the ARM toolchain to your PATH"
    echo "2. Source the Zephyr environment with:"
    echo "   source \${ZEPHYR_BASE}/zephyr-env.sh"
    echo "   or"
    echo "   source /opt/nordic/ncs/v2.x.x/zephyrsdk/zephyr-env.sh"
    exit 1
fi

# If ELF file is provided as argument, use it
if [ $# -eq 1 ]; then
    elf_file="$1"
    if [ ! -f "$elf_file" ]; then
        echo "Error: Could not find ELF file at: $elf_file"
        exit 1
    fi
else
    # Find the script's directory and locate build directories
    script_dir=$(dirname "$0")
    build_dirs=$(find "$script_dir/.." -maxdepth 1 -type d -name "build*")

    # Check if any build directories were found
    if [ -z "$build_dirs" ]; then
        echo "Error: No build directories found."
        echo "Either:"
        echo "1. Provide the path to zephyr.elf as an argument"
        echo "2. Make sure you have built the project and are running this script from the tools directory"
        exit 1
    fi

    # If multiple build directories exist, let user select one
    if [ $(echo "$build_dirs" | wc -l) -eq 1 ]; then
        selected_build_dir=$build_dirs
    else
        echo "Multiple build directories found:"
        PS3="Please select a build directory: "
        select build_dir in $build_dirs; do
            if [ -n "$build_dir" ]; then
                echo "You selected: $build_dir"
                selected_build_dir=$build_dir
                break
            else
                echo "Error: Invalid selection"
                exit 1
            fi
        done
    fi

    # Set the default ELF file path
    elf_file="$selected_build_dir/application/zephyr/zephyr.elf"
    if [ ! -f "$elf_file" ]; then
        echo "Error: Could not find ELF file at: $elf_file"
        echo "Make sure you have built the project and the build directory is complete."
        exit 1
    fi
    echo "Using ELF file: $elf_file"
fi

# Get the fault address from user input
read -p "Enter the \"Faulting instruction address\" (hex with prefix 0x): " faulting_address

# Validate the address format
if [[ ! $faulting_address =~ ^0x[0-9A-Fa-f]+$ ]]; then
    echo "Error: Invalid address format."
    echo "Please enter a valid hex address with 0x prefix (e.g., 0x12345678)."
    exit 1
fi

# Convert the address to a source location
echo -e "\nFault location:"
if ! arm-none-eabi-addr2line -e "$elf_file" "$faulting_address"; then
    echo "Error: Failed to convert address to source location."
    echo "Make sure the address is valid and the build includes debug symbols."
    exit 1
fi
