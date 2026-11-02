#!/usr/bin/env python3
"""
investigate_harvest.py – Examine SQLite DBs and DeepSeek exports for code blocks.
"""
import os, json, sqlite3, re, zipfile
from pathlib import Path

HOME = Path.home()

# --- 1. SQLite graph databases ---
db_paths = [
    HOME / "termux-multi-agent/local_repo.db",
    HOME / "synthegration-cli/local_repo.db"
]
for db_path in db_paths:
    if not db_path.exists():
        print(f"Not found: {db_path}")
        continue
    print(f"\n=== {db_path} ===")
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    # get all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]
    print("Tables:", tables)
    for tbl in tables:
        cur.execute(f"PRAGMA table_info({tbl})")
        cols = [c[1] for c in cur.fetchall()]
        print(f"\n{tbl} columns: {cols}")
        cur.execute(f"SELECT * FROM {tbl} LIMIT 3")
        rows = cur.fetchall()
        for i, row in enumerate(rows):
            # print each row succinctly
            print(f" Row {i}: {row}")
        # If table looks like it stores code blocks, do more
        if 'content' in cols or 'code' in cols or 'text' in cols:
            cur.execute(f"SELECT count(*) FROM {tbl}")
            count = cur.fetchone()[0]
            print(f"  Total rows: {count}")
    conn.close()

# --- 2. DeepSeek export directory ---
export_dir = HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports"
if export_dir.is_dir():
    print("\n=== DeepSeek exports directory ===")
    for f in sorted(export_dir.iterdir()):
        print(f"  {f.name} ({'dir' if f.is_dir() else f'{f.stat().st_size} bytes'})")
    # If there are zip files, list their contents
    for f in export_dir.glob("*.zip"):
        print(f"\nContents of {f.name}:")
        try:
            with zipfile.ZipFile(f, 'r') as zf:
                for info in zf.infolist():
                    print(f"  {info.filename} ({info.file_size} bytes)")
        except Exception as e:
            print(f"  Error: {e}")
    # If there are JSON files, sample them for code blocks
    for f in export_dir.glob("*.json"):
        try:
            with open(f, 'r') as fh:
                data = json.load(fh)
            blocks = re.findall(r"```(?:\w+)?\n(.*?)\n```", str(data), re.DOTALL)
            if blocks:
                print(f"\n{f.name}: {len(blocks)} code blocks")
                for b in blocks[:2]:
                    print(f"  {b[:100]}...")
            else:
                print(f"\n{f.name}: no fenced code blocks, type: {type(data)}")
        except Exception as e:
            print(f"{f.name}: {e}")
    # If there are subdirectories like deepseek_data-2026-05-26, scan them
    for sub in export_dir.glob("deepseek_data-*"):
        if sub.is_dir():
            json_files = list(sub.glob("*.json"))
            print(f"\n{sub.name}: {len(json_files)} JSON files")
            for jf in json_files[:3]:
                try:
                    data = json.loads(jf.read_text())
                    blocks = re.findall(r"```(?:\w+)?\n(.*?)\n```", str(data), re.DOTALL)
                    print(f"  {jf.name}: {len(blocks)} code blocks")
                except:
                    pass
else:
    print(f"\nExport directory not found: {export_dir}")

# --- 3. Check harvest work for any other file types ---
hw = HOME / "deepseek_harvest_work"
if hw.is_dir():
    print("\n=== deepseek_harvest_work files ===")
    for f in sorted(hw.iterdir()):
        print(f"  {f.name} ({'dir' if f.is_dir() else f'{f.stat().st_size} bytes'})")
    # If there's an index or pickle file, report it
    for f in hw.glob("*"):
        if f.suffix in ['.pkl', '.pickle', '.index', '.db', '.sqlite']:
            print(f"Found potential index: {f}")