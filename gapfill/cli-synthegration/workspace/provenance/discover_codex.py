#!/usr/bin/env python3
"""
discover_codex.py – Explore codex blobs and find actual code‑block sources.
"""
import os, json, subprocess, hashlib, re
from pathlib import Path

HOME = Path.home()
CODEX_DIR = HOME / "cli-synthegration/codex/blobs"
EXPORT_DIR = HOME / "synthegration_exports"
HARVEST_DIR = HOME / "deepseek_harvest_work"

print("=== 1. Codex blob store ===")
if CODEX_DIR.is_dir():
    blobs = sorted(CODEX_DIR.glob("*.blob"))
    print(f"Found {len(blobs)} blobs")
    # Sample first blob – read bytes, try to decode as text
    for blob in blobs[:3]:
        try:
            raw = blob.read_bytes()
            print(f"\nBlob: {blob.name} ({len(raw)} bytes)")
            # Try to detect JSON
            try:
                data = json.loads(raw)
                print("  JSON structure. Keys:", list(data.keys()))
                if 'messages' in data:
                    msgs = data['messages']
                    print(f"  Messages: {len(msgs)}")
                    for msg in msgs[:2]:
                        if isinstance(msg, dict):
                            print(f"    Message keys: {list(msg.keys())}")
                            content = msg.get('content','')[:200]
                            print(f"    Content: {content}")
                elif 'mapping' in data:
                    print(f"  Mapping with {len(data['mapping'])} nodes")
            except:
                # Maybe text with code blocks
                text = raw.decode('utf-8', errors='ignore')
                blocks = re.findall(r"```(?:\w+)?\n(.*?)\n```", text, re.DOTALL)
                print(f"  Plain text, code blocks found: {len(blocks)}")
                for b in blocks[:2]:
                    print(f"    {b[:100]}...")
        except Exception as e:
            print(f"  Error reading: {e}")
else:
    print("No codex/blobs directory")

print("\n=== 2. Export directories ===")
for name, d in [("synthegration_exports", EXPORT_DIR), ("deepseek_harvest_work", HARVEST_DIR)]:
    if d.is_dir():
        files = sorted(d.glob("*.json"))
        print(f"{name}: {len(files)} JSON files")
        for f in files[:5]:
            try:
                data = json.loads(f.read_text())
                keys = list(data.keys()) if isinstance(data, dict) else "list"
                print(f"  {f.name}: {keys}")
            except: pass
    else:
        print(f"{name}: not found")

print("\n=== 3. synthegration codex-index ===")
# Run the CLI command to see if it works
subprocess.run("synthegration codex-index", shell=True, check=False)

print("\n=== 4. Search codex for a known code snippet ===")
# We'll search for 'sha256' which appears in our scripts
subprocess.run("synthegration codex-search sha256 | head -20", shell=True, check=False)

print("\n=== 5. Offline search for 'provenance' in exports ===")
if EXPORT_DIR.is_dir():
    subprocess.run(f"synthegration offline-search {EXPORT_DIR} provenance | head -20", shell=True, check=False)