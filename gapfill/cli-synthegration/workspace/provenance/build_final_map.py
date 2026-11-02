#!/usr/bin/env python3
"""
build_final_map.py – Create definitive file‑to‑session provenance map.
Uses cached hash index and matches.jsonl; produces clean per‑file mapping.
"""
import json, sys, os
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUTPUT_DIR = HOME / "cli-synthegration/workspace/provenance"
INDEX_FILE = OUTPUT_DIR / "hash_index.json"
MATCHES_FILE = OUTPUT_DIR / "matches.jsonl"
FILE_PROV_FILE = OUTPUT_DIR / "file_provenance.json"
SUMMARY_FILE = OUTPUT_DIR / "provenance_summary.json"

# Load hash index (quick)
if not INDEX_FILE.exists():
    print("Hash index missing; run final_provenance.py first.")
    sys.exit(1)
with open(INDEX_FILE) as f:
    cache = json.load(f)
exact = cache.get('exact', {})
norm = cache.get('norm', {})
print(f"Loaded {len(exact)} file hashes.")

# Parse matches and group by file
file_matches = {}
delays_all = []
match_count = 0
if MATCHES_FILE.exists():
    with open(MATCHES_FILE) as fh:
        for line in fh:
            try:
                m = json.loads(line)
            except:
                continue
            fname = m['file']
            cb = m['code_block']
            # compute delay if timestamps exist
            ts_utc = None
            if cb.get('timestamp_utc'):
                try:
                    ts_utc = datetime.fromisoformat(cb['timestamp_utc']).timestamp()
                except:
                    pass
            file_ts = None
            if m.get('file_mtime_utc'):
                try:
                    file_ts = datetime.fromisoformat(m['file_mtime_utc']).timestamp()
                except:
                    pass
            delay = (file_ts - ts_utc) if (ts_utc and file_ts) else None
            entry = {
                'session': cb['session'],
                'node_id': cb['node_id'],
                'block_idx': cb['block_idx'],
                'timestamp_utc': cb['timestamp_utc'],
                'hash': cb['hash'],
                'snippet': cb.get('snippet', ''),
                'delay_seconds': delay
            }
            file_matches.setdefault(fname, []).append(entry)
            if delay is not None:
                delays_all.append(delay)
            match_count += 1
print(f"Processed {match_count} matches for {len(file_matches)} files.")

# For each file, select the best match (smallest absolute delay, preferring positive)
best_matches = {}
for fname, entries in file_matches.items():
    # sort by abs(delay) then by delay sign (positive preferred)
    def sort_key(e):
        d = e.get('delay_seconds')
        if d is None:
            return (float('inf'), 0)
        return (abs(d), -d if d > 0 else d)
    best = sorted(entries, key=sort_key)[0]
    best_matches[fname] = best

# Write per‑file provenance
with open(FILE_PROV_FILE, 'w') as f:
    json.dump(best_matches, f, indent=2)
print(f"File provenance map → {FILE_PROV_FILE}")

# Summary stats
import statistics
if delays_all:
    stats = {
        'total_files': len(file_matches),
        'total_matches': match_count,
        'delays': {
            'count': len(delays_all),
            'min_s': min(delays_all),
            'max_s': max(delays_all),
            'mean_s': statistics.mean(delays_all),
            'median_s': statistics.median(delays_all),
            'positive_median_s': statistics.median([d for d in delays_all if d > 0]) if any(d > 0 for d in delays_all) else None,
            'absolute_median_s': statistics.median([abs(d) for d in delays_all])
        }
    }
    with open(SUMMARY_FILE, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Summary → {SUMMARY_FILE}")
    print(f"Median copy‑paste delay: {stats['delays']['positive_median_s']:.0f}s")
else:
    print("No delays available.")