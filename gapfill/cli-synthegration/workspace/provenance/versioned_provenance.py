#!/usr/bin/env python3
"""
versioned_provenance.py – Multi‑version file provenance from 2026 DeepSeek sessions.
Tracks all code‑block → file matches, not just the best one.
"""
import json, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
INDEX_FILE = OUT / "hash_index.json"
VERSIONED_PROV = OUT / "versioned_provenance.json"
VERSION_STATS = OUT / "version_stats.json"

# 2026 export files (primary source)
EXPORT_2026 = [
    HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-26/conversations.json",
    HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-17/conversations.json",
]

# Load hash index
with open(INDEX_FILE) as f:
    cache = json.load(f)
exact_hashes = set(cache.get('exact', {}).keys())
norm_hashes  = set(cache.get('norm', {}).keys())

# --- Extract all code blocks from 2026 sessions ---
print("Extracting code blocks from 2026 sessions...")
code_blocks = []  # list of {hash, session, timestamp_utc, snippet, ...}

for conv_file in EXPORT_2026:
    if not conv_file.exists():
        print(f"  Not found: {conv_file}")
        continue
    print(f"  Loading {conv_file.name}...")
    try:
        with open(conv_file) as f:
            data = json.load(f)
    except Exception as e:
        print(f"  Failed: {e}")
        continue

    conversations = data if isinstance(data, list) else [data]
    for conv in conversations:
        session_id = conv.get('id') or conv.get('title', 'unknown')
        mapping = conv.get('mapping', {})
        if not mapping:
            continue
        for node_id, node in mapping.items():
            msg_obj = node.get('message')
            if not isinstance(msg_obj, dict):
                continue
            ts = msg_obj.get('inserted_at')
            utc_ts = None
            if ts:
                try:
                    utc_ts = datetime.fromisoformat(str(ts).replace('Z', '+00:00')).timestamp()
                except:
                    pass
            fragments = msg_obj.get('fragments', [])
            full_content = ''
            for frag in fragments:
                if isinstance(frag, dict):
                    full_content += frag.get('content', '') + '\n'
            # Extract code blocks
            import re
            blocks = re.findall(r"```(?:\w+)?\n(.*?)\n```", full_content, re.DOTALL)
            for bi, block in enumerate(blocks):
                h = __import__('hashlib').sha256(block.strip().encode()).hexdigest()
                nh = __import__('hashlib').sha256(
                    '\n'.join(line.rstrip() for line in block.splitlines()).encode()
                ).hexdigest()
                if h in exact_hashes or nh in norm_hashes:
                    code_blocks.append({
                        'hash': h,
                        'session': str(session_id),
                        'node_id': node_id,
                        'block_idx': bi,
                        'timestamp_utc': utc_ts,
                        'snippet': block[:200] + ('...' if len(block) > 200 else ''),
                        'ts_iso': datetime.fromtimestamp(utc_ts, tz=timezone.utc).isoformat() if utc_ts else None
                    })

print(f"Hash‑confirmed code blocks from 2026: {len(code_blocks)}")

# --- Map each code block to the file(s) it matches ---
# Reverse lookup: hash -> file path
hash_to_file = {}
for h in exact_hashes:
    hash_to_file[h] = cache['exact'][h]
for h in norm_hashes:
    if h not in hash_to_file:
        hash_to_file[h] = cache['norm'][h]

# Group code blocks by file
file_versions = {}
for cb in code_blocks:
    fname = hash_to_file.get(cb['hash'])
    if not fname:
        continue
    file_versions.setdefault(fname, []).append(cb)

# Sort each file's versions by timestamp
for fname in file_versions:
    file_versions[fname].sort(key=lambda cb: cb['timestamp_utc'] or 0)

# Get file mtimes
file_mtimes = {}
for fname in file_versions:
    fpath = HOME / fname
    if fpath.exists():
        file_mtimes[fname] = fpath.stat().st_mtime

# Build versioned index
versioned = {}
all_first_delays = []
all_iteration_counts = []
all_total_spans = []

for fname, versions in file_versions.items():
    mtime = file_mtimes.get(fname)
    first_ts = versions[0]['timestamp_utc']
    last_ts = versions[-1]['timestamp_utc']
    first_delay = (mtime - first_ts) if (mtime and first_ts) else None
    total_span = (last_ts - first_ts) if (first_ts and last_ts) else None
    iteration_count = len(versions)

    versioned[fname] = {
        'file_mtime_utc': datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat() if mtime else None,
        'first_write_delay_s': first_delay,
        'iteration_count': iteration_count,
        'total_evolution_span_s': total_span,
        'versions': [{
            'session': v['session'],
            'timestamp_utc': v['ts_iso'],
            'block_idx': v['block_idx'],
            'hash': v['hash'],
            'snippet': v['snippet']
        } for v in versions]
    }
    if first_delay is not None:
        all_first_delays.append(first_delay)
    all_iteration_counts.append(iteration_count)
    if total_span is not None:
        all_total_spans.append(total_span)

with open(VERSIONED_PROV, 'w') as f:
    json.dump(versioned, f, indent=2)

# Stats
import statistics
stats = {
    'files_with_provenance': len(versioned),
    'first_write_delay': {
        'count': len(all_first_delays),
        'min_s': min(all_first_delays) if all_first_delays else None,
        'max_s': max(all_first_delays) if all_first_delays else None,
        'mean_s': statistics.mean(all_first_delays) if all_first_delays else None,
        'median_s': statistics.median(all_first_delays) if all_first_delays else None,
    },
    'iterations_per_file': {
        'min': min(all_iteration_counts) if all_iteration_counts else 0,
        'max': max(all_iteration_counts) if all_iteration_counts else 0,
        'mean': statistics.mean(all_iteration_counts) if all_iteration_counts else 0,
        'median': statistics.median(all_iteration_counts) if all_iteration_counts else 0,
    },
    'total_evolution_span': {
        'min_s': min(all_total_spans) if all_total_spans else None,
        'max_s': max(all_total_spans) if all_total_spans else None,
        'mean_s': statistics.mean(all_total_spans) if all_total_spans else None,
        'median_s': statistics.median(all_total_spans) if all_total_spans else None,
    }
}
with open(VERSION_STATS, 'w') as f:
    json.dump(stats, f, indent=2)

print(f"\nFiles with versioned provenance: {len(versioned)}")
if all_first_delays:
    print(f"First‑write delay (median): {statistics.median(all_first_delays):.0f}s")
    # Show histogram in 60s buckets
    hist = {}
    for d in all_first_delays:
        b = int(d // 60) * 60
        hist[b] = hist.get(b, 0) + 1
    print("First‑write histogram (60s buckets):")
    for b in sorted(hist):
        print(f"  {b//60}min: {hist[b]} files")
print(f"Iterations per file (median): {statistics.median(all_iteration_counts):.0f}")