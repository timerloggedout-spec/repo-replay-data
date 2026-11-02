#!/usr/bin/env python3
"""Patch tui.py to limit tree children, preventing freezes on long sessions."""
import re, sys

TUI_PATH = '/data/data/com.termux/files/home/deepcli-tui/tui.py'

with open(TUI_PATH, 'r') as f:
    content = f.read()

# 1. Add MAX_CHILDREN constant after the existing max_depth default
OLD = 'def build_tree_str(messages, selected_parent_id=None, max_depth=8, content_width=50):'
NEW = '''MAX_CHILDREN = 80

def build_tree_str(messages, selected_parent_id=None, max_depth=8, content_width=50):'''
content = content.replace(OLD, NEW)

# 2. Modify _render to limit children and show count
# We need to insert a children limit inside the for loop.
# Look for: for i, child in enumerate(children):
# and replace the block.
pattern = r'(for i, child in enumerate\(children\):\s+last = \(i == len\(children\)-1\)\s+new_prefix = prefix \+ \("   " if is_last else "│  "\)\s+_render\(child, new_prefix, last, depth\+1\))'

replacement = '''for i, child in enumerate(children[:MAX_CHILDREN]):
                    last = (i == min(len(children), MAX_CHILDREN)-1)
                    new_prefix = prefix + ("   " if is_last else "│  ")
                    _render(child, new_prefix, last, depth+1)
                if len(children) > MAX_CHILDREN:
                    lines.append(f"{prefix}└── [yellow](... and {len(children)-MAX_CHILDREN} more messages collapsed)[/]")'''

# The original indentation is 24 spaces, so we need to preserve that.
# We'll use a regex that captures the whole block with flexible whitespace.
OLD_FOR_BLOCK = re.compile(
    r'for i, child in enumerate\(children\):\s+'
    r'last = \(i == len\(children\)-1\)\s+'
    r'new_prefix = prefix \+ \("   " if is_last else "│  "\)\s+'
    r'_render\(child, new_prefix, last, depth\+1\)'
)
if OLD_FOR_BLOCK.search(content):
    content = OLD_FOR_BLOCK.sub(replacement, content)
else:
    print("⚠️  Could not locate the children loop; manual edit may be required.", file=sys.stderr)

with open(TUI_PATH, 'w') as f:
    f.write(content)

print("✅ TUI tree patched with children limit.")