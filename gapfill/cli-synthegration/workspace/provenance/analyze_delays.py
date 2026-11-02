#!/usr/bin/env python3
"""Diagnose delay outliers and produce a cleaned, realistic provenance index."""
import json, statistics, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
INDEX_FILE = OUT / "hash_index.json"
MATCHES_FILE = OUT / "matches.jsonl"
TRUE_PROV = OUT / "true_file_provenance.json"  # input (from true_delays.py) or we re‑compute here
CLEAN_PROV = OUT / "real_provenance.json"
STATS_OUT = OUT / "delay_analysis.json"

# Load hash index
with open(INDEX_FILE) as f:
    cache = json.load(f)
exact_hashes = set(cache.get('exact', {}).keys())
norm_hashes  = set(cache.get('norm', {}).keys())

# Re‑parse matches.jsonl and collect only exact or norm hash matches
all_entries = []
delays_all = []
if MATCHES_FILE.exists():
    with open(MATCHES_FILE) as fh:
        for line in fh:
            m = json.loads(line)
            cb = m['code_block']
            h = cb['hash']
            # Keep only if exact or normalized hash match
            if h not in exact_hashes and h not in norm_hashes:
                continue
            # Compute delay
            ts_str = cb.get('timestamp_utc')
            file_ts_str = m.get('file_mtime_utc')
            delay = None
            if ts_str and file_ts_str:
                try:
                    utc = datetime.fromisoformat(ts_str).timestamp()
                    fts = datetime.fromisoformat(file_ts_str).timestamp()
                    delay = fts - utc
                except:
                    pass
            entry = {
                'file': m['file'],
                'session': cb['session'],
                'node_id': cb['node_id'],
                'block_idx': cb['block_idx'],
                'timestamp_utc': ts_str,
                'hash': h,
                'snippet': cb.get('snippet', ''),
                'delay_seconds': delay
            }
            all_entries.append(entry)
            if delay is not None:
                delays_all.append(delay)

print(f"Total hash‑confirmed matches: {len(all_entries)}")
if not all_entries:
    print("No matches found. Exiting.")
    sys.exit(0)

# --- Outlier analysis ---
delays_sorted = sorted(delays_all)
print(f"Delay range: {min(delays_all):.0f}s to {max(delays_all):.0f}s")
print(f"Median (all): {statistics.median(delays_all):.0f}s")
pos_delays = [d for d in delays_all if d > 0]
if pos_delays:
    print(f"Median (positive only): {statistics.median(pos_delays):.0f}s")

# Top 20 outliers (largest absolute)
outliers = sorted(all_entries, key=lambda e: abs(e['delay_seconds']) if e['delay_seconds'] is not None else 0, reverse=True)[:20]
print("\n=== Top 20 outliers (largest |delay|) ===")
for e in outliers:
    d = e['delay_seconds']
    print(f"  {e['file']}: delay={d:.0f}s, session={e['session']}, snippet={e['snippet'][:60]}...")

# Sample realistic matches (delay between 0 and 2 hours)
realistic = [e for e in all_entries if e['delay_seconds'] is not None and 0 < e['delay_seconds'] <= 7200]
print(f"\nRealistic matches (0–2h positive delay): {len(realistic)}")
if realistic:
    real_delays = [e['delay_seconds'] for e in realistic]
    print(f"  Realistic median: {statistics.median(real_delays):.0f}s")
    # Save cleaned provenance with only realistic matches (one per file, best delay)
    file_best = {}
    for e in realistic:
        f = e['file']
        if f not in file_best or abs(e['delay_seconds']) < abs(file_best[f]['delay_seconds']):
            file_best[f] = e
    with open(CLEAN_PROV, 'w') as f:
        json.dump(file_best, f, indent=2)
    print(f"  Clean provenance saved to {CLEAN_PROV} ({len(file_best)} files)")

    # Compute stats and save
    stats = {
        'count': len(real_delays),
        'min_s': min(real_delays),
        'max_s': max(real_delays),
        'mean_s': statistics.mean(real_delays),
        'median_s': statistics.median(real_delays),
        'histogram_60s_buckets': {}
    }
    for d in real_delays:
        bucket = int(d // 60) * 60
        stats['histogram_60s_buckets'][str(bucket)] = stats['histogram_60s_buckets'].get(str(bucket), 0) + 1
    with open(STATS_OUT, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"  Delay stats saved to {STATS_OUT}")
else:
    print("No realistic matches found. Check timezone offset.")

# Timezone sanity: compare a few file mtimes with known recent session timestamps
print("\n=== Timezone sanity check ===")
# Take a file we just created (this script) and a recent match if any
recent_files = [
    "cli-synthegration/workspace/provenance/analyze_delays.py",
    "cli-synthegration/workspace/provenance/final_provenance.py",
]
for fname in recent_files:
    fpath = HOME / fname
    if fpath.exists():
        mtime = fpath.stat().st_mtime
        print(f"{fname}: mtime={datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()}")
# Show a few session timestamps
if all_entries:
    sample_session_ts = all_entries[0]['timestamp_utc']
    print(f"Sample session timestamp: {sample_session_ts}")