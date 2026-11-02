#!/usr/bin/env python3
"""
rematch_temporal.py – Re‑match files to the closest session *before* file mtime.
This finds the actual conversation that created each file and computes a realistic delay.
"""
import json, statistics, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
INDEX_FILE = OUT / "hash_index.json"
MATCHES_FILE = OUT / "matches.jsonl"
FINAL_PROV = OUT / "temporal_provenance.json"
STATS_FILE = OUT / "temporal_delay_stats.json"

# Load hash index
with open(INDEX_FILE) as f:
    cache = json.load(f)
exact_hashes = set(cache.get('exact', {}).keys())
norm_hashes  = set(cache.get('norm', {}).keys())

# Parse matches.jsonl, keep only hash‑confirmed entries, store all sessions per file
file_sessions = {}
with open(MATCHES_FILE) as fh:
    for line in fh:
        m = json.loads(line)
        cb = m['code_block']
        h = cb['hash']
        if h not in exact_hashes and h not in norm_hashes:
            continue
        ts_str = cb.get('timestamp_utc')
        utc_ts = None
        if ts_str:
            try:
                utc_ts = datetime.fromisoformat(ts_str).timestamp()
            except:
                pass
        entry = {
            'session': cb['session'],
            'node_id': cb['node_id'],
            'block_idx': cb['block_idx'],
            'timestamp_utc': utc_ts,
            'hash': h,
            'snippet': cb.get('snippet', '')
        }
        fname = m['file']
        file_sessions.setdefault(fname, []).append(entry)

print(f"Files with hash matches: {len(file_sessions)}")

# Get file mtimes (we can load from the hash index path -> mtime? Not stored.
# We'll stat each file now; it's fast.)
file_mtimes = {}
for fname in file_sessions:
    fpath = HOME / fname
    if fpath.exists():
        file_mtimes[fname] = fpath.stat().st_mtime

# For each file, select the session with the largest timestamp that is <= file mtime
# (the most recent session before the file was created)
best = {}
delays = []
used_sessions = set()
for fname, sessions in file_sessions.items():
    mtime = file_mtimes.get(fname)
    if not mtime:
        continue
    # Filter sessions with valid timestamp <= mtime
    valid = [s for s in sessions if s['timestamp_utc'] is not None and s['timestamp_utc'] <= mtime]
    if not valid:
        continue
    # Pick the latest session (closest to mtime, but still before)
    best_sess = max(valid, key=lambda s: s['timestamp_utc'])
    delay = mtime - best_sess['timestamp_utc']
    best_sess['delay_seconds'] = delay
    best[fname] = best_sess
    delays.append(delay)
    used_sessions.add(best_sess['session'])

print(f"Files with a prior session: {len(best)}")
if delays:
    print(f"Delay range: {min(delays):.0f}s – {max(delays):.0f}s")
    print(f"Median copy‑paste delay: {statistics.median(delays):.0f}s")
    pos_delays = [d for d in delays if d > 0]
    if pos_delays:
        print(f"Median positive delay: {statistics.median(pos_delays):.0f}s")
    # Save
    with open(FINAL_PROV, 'w') as f:
        json.dump(best, f, indent=2)
    stats = {
        'count': len(delays),
        'min_s': min(delays),
        'max_s': max(delays),
        'mean_s': statistics.mean(delays),
        'median_s': statistics.median(delays),
        'positive_median_s': statistics.median(pos_delays) if pos_delays else None
    }
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Temporal provenance written to {FINAL_PROV}")
else:
    print("No files had a session before their mtime.")