#!/usr/bin/env python3
"""
fix_timestamps.py – Diagnose timestamp offsets, then re‑match files to 2026 sessions
using a tight time window, regardless of exact hash match.
"""
import json, sys, re, hashlib, statistics, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"

# ========== 1. Timestamp sanity ==========
print("=== Timestamp Sanity Check ===")
now_utc = datetime.now(timezone.utc)
print(f"Current UTC time: {now_utc.isoformat()}")
test_file = OUT / "fix_timestamps.py"
if test_file.exists():
    mtime = test_file.stat().st_mtime
    mtime_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    print(f"File mtime (should be now): {mtime_dt.isoformat()}")
    print(f"Difference: {(now_utc - mtime_dt).total_seconds():.0f} seconds ago")

# Load a few conversation timestamps
conv_file = HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-26/conversations.json"
if conv_file.exists():
    with open(conv_file) as f:
        data = json.load(f)
    conversations = data if isinstance(data, list) else [data]
    # Find latest and earliest message timestamps
    all_ts = []
    for conv in conversations:
        for nid, node in conv.get('mapping', {}).items():
            msg = node.get('message')
            if not isinstance(msg, dict): continue
            ts = msg.get('inserted_at')
            if ts:
                try:
                    dt = datetime.fromisoformat(str(ts).replace('Z','+00:00'))
                    all_ts.append(dt)
                except: pass
    if all_ts:
        print(f"Conversation messages range: {min(all_ts).isoformat()} to {max(all_ts).isoformat()}")
        print(f"Latest message age: {(now_utc - max(all_ts)).total_seconds():.0f} seconds ago")

# ========== 2. Re‑match with tight time window (2026 only) ==========
print("\n=== Re‑matching with 2‑hour window (2026 sessions) ===")
MAX_DELAY = 2 * 3600  # 2 hours

# Load file mtimes (only for files in our projects)
SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT = {"node_modules","__pycache__",".cache",".git","dist","codex/blobs","browser-data",".blob","logs","tmp"}
file_mtimes = {}
for base in SOURCE_DIRS:
    for fp in (HOME / base).rglob('*'):
        if fp.is_file() and not any(p in BLOAT for p in fp.parts):
            file_mtimes[str(fp.relative_to(HOME))] = fp.stat().st_mtime
print(f"Source files: {len(file_mtimes)}")

# Extract all code blocks from 2026 exports (same as before, but store full text too)
def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()
def normalize(text):
    return '\n'.join(line.rstrip() for line in text.splitlines())

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
                try:
                    utc_ts = datetime.fromisoformat(str(ts).replace('Z','+00:00')).timestamp()
                except: pass
            content = ''
            for frag in msg.get('fragments', []):
                if isinstance(frag, dict):
                    content += frag.get('content','') + '\n'
            for bi, block in enumerate(re.findall(r"```(?:\w+)?\n(.*?)\n```", content, re.DOTALL)):
                code_blocks.append({
                    'session': str(sid),
                    'node_id': nid,
                    'block_idx': bi,
                    'timestamp_utc': utc_ts,
                    'text': block,
                    'hash': sha256(block.strip()),
                    'norm_hash': sha256(normalize(block))
                })
print(f"Code blocks from 2026 sessions: {len(code_blocks)}")

# Match: for each file, find all code blocks with timestamp <= mtime and within MAX_DELAY
results = []  # (fname, session, delay_s, snippet)
for fname, mtime in file_mtimes.items():
    best = None
    for cb in code_blocks:
        if cb['timestamp_utc'] is None: continue
        if cb['timestamp_utc'] <= mtime:
            delay = mtime - cb['timestamp_utc']
            if delay <= MAX_DELAY:
                if best is None or delay < best[1]:
                    # Also check if the content is somewhat similar? 
                    # We'll just use time for now, but prefer exact/norm hash if possible
                    best = (cb, delay)
    if best:
        cb, delay = best
        results.append((fname, cb['session'], delay, cb['text'][:100]))

results.sort(key=lambda r: r[2])
delays = [r[2] for r in results]
print(f"Files matched within 2h: {len(results)}")
if delays:
    print(f"Delay range: {min(delays):.0f}s – {max(delays):.0f}s")
    print(f"Median copy‑paste delay: {statistics.median(delays):.0f}s")
    # Print sample
    for fname, sess, delay, snippet in results[:10]:
        print(f"  {fname}: {delay:.0f}s, {sess[:30]}...")
    
    # Save
    prov = {}
    for fname, sess, delay, snip in results:
        prov[fname] = {
            'session': sess,
            'delay_seconds': delay,
            'snippet': snip
        }
    with open(OUT / "tight_provenance.json", 'w') as f:
        json.dump(prov, f, indent=2)
    print("Saved to tight_provenance.json")
else:
    print("No matches within 2 hours. The 2026 sessions might be older than the files.")
    # Let's check: what's the latest message timestamp vs oldest file mtime?
    if code_blocks:
        latest_msg = max(cb['timestamp_utc'] for cb in code_blocks if cb['timestamp_utc'])
        oldest_file = min(file_mtimes.values())
        print(f"Latest message: {datetime.fromtimestamp(latest_msg, tz=timezone.utc).isoformat()}")
        print(f"Oldest file:    {datetime.fromtimestamp(oldest_file, tz=timezone.utc).isoformat()}")
        print(f"Gap: {(oldest_file - latest_msg)/3600:.1f} hours")