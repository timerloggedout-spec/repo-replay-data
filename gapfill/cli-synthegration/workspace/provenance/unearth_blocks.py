#!/usr/bin/env python3
"""
unearth_blocks.py – Unzip DeepSeek exports and scan for code blocks.
Also explore code_harvest directory.
"""
import json, re, zipfile, os
from pathlib import Path

HOME = Path.home()

# --- 1. DeepSeek export zips ---
export_dir = HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports"
for zip_path in sorted(export_dir.glob("*.zip")):
    print(f"\n=== {zip_path.name} ===")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if 'conversations' in name and name.endswith('.json'):
                    # Stream the file, searching for code blocks
                    print(f"  Scanning {name} ({zf.getinfo(name).file_size} bytes)...")
                    with zf.open(name) as f:
                        # Process as text stream line by line to find code fences
                        code_blocks_found = 0
                        sample_blocks = []
                        in_block = False
                        current_block = []
                        for line in f:
                            try:
                                decoded = line.decode('utf-8')
                            except:
                                continue
                            if decoded.startswith("```") and not in_block:
                                in_block = True
                                current_block = [decoded]
                            elif decoded.startswith("```") and in_block:
                                # End of block
                                current_block.append(decoded)
                                code_blocks_found += 1
                                if len(sample_blocks) < 5:
                                    sample_blocks.append(''.join(current_block))
                                current_block = []
                                in_block = False
                            elif in_block:
                                current_block.append(decoded)
                        print(f"    Code blocks found: {code_blocks_found}")
                        for sb in sample_blocks:
                            print(f"    Sample: {sb[:150]}...")
    except Exception as e:
        print(f"  Error: {e}")

# --- 2. code_harvest directory ---
code_harvest_dir = HOME / "deepseek_harvest_work/code_harvest"
if code_harvest_dir.is_dir():
    print(f"\n=== {code_harvest_dir} contents ===")
    for f in sorted(code_harvest_dir.rglob("*")):
        if f.is_file():
            size = f.stat().st_size
            print(f"  {f.relative_to(code_harvest_dir)} ({size} bytes)")
            # If small, print content head
            if size < 2000:
                try:
                    content = f.read_text()
                    print(f"    {content[:200]}")
                except: pass
            elif f.suffix == '.json':
                # peek first 500 bytes
                try:
                    with open(f, 'r') as fh:
                        print(f"    {fh.read(300)}")
                except: pass

# --- 3. harvest.py functions ---
harvest_py = HOME / "deepseek_harvest_work/harvest.py"
if harvest_py.exists():
    print(f"\n=== harvest.py functions ===")
    try:
        text = harvest_py.read_text()
        # Find all def lines
        for line in text.splitlines():
            if line.strip().startswith('def '):
                print(f"  {line.strip()}")
    except: pass