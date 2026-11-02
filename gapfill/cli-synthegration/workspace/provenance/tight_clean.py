#!/usr/bin/env python3
"""Fast tight‑window provenance – only clean source files, no similarity."""
import json, hashlib, re, statistics, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
MAX_DELAY = 2 * 3600

SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT_PARTS = {
    "node_modules","__pycache__",".cache",".git","dist",
    "codex","blobs","browser-data",".blob","logs","tmp",
    "target","release",".fingerprint","deps","build"
}

def sha256(text): return hashlib.sha256(text.encode()).hexdigest()
def normalize(text): return '\n'.join(line.rstrip() for line in text.splitlines())
def is_bloat(parts): return any(p in BLOAT_PARTS for p in parts)

# --- File info ---
file_info = {}
for base in SOURCE_DIRS:
    for fp in (HOME / base).rglob('*'):
        if fp.is_file() and not is_bloat(fp.parts):
            if fp.stat().st_size > 1_000_000: continue
            try:
                content = fp.read_text()
                file_info[str(fp.relative_to(HOME))] = {
                    'mtime': fp.stat().st_mtime,
                    'hash': sha256(content),
                    'norm_hash': sha256(normalize(content))
                }
            except: pass
print(f"Clean source files: {len(file_info)}")

# --- Code blocks (2026) ---
code_blocks = []
for cf in [
    HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-26/conversations.json",
    HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-17/conversations.json",
]:
    if not cf.exists(): continue
    with open(cf) as f:
        data = json.load(f)
    for conv in (data if isinstance(data, list) else [data]):
        sid = conv.get('id') or conv.get('title','?')
        for nid, node in conv.get('mapping',{}).items():
            msg = node.get('message')
            if not isinstance(msg, dict): continue
            ts = msg.get('inserted_at')
            utc_ts = None
            if ts:
                try: utc_ts = datetime.fromisoformat(str(ts).replace('Z','+00:00')).timestamp()
                except: pass
            content = ''
            for frag in msg.get('fragments', []):
                if isinstance(frag, dict): content += frag.get('content','') + '\n'
            for bi, block in enumerate(re.findall(r"```(?:\w+)?\n(.*?)\n```", content, re.DOTALL)):
                code_blocks.append({
                    'session': str(sid), 'node_id': nid, 'block_idx': bi,
                    'timestamp_utc': utc_ts, 'text': block,
                    'hash': sha256(block.strip()), 'norm_hash': sha256(normalize(block))
                })
print(f"Code blocks: {len(code_blocks)}")

# --- Match ---
results = {}
for fname, finfo in file_info.items():
    best = None
    for cb in code_blocks:
        if cb['timestamp_utc'] is None: continue
        delay = finfo['mtime'] - cb['timestamp_utc']
        if 0 <= delay <= MAX_DELAY:
            if cb['hash'] == finfo['hash'] or cb['norm_hash'] == finfo['norm_hash']:
                if best is None or delay < best[1]:
                    best = (cb, delay)
    if best:
        cb, delay = best
        results[fname] = {
            'session': cb['session'],
            'delay_seconds': delay,
            'snippet': cb['text'][:200]
        }

with open(OUT / "tight_clean.json", 'w') as f:
    json.dump(results, f, indent=2)

delays = [v['delay_seconds'] for v in results.values()]
print(f"Matched files: {len(results)}")
if delays:
    print(f"Median delay: {statistics.median(delays):.0f}s")
    print(f"Delay range: {min(delays):.0f}s – {max(delays):.0f}s")