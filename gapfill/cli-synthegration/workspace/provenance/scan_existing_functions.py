#!/usr/bin/env python3
"""Scan all projects for code-block related functions, exports, and databases."""
import subprocess, json, os
from pathlib import Path

HOME = Path.home()
PROJECTS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]

# 1. Find Python functions with 'code' or 'block' or 'export' in name
print("=== Python functions related to code blocks / exports ===")
for proj in PROJECTS:
    proj_dir = HOME / proj
    if not proj_dir.is_dir(): continue
    # Use ast-grep to find function definitions
    try:
        result = subprocess.run(
            ["ast-grep", "-p", "def $_FUNC", "--json", "--no-ignore"],
            cwd=proj_dir, capture_output=True, text=True
        )
        if result.stdout:
            for line in result.stdout.splitlines():
                if any(kw in line.lower() for kw in ['code','block','export','provenance','blob','fragment']):
                    print(f"  {proj}: {line.strip()}")
    except: pass

# 2. Search for JSON export directories
print("\n=== Export/block directories ===")
for proj in PROJECTS + ["synthegration_exports", "deepseek_harvest_work"]:
    proj_dir = HOME / proj
    if not proj_dir.is_dir(): continue
    for d in proj_dir.glob("**/export*"):
        if d.is_dir():
            file_count = len(list(d.rglob("*.json")))
            print(f"  {d} ({file_count} JSON files)")
    for d in proj_dir.glob("**/codex*"):
        if d.is_dir():
            blob_count = len(list(d.rglob("*.blob")))
            print(f"  {d} ({blob_count} blob files)")

# 3. Search for any .json file with 'mapping' or 'messages' top-level keys (conversation data) outside known dirs
print("\n=== Conversation JSON files in project trees ===")
for proj in PROJECTS:
    proj_dir = HOME / proj
    for f in proj_dir.rglob("*.json"):
        if any(p in f.parts for p in ["node_modules","__pycache__",".cache",".git","dist","codex/blobs","browser-data"]):
            continue
        try:
            if f.stat().st_size > 100000: continue
            with open(f) as fh:
                data = json.load(fh)
            if isinstance(data, dict) and ('mapping' in data or 'messages' in data):
                print(f"  {f}")
        except: pass

# 4. Print known module structures
print("\n=== Modules in cli-synthegration ===")
import cli_synthegration  # if possible
for name in dir(cli_synthegration):
    if not name.startswith('_'):
        print(f"  {name}")