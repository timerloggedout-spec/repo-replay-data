#!/usr/bin/env python3
"""
rematch_recent.py – Re‑match files to sessions within 7 days before file mtime.
Only those can be the real copy‑paste origin.
"""
import json, statistics, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
INDEX_FILE = OUT / "hash_index.json"
MATCHES_FILE = OUT / "matches.jsonl"
RECENT_PROV = OUT / "recent_provenance.json"
RECENT_STATS = OUT / "recent_delay_stats.json"

MAX_AGE_SECONDS = 7 * 86400  # 7 days

# Load hash index
with open(INDEX_FILE) as f:
    cache = json.load(f)
exact_hashes = set(cache.get('exact', {}).keys())
norm_hashes  = set(cache.get('norm', {}).keys())

# Parse matches, keep hash‑confirmed, group by file
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

# Get file mtimes
file_mtimes = {}
for fname in file_sessions:
    fpath = HOME / fname
    if fpath.exists():
        file_mtimes[fname] = fpath.stat().st_mtime

# For each file, select best session: must be before file, and within MAX_AGE
best = {}
delays = []
no_recent = 0
for fname, sessions in file_sessions.items():
    mtime = file_mtimes.get(fname)
    if not mtime:
        continue
    # Filter: timestamp <= mtime, and age <= MAX_AGE
    recent = [
        s for s in sessions
        if s['timestamp_utc'] is not None
        and s['timestamp_utc'] <= mtime
        and (mtime - s['timestamp_utc']) <= MAX_AGE_SECONDS
    ]
    if not recent:
        no_recent += 1
        continue
    # Pick the one closest to mtime (most recent session)
    best_sess = max(recent, key=lambda s: s['timestamp_utc'])
    delay = mtime - best_sess['timestamp_utc']
    best_sess['delay_seconds'] = delay
    best[fname] = best_sess
    delays.append(delay)

print(f"Files with a recent session (≤7 days): {len(best)} (skipped {no_recent})")
if delays:
    print(f"Delay range: {min(delays):.0f}s – {max(delays):.0f}s")
    print(f"Median copy‑paste delay: {statistics.median(delays):.0f}s")
    pos_delays = [d for d in delays if d > 0]
    if pos_delays:
        print(f"Median positive delay: {statistics.median(pos_delays):.0f}s")
    with open(RECENT_PROV, 'w') as f:
        json.dump(best, f, indent=2)
    stats = {
        'count': len(delays),
        'min_s': min(delays),
        'max_s': max(delays),
        'mean_s': statistics.mean(delays),
        'median_s': statistics.median(delays),
        'positive_median_s': statistics.median(pos_delays) if pos_delays else None
    }
    with open(RECENT_STATS, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Saved to {RECENT_PROV}")
else:
    print("No recent matches at all. The sessions are all older than 7 days before the files.")