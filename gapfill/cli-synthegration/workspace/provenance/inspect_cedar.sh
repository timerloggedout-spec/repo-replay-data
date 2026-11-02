#!/bin/bash
echo "=== CEDARscript discovery ==="

# 1. Check for any CEDARscript executables in standard Termux paths
echo ""
echo "Executables in PATH:"
which cedar 2>/dev/null || echo "  'cedar' not in PATH"
which cedarscript 2>/dev/null || echo "  'cedarscript' not in PATH"
ls $PREFIX/bin/cedar* 2>/dev/null || echo "  No cedar* in $PREFIX/bin"

# 2. Python package location and attributes
echo ""
echo "Python package:"
python3 -c "
import cedarscript_editor, os, inspect
pkg_dir = os.path.dirname(cedarscript_editor.__file__)
print('Location:', pkg_dir)
print('Contents:')
for name in sorted(os.listdir(pkg_dir)):
    print(' ', name)
print()
print('Module attributes:')
for attr in sorted(dir(cedarscript_editor)):
    if not attr.startswith('_'):
        obj = getattr(cedarscript_editor, attr)
        if callable(obj):
            try: sig = inspect.signature(obj)
            except: sig = '()'
            print(f'  {attr}{sig}')
        else:
            print(f'  {attr} = {obj!r}')
"

# 3. Quick test of the CEDARScriptEditor class (if present)
echo ""
echo "Quick functional test:"
python3 -c "
from cedarscript_editor import CEDARScriptEditor
editor = CEDARScriptEditor(root_path='.')
print('CEDARScriptEditor created, root:', editor.root_path)
# Try to list methods
methods = [m for m in dir(editor) if not m.startswith('_') and callable(getattr(editor, m))]
print('Methods:', methods)
"