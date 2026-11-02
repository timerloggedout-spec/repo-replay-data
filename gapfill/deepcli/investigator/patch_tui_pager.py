#!/usr/bin/env python3
"""Patch tui.py: replace fixed print of tree with Rich pager for long output."""
import shutil

TUI = '/data/data/com.termux/files/home/deepcli-tui/tui.py'
with open(TUI, 'r') as f:
    content = f.read()

# Find the line where we currently print the header: console.print(header)
# We'll replace it with a pager call if the tree is tall.
old = '''                # Print static layout                                      console.clear()                                            console.print(header)                                      console.print(status)                                      console.print(fork_info)'''
new = '''                # Print static layout (use pager if tree is longer than terminal)
                console.clear()
                tree_height = len(tree_str.splitlines())
                term_height = shutil.get_terminal_size().lines
                if tree_height > term_height - 6:  # leave room for status + fork_info
                    with console.pager():
                        console.print(header)
                        console.print(status)
                        console.print(fork_info)
                else:
                    console.print(header)
                    console.print(status)
                    console.print(fork_info)'''

# Also need to import shutil at top
if 'import shutil' not in content:
    import_line = 'import sys, os, json, time, re\n'
    content = content.replace(import_line, import_line + 'import shutil\n')

content = content.replace(old, new)

with open(TUI, 'w') as f:
    f.write(content)

print('✅ TUI pager patched – long trees will now scroll in Rich’s pager.')