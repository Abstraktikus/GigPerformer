import re

with open("Global Rackspace V25.gpscript", "r") as f:
    lines = f.readlines()

# Sample a few functions to see dependency patterns
test_funcs = ["DebugCrash", "TraceActiveScope", "RefreshDiagDisplay", "ScrollToCurrentChannel", "TraceForensicChannelDump"]

funcs_set = {"Wait", "Trace", "DebugCrash", "TraceActiveScope", "GetFirstActiveScope", "RefreshDiagDisplay", "ScrollToCurrentChannel"}

func_lines = {}
for i, line in enumerate(lines):
    m = re.match(r'^Function\s+(\w+)', line)
    if m and m.group(1) in funcs_set:
        func_lines[m.group(1)] = i

for fname in test_funcs:
    if fname not in func_lines:
        print(f"{fname}: NOT FOUND")
        continue
    
    start = func_lines[fname]
    end = start + 1
    depth = 0
    while end < len(lines):
        s = lines[end].strip()
        if s and not s.startswith('//'):
            if s.startswith(('If ', 'While ', 'For ')):
                depth += 1
            elif s == 'End':
                if depth == 0:
                    break
                depth -= 1
        end += 1
    
    called = []
    for other in funcs_set:
        if other == fname:
            continue
        pat = r'\b' + re.escape(other) + r'\s*\('
        for j in range(start + 1, end):
            if re.search(pat, lines[j]):
                called.append(other)
                break
    
    print(f"{fname}: {called}")

