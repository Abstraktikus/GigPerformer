#!/usr/bin/env python3
"""
Fixes forward reference violations by reordering functions using topological sort.
Maintains thematic section headers but orders functions strictly by dependency.
"""
import re
import sys

filepath = "Global Rackspace V26.gpscript"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
n = len(lines)

# ============================================================
# PHASE 1: Parse file into blocks
# ============================================================
func_pattern = re.compile(r'^Function\s+(\w+)\s*[\(]')
section_pattern = re.compile(r'^// SECTION \d+')

# Find Var block end (first Function line)
var_end = 0
for i, line in enumerate(lines):
    if func_pattern.match(line):
        var_end = i
        break

# Find Initialization start
init_start = 0
for i, line in enumerate(lines):
    if line.strip() == 'Initialization':
        init_start = i
        break

# Find all section headers in function area
section_headers = {}  # line_idx -> header text (including surrounding lines)
for i in range(var_end, init_start):
    if section_pattern.match(lines[i]):
        # Capture the header block (typically 3 lines: ====, SECTION, ====)
        start = max(var_end, i-1)
        while start > var_end and (lines[start].startswith('//') or lines[start].strip() == ''):
            start -= 1
        start += 1
        end = i + 1
        while end < init_start and (lines[end].startswith('//') or lines[end].strip() == ''):
            end += 1
        section_headers[i] = '\n'.join(lines[start:end])

# Parse functions with their preceding comments
functions = []  # list of (name, start_line, end_line, text)
i = var_end
comment_start = var_end

while i < init_start:
    line = lines[i]

    # Skip section headers
    if section_pattern.match(line):
        # Skip entire section header block
        while i < init_start and (lines[i].startswith('//') or lines[i].strip() == ''):
            i += 1
        comment_start = i
        continue

    # Track comment blocks
    if line.startswith('//') or line.strip() == '':
        i += 1
        continue

    m = func_pattern.match(line)
    if m:
        func_name = m.group(1)
        func_start = comment_start

        # Find end of function (top-level End)
        j = i + 1
        while j < init_start:
            stripped = lines[j].strip()
            if stripped == 'End' and (not lines[j].startswith('   ') or lines[j] == 'End'):
                j += 1
                break
            j += 1

        # Include trailing blank lines
        while j < init_start and lines[j].strip() == '':
            j += 1

        func_text = '\n'.join(lines[func_start:j])
        functions.append((func_name, i, j, func_text))

        comment_start = j
        i = j
        continue

    # Handle stray callbacks between functions (On WidgetValueChanged etc)
    if line.startswith('On '):
        j = i + 1
        while j < init_start:
            stripped = lines[j].strip()
            if stripped == 'End' and not lines[j].startswith('   '):
                j += 1
                break
            j += 1
        while j < init_start and lines[j].strip() == '':
            j += 1

        stray_text = '\n'.join(lines[comment_start:j])
        functions.append(('__CALLBACK__' + str(i), i, j, stray_text))
        comment_start = j
        i = j
        continue

    i += 1
    comment_start = i

print(f"Parsed {len(functions)} function blocks", file=sys.stderr)

# ============================================================
# PHASE 2: Build call graph
# ============================================================
func_names = {f[0] for f in functions}
func_line_map = {f[0]: f[1] for f in functions}

# For each function, find which other functions it calls
func_calls = {}  # name -> set of called function names
for name, start, end, text in functions:
    calls = set()
    for fline in text.split('\n'):
        # Skip the function declaration line itself
        if func_pattern.match(fline):
            continue
        found = re.findall(r'\b([A-Z]\w+)\s*\(', fline)
        for f in found:
            if f in func_names and f != name:
                calls.add(f)
    func_calls[name] = calls

# ============================================================
# PHASE 3: Topological sort (Kahn's algorithm)
# ============================================================
# Build in-degree map
in_degree = {f[0]: 0 for f in functions}
dependents = {f[0]: set() for f in functions}

for name, calls in func_calls.items():
    for callee in calls:
        if callee in in_degree:
            in_degree[callee] += 1  # wrong direction for topo sort

# Actually we need: if A calls B, then B must come before A
# So edges are: B -> A (B must be placed before A)
# in_degree of A = number of functions A calls (that must be placed first)

in_degree = {f[0]: 0 for f in functions}
reverse_deps = {f[0]: set() for f in functions}  # who depends on me

for name, calls in func_calls.items():
    for callee in calls:
        if callee in in_degree:
            in_degree[name] += 1  # name depends on callee
            reverse_deps[callee].add(name)

# Start with functions that have no dependencies
from collections import deque
queue = deque()
for f_name, _, _, _ in functions:
    if in_degree[f_name] == 0:
        queue.append(f_name)

ordered_names = []
while queue:
    # Among all available, prefer to pick the one that appeared earliest in original
    # This preserves thematic grouping as much as possible
    best = None
    best_line = float('inf')
    for candidate in queue:
        if func_line_map[candidate] < best_line:
            best = candidate
            best_line = func_line_map[candidate]

    queue.remove(best)
    ordered_names.append(best)

    for dependent in reverse_deps[best]:
        in_degree[dependent] -= 1
        if in_degree[dependent] == 0:
            queue.append(dependent)

if len(ordered_names) != len(functions):
    # Circular dependencies - add remaining in original order
    remaining = [f[0] for f in functions if f[0] not in set(ordered_names)]
    print(f"WARNING: {len(remaining)} functions in circular dependencies:", file=sys.stderr)
    for r in remaining:
        print(f"  {r}", file=sys.stderr)
    ordered_names.extend(remaining)

print(f"Topological sort: {len(ordered_names)} functions ordered", file=sys.stderr)

# ============================================================
# PHASE 4: Reassemble file
# ============================================================
func_text_map = {f[0]: f[3] for f in functions}

var_block = '\n'.join(lines[:var_end])
init_and_callbacks = '\n'.join(lines[init_start:])

# Determine section for each function based on its position in the ordered list
# We'll insert section headers at transitions
SECTION_MAP = {}
for name, start, end, text in functions:
    # Determine original section based on line number
    if start < 1161: SECTION_MAP[name] = 13
    elif start < 1397: SECTION_MAP[name] = 14
    elif start < 1979: SECTION_MAP[name] = 15
    elif start < 2842: SECTION_MAP[name] = 16
    elif start < 4581: SECTION_MAP[name] = 17
    elif start < 5704: SECTION_MAP[name] = 18
    elif start < 7371: SECTION_MAP[name] = 19
    elif start < 8120: SECTION_MAP[name] = 20
    elif start < 9192: SECTION_MAP[name] = 21
    elif start < 9603: SECTION_MAP[name] = 22
    else: SECTION_MAP[name] = 23

HEADERS = {
    13: "// ============================================================================\n// SECTION 13: CORE UTILITIES\n// ============================================================================\n",
    14: "// ============================================================================\n// SECTION 14: HARDWARE ABSTRACTION LAYER — RUNTIME\n// ============================================================================\n",
    15: "// ============================================================================\n// SECTION 15: MIDI & CHANNEL ENGINE\n// ============================================================================\n",
    16: "// ============================================================================\n// SECTION 16: DISPLAY ENGINE\n// ============================================================================\n",
    17: "// ============================================================================\n// SECTION 17: CONTROLLER MAP ENGINE\n// ============================================================================\n",
    18: "// ============================================================================\n// SECTION 18: LOOPER ENGINE\n// ============================================================================\n",
    19: "// ============================================================================\n// SECTION 19: PROMPTER & TIMELINE ENGINE\n// ============================================================================\n",
    20: "// ============================================================================\n// SECTION 20: VST REPLACER ENGINE\n// ============================================================================\n",
    21: "// ============================================================================\n// SECTION 21: ORCHESTRATION\n// ============================================================================\n",
    22: "// ============================================================================\n// SECTION 22: HARDWARE INPUT PROCESSING\n// ============================================================================\n",
    23: "// ============================================================================\n// SECTION 23: SONG & SNAPSHOT MANAGEMENT\n// ============================================================================\n",
}

# Build output
output_parts = [var_block, '']

last_section = -1
for name in ordered_names:
    sec = SECTION_MAP.get(name, 99)
    if sec != last_section and sec in HEADERS:
        output_parts.append('')
        output_parts.append(HEADERS[sec])
        last_section = sec
    output_parts.append(func_text_map[name])

output_parts.append('')
output_parts.append(init_and_callbacks)

output = '\n'.join(output_parts)

# Clean up excessive blank lines (more than 2 consecutive)
import re as re2
output = re2.sub(r'\n{4,}', '\n\n\n', output)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(output)

print(f"Output written: {output.count(chr(10))+1} lines", file=sys.stderr)
