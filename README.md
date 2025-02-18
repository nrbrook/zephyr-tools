# Zephyr Tools

This directory contains tools for debugging tasks I've needed to perform on Zephyr projects.

## License

These tools are released under the MIT License. See the [LICENSE](LICENSE) file for details.

You are free to:
- Use commercially
- Distribute
- Modify
- Private use

Under the following conditions:
- Include the original license and copyright notice

## Tips for Memory Analysis

1. Use `compare_size_trees.py` for a high-level view of memory usage by component/directory
2. Use `compare_map_files.py` for detailed symbol-level analysis, or if the link step fails due to overflow (so Zephyr's ROM_MAP or RAM_MAP tools don't work):
   - Use `--mode rom` to focus on flash usage
   - Use `--mode ram` to focus on RAM usage
3. Look for:
   - Large individual symbols (functions or data)
   - Patterns of growth in specific directories
   - Unexpected additions or changes
4. Common optimization targets:
   - Large string constants in .rodata
   - Debug/logging code in .text
   - Uninitialized arrays in .bss
   - Initialized global variables in .data 

## Tools

### compare_size_trees.py

A tool for comparing memory usage between two builds by analyzing the tree output from Zephyr's ROM_MAP or RAM_MAP tools.

### Purpose
- Analyzes memory consumption differences between two builds
- Shows hierarchical view of memory usage by path
- Helps identify which components are contributing to size changes
- Works with both ROM (flash) and RAM reports

### Usage
```bash
# Generate trees for both builds first:
# For ROM analysis:
west build --build-dir build_old -t rom_report > rom_report_old.txt
west build --build-dir build_new -t rom_report > rom_report_new.txt

# For RAM analysis:
west build --build-dir build_old -t ram_report > ram_report_old.txt
west build --build-dir build_new -t ram_report > ram_report_new.txt

# Compare the trees
python3 compare_size_trees.py old_report.txt new_report.txt [--show-unchanged]
```

### Options
- `--show-unchanged`: Include entries that haven't changed in size

### Output Example
```
Total usage change: +100 bytes (+9.8%)
Old total: 1024 bytes
New total: 1124 bytes

Detailed changes:
app/                                    (changed: Old: 1024, New: 1124, Diff: +100)
  ├── main.c                           (changed: Old: 512, New: 552, Diff: +40)
  └── module/                          (changed: Old: 512, New: 572, Diff: +60)
      └── feature.c                    (changed: Old: 512, New: 572, Diff: +60)
```

## compare_map_files.py

A tool for analyzing memory usage differences between two builds by comparing their map files. Provides detailed analysis of both ROM (flash) and RAM usage at the symbol level.

### Purpose
- Compares symbol sizes between two map files
- Groups changes by directory and object file
- Can focus on either ROM or RAM usage
- Sorts by impact to easily identify "worst offenders"

### Usage
```bash
python3 compare_map_files.py old_map.map new_map.map [--mode rom|ram] [--show-unchanged]
```

### Options
- `--mode rom`: Show only ROM-related sections (.text, .rodata)
- `--mode ram`: Show only RAM-related sections (.data, .bss, .noinit)
- `--show-unchanged`: Include symbols that haven't changed in size

### Output Example
```
Section Totals:
--------------------------------------------------------------------------------
.text                 +256 bytes
.rodata              -32 bytes
--------------------------------------------------------------------------------
Total ROM size difference: +224 bytes

Showing only ROM sections. Sorted by impact (largest changes first).

├── app/ (+256 bytes)
│   └── libapp.a(system_settings.c.obj) (+256 bytes)
│       └── .text (+256 bytes)
│           ├── parse_uint                    [CHANGED] Old:    40 New:    52 Diff: +12
│           └── send_settings_change_event    [ADDED]           New:    34 Diff: +34
```

### Section Types
- ROM sections:
  - `.text`: Code/instructions
  - `.rodata`: Read-only data (constants)
- RAM sections:
  - `.data`: Initialized data
  - `.bss`: Uninitialized data
  - `.noinit`: Non-initialized data

## bus_fault_debug.sh

A utility script for debugging bus faults in embedded systems by converting fault addresses to source code locations.

### Purpose
- Helps debug hard faults and bus faults in embedded systems
- Converts fault addresses to source code file and line numbers
- Can use a specific ELF file or automatically find one in build directories
- Works with any ARM-based embedded system (including Zephyr RTOS)

### Usage
```bash
# Method 1: Let the script find the ELF file
./bus_fault_debug.sh

# Method 2: Specify the ELF file path directly
./bus_fault_debug.sh path/to/zephyr.elf
```

The script will then prompt you for the fault address (in hex with 0x prefix).

### ELF File Locations
The ELF file (zephyr.elf) is typically found in one of these locations:
1. In Zephyr builds:
   ```
   build_<board>/application/zephyr/zephyr.elf
   ```
2. In Nordic SDK builds:
   ```
   build_<board>/zephyr/zephyr.elf
   ```
3. Other common locations:
   ```
   out/zephyr.elf
   build/zephyr.elf
   ```

### Example
```bash
# Using automatic ELF file detection
$ ./bus_fault_debug.sh
Using ELF file: build_nrf52840dk/application/zephyr/zephyr.elf
Enter the "Faulting instruction address" (hex with prefix 0x): 0x12345678
Fault location:
../src/modules/system_controller.c:123

# Specifying ELF file directly
$ ./bus_fault_debug.sh build_nrf52840dk/application/zephyr/zephyr.elf
Enter the "Faulting instruction address" (hex with prefix 0x): 0x12345678
Fault location:
../src/modules/system_controller.c:123
```

### Requirements
- ARM toolchain (specifically `arm-none-eabi-addr2line`)
- ELF file must be built with debug symbols

If `arm-none-eabi-addr2line` is not found, you can:
1. Add the ARM toolchain to your PATH, or
2. Source the Zephyr environment:
   ```bash
   # If using Zephyr directly:
   source ${ZEPHYR_BASE}/zephyr-env.sh
   
   # If using Nordic Connect SDK:
   source /opt/nordic/ncs/v2.x.x/zephyrsdk/zephyr-env.sh
   ```

### Tips for Bus Fault Debugging
1. Get the fault address from your crash log or debugger output
2. Make sure you're using the ELF file that matches your firmware
3. Ensure the build includes debug symbols (default for development builds)
4. The address should be in hex format with '0x' prefix
5. If the output shows `??:0`, it means:
   - The address is invalid
   - The ELF file doesn't match the running firmware
   - The build doesn't include debug symbols
