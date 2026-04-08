#!/usr/bin/env python3
"""
Validates declare-before-use ordering in a GPScript file.
Finds all cases where a function calls another function that is defined LATER in the file.
"""
import re
import sys

filepath = "Global Rackspace V26.gpscript"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Step 1: Find all function definitions and their line numbers
func_defs = {}  # name -> line_number
func_pattern = re.compile(r'^Function\s+(\w+)\s*[\(]')
for i, line in enumerate(lines, 1):
    m = func_pattern.match(line)
    if m:
        func_defs[m.group(1)] = i

print(f"Found {len(func_defs)} function definitions", file=sys.stderr)

# Step 2: For each function, find what other user-defined functions it calls
# and check if they are defined BEFORE this function
errors = []
current_func = None
current_func_line = 0

for i, line in enumerate(lines, 1):
    m = func_pattern.match(line)
    if m:
        current_func = m.group(1)
        current_func_line = i
        continue

    if current_func is None:
        continue

    # Check for function calls in this line
    # Look for identifiers followed by (
    calls = re.findall(r'\b([A-Z]\w+)\s*\(', line)
    for call in calls:
        if call in func_defs:
            called_line = func_defs[call]
            if called_line > current_func_line:
                errors.append({
                    'caller': current_func,
                    'caller_line': current_func_line,
                    'callee': call,
                    'callee_line': called_line,
                    'call_at_line': i
                })

# Deduplicate by (caller, callee)
seen = set()
unique_errors = []
for e in errors:
    key = (e['caller'], e['callee'])
    if key not in seen:
        seen.add(key)
        unique_errors.append(e)

# Sort by caller line
unique_errors.sort(key=lambda x: x['call_at_line'])

print(f"\n{'='*80}")
print(f"FORWARD REFERENCE VIOLATIONS: {len(unique_errors)}")
print(f"{'='*80}\n")

for e in unique_errors:
    print(f"  Line {e['call_at_line']:5d}: {e['caller']} (def@{e['caller_line']}) calls {e['callee']} (def@{e['callee_line']})")

# Also group by: which functions need to move earlier?
needs_move = {}
for e in unique_errors:
    callee = e['callee']
    if callee not in needs_move:
        needs_move[callee] = {'defined_at': e['callee_line'], 'called_from': []}
    needs_move[callee]['called_from'].append((e['caller'], e['caller_line'], e['call_at_line']))

print(f"\n{'='*80}")
print(f"FUNCTIONS THAT NEED TO BE MOVED EARLIER: {len(needs_move)}")
print(f"{'='*80}\n")

for name, info in sorted(needs_move.items(), key=lambda x: x[1]['defined_at']):
    earliest_call = min(c[2] for c in info['called_from'])
    print(f"  {name} (def@{info['defined_at']}) — needs to be before line {earliest_call}")
    for caller, caller_line, call_line in info['called_from']:
        print(f"    called by {caller} (def@{caller_line}) at line {call_line}")
