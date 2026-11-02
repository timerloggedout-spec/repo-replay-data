import re, sys

input_file = os.path.expanduser("~/.zshrc")
backup = os.path.expanduser("~/.zshrc.backup")
output_lines = []
aliases_seen = {}   # alias_name -> line_index
functions_seen = {} # function_name -> line_index

with open(input_file, 'r') as f:
    lines = f.readlines()

# First pass: record last occurrence of each alias/function
for i, line in enumerate(lines):
    # Match 'alias foo=...' or 'alias foo="..."'
    m = re.match(r'^alias\s+([^=]+)=', line)
    if m:
        name = m.group(1).strip()
        aliases_seen[name] = i
        continue
    # Match bare assignments that look like aliases: foo=...
    m = re.match(r'^(\w[\w_-]*)=(.*)', line)
    if m and not line.startswith(('#', 'export', 'typeset', 'function', 'if', 'for')):
        name = m.group(1)
        if any(cmd in m.group(2) for cmd in ['python3', 'bash', 'cd ', 'jq', '~/']):
            # Treat as alias-like
            aliases_seen[name] = i
            continue
    # Match function definitions: 'function name {' or 'name() {'
    m = re.match(r'(?:function\s+)?(\w[\w_-]*)\s*\(\)\s*\{', line)
    if m:
        name = m.group(1)
        functions_seen[name] = i
        continue

# Second pass: keep only lines that are not stale aliases/functions
keep = [True] * len(lines)
for name, idx in aliases_seen.items():
    # Mark all earlier occurrences for deletion
    for j in range(idx):
        if j in aliases_seen.values() and lines[j].strip().startswith(('alias', name)):
            keep[j] = False
    # Also mark bare assignments earlier
    for j in range(idx):
        if re.match(fr'^{name}=', lines[j].strip()):
            keep[j] = False

for name, idx in functions_seen.items():
    for j in range(idx):
        if re.match(fr'(function\s+)?{name}\s*\(\)', lines[j].strip()):
            keep[j] = False

# Write backup and filtered file
with open(backup, 'w') as f:
    f.writelines(lines)

with open(input_file, 'w') as f:
    for i, line in enumerate(lines):
        if keep[i]:
            f.write(line)

print("✅ .zshrc deduplicated. Original saved to .zshrc.backup")