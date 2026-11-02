#!/usr/bin/env python3
"""
fragment_provenance.py – Match code blocks to file fragments (or whole files).
Computes true iteration acceleration using message‑to‑message intervals.
"""
import json, sys, re, hashlib, statistics, difflib
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
MAX_DELAY = 12 * 3600       # 12 hours
SIMILARITY = 0.5            # looser match for whole files
MIN_FRAGMENT_LINES = 4

SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
# Exact directory names to skip (not substrings)
BLOAT_NAMES = {"node_modules","__pycache__",".cache",".git","dist",
               "codex","blobs","browser-data",".blob","logs","tmp",
               "target","release",".fingerprint","deps","build"}

def is_bloat(parts):
    # Skip if any part exactly matches a bloat name
    return any(p in BLOAT_NAMES for p in parts)

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

# --- 1. Load source files (whole file) ---
file_info = {}
scanned = 0
for base in SOURCE_DIRS:
    for fp in (HOME / base).rglob('*.py'):
        scanned += 1
        if fp.is_file() and not is_bloat(fp.parts):
            if fp.stat().st_size > 1_000_000: continue
            try:
                content = fp.read_text()
                rel = str(fp.relative_to(HOME))
                file_info[rel] = {'mtime': fp.stat().st_mtime, 'content': content}
            except: pass
print(f"Scanned {scanned} .py files, loaded {len(file_info)} clean source files.")

# --- 2. Extract code blocks from 2026 exports ---
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
                    'hash': sha256(block.strip())
                })
print(f"Code blocks: {len(code_blocks)}")

# --- 3. Match whole files with similarity ---
file_versions = {}
for fname, finfo in file_info.items():
    versions = []
    # Try exact/norm hash first (fast)
    file_hash = sha256(finfo['content'])
    file_norm_hash = sha256('\n'.join(line.rstrip() for line in finfo['content'].splitlines()))
    for cb in code_blocks:
        if cb['timestamp_utc'] is None: continue
        delay = finfo['mtime'] - cb['timestamp_utc']
        if 0 <= delay <= MAX_DELAY:
            matched = False
            sim = 0.0
            # Fast path: exact or normalized hash
            if cb['hash'] == file_hash or sha256('\n'.join(line.rstrip() for line in cb['text'].splitlines())) == file_norm_hash:
                matched = True
                sim = 1.0
            else:
                # Quick line count filter
                fl = len(finfo['content'].splitlines())
                bl = len(cb['text'].splitlines())
                if max(fl, bl) / (min(fl, bl) + 1) <= 3:
                    sim = difflib.SequenceMatcher(None, finfo['content'], cb['text']).ratio()
                    matched = sim >= SIMILARITY
            if matched:
                versions.append({
                    'session': cb['session'], 'node_id': cb['node_id'],
                    'block_idx': cb['block_idx'],
                    'timestamp_utc': datetime.fromtimestamp(cb['timestamp_utc'], tz=timezone.utc).isoformat(),
                    'delay_s': delay, 'similarity': round(sim, 3),
                    'snippet': cb['text'][:200]
                })
    if versions:
        versions.sort(key=lambda v: v['delay_s'])
        file_versions[fname] = versions

with open(OUT / "fragment_provenance.json", 'w') as f:
    json.dump(file_versions, f, indent=2)
print(f"Files with provenance: {len(file_versions)}")

# --- 4. True iteration speedup (message‑to‑message intervals) ---
session_intervals = []
for fname, versions in file_versions.items():
    by_session = {}
    for v in versions:
        by_session.setdefault(v['session'], []).append(v)
    for sess_versions in by_session.values():
        sess_versions.sort(key=lambda v: v['timestamp_utc'])
        for i in range(1, len(sess_versions)):
            t0 = datetime.fromisoformat(sess_versions[i-1]['timestamp_utc']).timestamp()
            t1 = datetime.fromisoformat(sess_versions[i]['timestamp_utc']).timestamp()
            interval = t1 - t0
            if interval > 0:
                session_intervals.append(interval)

if session_intervals:
    median_int = statistics.median(session_intervals)
    print(f"Message‑to‑message intervals (n={len(session_intervals)}):")
    print(f"  Median interval: {median_int:.0f}s")
    print(f"  Min: {min(session_intervals):.0f}s, Max: {max(session_intervals):.0f}s")
    stats = {
        'files_with_provenance': len(file_versions),
        'total_versions': sum(len(v) for v in file_versions.values()),
        'message_interval_median_s': median_int,
        'message_interval_min_s': min(session_intervals),
        'message_interval_max_s': max(session_intervals),
        'interpretation': f"Median {median_int:.0f}s between successive code blocks in the same session."
    }
    with open(OUT / "true_iteration_stats.json", 'w') as f:
        json.dump(stats, f, indent=2)
    print("Stats saved to true_iteration_stats.json")
else:
    print("No multi‑version files in the same session — try lowering SIMILARITY further.")