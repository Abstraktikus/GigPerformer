#!/usr/bin/env python3
"""
Finds var declarations that appear after executable code within a function.
GPScript requires all var declarations before any executable statements.
"""
import re
import sys

filepath = "Global Rackspace V26.gpscript"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

func_pattern = re.compile(r'^Function\s+(\w+)')
var_pattern = re.compile(r'^\s+var\s+', re.IGNORECASE)
# Lines that are clearly executable (not declarations, not comments, not blank)
exec_patterns = [
    re.compile(r'^\s+(if |If |for |For |while |While |Select$|result |result=|[A-Za-z]\w+\s*=|[A-Za-z]\w+\s*\(|[A-Za-z]\w+\.\w+|SetWidget|GetWidget|Trace|Print|Send|End$)', re.IGNORECASE),
]

current_func = None
current_func_line = 0
seen_exec = False
issues = []

for i, line in enumerate(lines, 1):
    stripped = line.strip()

    # New function
    m = func_pattern.match(line)
    if m:
        current_func = m.group(1)
        current_func_line = i
        seen_exec = False
        continue

    if current_func is None:
        continue

    # End of function
    if stripped == 'End' and not line.startswith('   '):
        current_func = None
        continue

    # Skip blank lines and comments
    if stripped == '' or stripped.startswith('//'):
        continue

    # Check for var declaration
    if var_pattern.match(line):
        if seen_exec:
            issues.append((i, current_func, current_func_line, stripped))
        continue

    # Check for executable code
    for p in exec_patterns:
        if p.match(line):
            seen_exec = True
            break

print(f"LATE VAR DECLARATIONS: {len(issues)}")
for line_num, func, func_line, text in issues:
    print(f"  Line {line_num}: in {func} (def@{func_line}): {text[:80]}")
