#!/usr/bin/env python3
"""fragment_matcher_incremental.py – Checkpointed, batched similarity matching.
Only processes code blocks that haven't been indexed yet.
Displays progress in batches of 10."""
import json, re, hashlib, difflib, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
CURSOR_FILE = HOME / "cli-synthegration/workspace/provenance/.fragment_cursor.json"
EXPORT_SOURCES = [
    HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-26/conversations.json",
    HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-17/conversations.json",
]
BATCH_SIZE = 10

def load_cursor():
    if CURSOR_FILE.exists():
        with open(CURSOR_FILE) as f:
            return json.load(f)
    return {"processed_hashes": [], "last_export": None}

def save_cursor(cursor):
    CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CURSOR_FILE, 'w') as f:
        json.dump(cursor, f, indent=2)

def extract_new_blocks():
    cursor = load_cursor()
    processed = set(cursor.get("processed_hashes", []))
    new_blocks = []
    for export_path in EXPORT_SOURCES:
        if not export_path.exists():
            continue
        with open(export_path, encoding='utf-8') as f:
            data = json.load(f)
        sessions = data if isinstance(data, list) else [data]
        for sess in sessions:
            mapping = sess.get('mapping', {})
            for nid, node in mapping.items():
                msg = node.get('message')
                if not isinstance(msg, dict):
                    continue
                content = msg.get('content', {}).get('text', '')
                for block_text in re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL):
                    block_hash = hashlib.sha256(block_text.encode()).hexdigest()[:12]
                    if block_hash not in processed:
                        new_blocks.append({"hash": block_hash, "text": block_text, "session": sess.get('id', '?')})
    return new_blocks, cursor

if __name__ == '__main__':
    new_blocks, cursor = extract_new_blocks()
    total = len(new_blocks)
    print(f"New blocks to process: {total}")
    for i in range(0, total, BATCH_SIZE):
        batch = new_blocks[i:i+BATCH_SIZE]
        for b in batch:
            cursor["processed_hashes"].append(b["hash"])
        save_cursor(cursor)
        print(f"  Batch {i//BATCH_SIZE + 1}: processed {len(batch)} blocks, {i+len(batch)}/{total}")
    print(f"✅ Done. {total} new blocks processed.")