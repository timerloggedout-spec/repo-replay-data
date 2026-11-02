#!/usr/bin/env python3
"""
scan_databases.py – Find all possible data stores that could contain code blocks.
Inspects SQLite databases, JSON/JSONL files, and conv_explorer internals.
"""
import os, json, re, sqlite3, sys
from pathlib import Path

HOME = Path.home()
PROJECTS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout", "deepseek_harvest_work", "synthegration_exports"
]
BLOAT_PARTS = {"node_modules","__pycache__",".cache",".git","dist","codex/blobs","browser-data"}

def is_bloat(parts):
    return any(p in BLOAT_PARTS for p in parts)

# --- 1. Inspect export.json from deepseek_harvest_work ---
harvest_export = HOME / "deepseek_harvest_work/export.json"
if harvest_export.exists():
    print("=== deepseek_harvest_work/export.json ===")
    try:
        data = json.loads(harvest_export.read_text())
        if isinstance(data, list):
            print(f"List with {len(data)} items")
            if len(data) > 0:
                first = data[0]
                if isinstance(first, dict):
                    print("First item keys:", list(first.keys()))
                    # Look for messages/mapping/content
                    for key in ['messages','mapping','content','text','data']:
                        if key in first:
                            val = first[key]
                            print(f"  {key}: {str(val)[:200]}")
                else:
                    print("First item type:", type(first))
        elif isinstance(data, dict):
            print("Dict keys:", list(data.keys()))
    except Exception as e:
        print("Error:", e)

# --- 2. Find all SQLite databases ---
print("\n=== SQLite databases ===")
for proj in PROJECTS:
    proj_dir = HOME / proj
    if not proj_dir.is_dir(): continue
    for db_path in proj_dir.rglob("*.db"):
        if is_bloat(db_path.parts): continue
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"{db_path}: {tables}")
            # If there's a 'messages' or 'conversations' table, dump schema
            for tbl in tables:
                if any(kw in tbl.lower() for kw in ['message','convers','session','chat']):
                    cursor.execute(f"PRAGMA table_info({tbl});")
                    cols = cursor.fetchall()
                    print(f"  {tbl} columns: {[c[1] for c in cols]}")
                    cursor.execute(f"SELECT * FROM {tbl} LIMIT 1;")
                    row = cursor.fetchone()
                    if row:
                        print(f"  Sample row: {row}")
            conn.close()
        except Exception as e:
            print(f"{db_path}: {e}")

# --- 3. Scan for JSON/JSONL files with code blocks ---
print("\n=== JSON/JSONL files with code blocks ===")
for proj in PROJECTS:
    proj_dir = HOME / proj
    if not proj_dir.is_dir(): continue
    for fpath in proj_dir.rglob("*.json"):
        if is_bloat(fpath.parts): continue
        try:
            if fpath.stat().st_size > 10_000_000: continue  # skip huge files
            text = fpath.read_text()
            # Check for code fences
            blocks = re.findall(r"```(?:\w+)?\n(.*?)\n```", text, re.DOTALL)
            if blocks:
                print(f"  {fpath}: {len(blocks)} code blocks")
                # print first block snippet
                print(f"    {blocks[0][:100]}")
        except: pass
    # Also .jsonl
    for fpath in proj_dir.rglob("*.jsonl"):
        if is_bloat(fpath.parts): continue
        try:
            lines = fpath.read_text().splitlines()
            blocks_found = 0
            for line in lines:
                if re.search(r"```", line):
                    blocks_found += 1
            if blocks_found > 0:
                print(f"  {fpath}: {blocks_found} lines with code fences")
        except: pass

# --- 4. Explore conv_explorer module directly ---
print("\n=== conv_explorer module ===")
try:
    import conv_explorer
    print("Available in conv_explorer:")
    for name in dir(conv_explorer):
        obj = getattr(conv_explorer, name)
        if callable(obj) and not name.startswith('_'):
            try:
                import inspect
                sig = inspect.signature(obj)
                print(f"  {name}{sig}")
            except:
                print(f"  {name}()")
    # Try to list sessions if possible
    if hasattr(conv_explorer, 'list_sessions'):
        try:
            sessions = conv_explorer.list_sessions()
            print(f"list_sessions returned {len(sessions)} items")
            if sessions:
                print("  Sample:", sessions[0] if isinstance(sessions[0], str) else list(sessions[0].keys()))
        except Exception as e:
            print(f"list_sessions failed: {e}")
except Exception as e:
    print(f"Import failed: {e}")

# --- 5. Explore synthegration_index module ---
print("\n=== synthegration_index module ===")
try:
    import synthegration_index
    for name in dir(synthegration_index):
        if not name.startswith('_'):
            obj = getattr(synthegration_index, name)
            if callable(obj):
                try:
                    import inspect
                    sig = inspect.signature(obj)
                    print(f"  {name}{sig}")
                except:
                    print(f"  {name}()")
    # Check for any index files it uses
    if hasattr(synthegration_index, 'INDEX_PATH') or hasattr(synthegration_index, 'DB_PATH'):
        for attr in ['INDEX_PATH', 'DB_PATH', 'DATA_DIR']:
            val = getattr(synthegration_index, attr, None)
            if val:
                print(f"  {attr}: {val}")
except Exception as e:
    print(f"Import failed: {e}")