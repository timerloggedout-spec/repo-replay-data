#!/usr/bin/env python3
"""Extract only exact-hash matches and compute real copy‑paste delays."""
import json, statistics
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
INDEX_FILE = OUT / "hash_index.json"
MATCHES_FILE = OUT / "matches.jsonl"
TRUE_PROV = OUT / "true_file_provenance.json"
TRUE_STATS = OUT / "true_copy_paste_stats.json"

# Load hash index
with open(INDEX_FILE) as f:
    cache = json.load(f)
exact = cache.get('exact', {})
norm = cache.get('norm', {})

file_matches = {}
delays = []

with open(MATCHES_FILE) as fh:
    for line in fh:
        m = json.loads(line)
        fname = m['file']
        cb = m['code_block']
        h = cb['hash']
        # Only keep if the hash is an exact match (or normalized)
        if h not in exact and h not in norm:
            continue
        # compute delay
        ts_str = cb.get('timestamp_utc')
        file_ts_str = m.get('file_mtime_utc')
        if ts_str and file_ts_str:
            try:
                utc = datetime.fromisoformat(ts_str).timestamp()
                fts = datetime.fromisoformat(file_ts_str).timestamp()
                delay = fts - utc
            except:
                delay = None
        else:
            delay = None
        entry = {
            'session': cb['session'],
            'node_id': cb['node_id'],
            'block_idx': cb['block_idx'],
            'timestamp_utc': cb['timestamp_utc'],
            'hash': h,
            'snippet': cb.get('snippet',''),
            'delay_seconds': delay
        }
        file_matches.setdefault(fname, []).append(entry)
        if delay is not None:
            delays.append(delay)

# Select best match per file (closest delay to zero)
best = {}
for fname, entries in file_matches.items():
    entries.sort(key=lambda e: abs(e['delay_seconds']) if e['delay_seconds'] is not None else float('inf'))
    best[fname] = entries[0]

with open(TRUE_PROV, 'w') as f:
    json.dump(best, f, indent=2)

if delays:
    pos_delays = [d for d in delays if d > 0]
    stats = {
        'count': len(delays),
        'positive_count': len(pos_delays),
        'min_s': min(delays),
        'max_s': max(delays),
        'mean_s': statistics.mean(delays),
        'median_s': statistics.median(delays),
        'positive_median_s': statistics.median(pos_delays) if pos_delays else None
    }
    with open(TRUE_STATS, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"True exact‑hash matches: {len(best)} files")
    print(f"Real copy‑paste median (positive): {stats['positive_median_s']:.0f}s")
else:
    print("No exact‑hash matches found.")