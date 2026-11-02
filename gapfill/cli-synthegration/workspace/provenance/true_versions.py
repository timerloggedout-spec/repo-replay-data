#!/usr/bin/env python3
"""
true_versions.py – Versioned provenance using content similarity.
Only code blocks that actually match the file are counted.
"""
import json, sys, re, hashlib, statistics, difflib
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
MAX_DELAY = 2 * 3600
SIMILARITY_THRESHOLD = 0.8  # 80% similarity

SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT = {"node_modules","__pycache__",".cache",".git","dist","codex/blobs","browser-data",".blob","logs","tmp"}

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

# --- File mtimes & content (for small files only, <1MB) ---
file_info = {}
for base in SOURCE_DIRS:
    for fp in (HOME / base).rglob('*'):
        if fp.is_file() and not any(p in BLOAT for p in fp.parts):
            if fp.stat().st_size > 1_000_000: continue
            try:
                content = fp.read_text()
                file_info[str(fp.relative_to(HOME))] = {
                    'mtime': fp.stat().st_mtime,
                    'content': content
                }
            except: pass
print(f"Files loaded: {len(file_info)}")

# --- Extract code blocks from 2026 exports ---
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
                    'hash': sha256(block.strip())
                })
print(f"Code blocks: {len(code_blocks)}")

# --- Match using content similarity ---
file_versions = {}
for fname, finfo in file_info.items():
    versions = []
    for cb in code_blocks:
        if cb['timestamp_utc'] is None: continue
        delay = finfo['mtime'] - cb['timestamp_utc']
        if 0 <= delay <= MAX_DELAY:
            # Check similarity between file content and code block
            similarity = difflib.SequenceMatcher(None, finfo['content'], cb['text']).ratio()
            if similarity >= SIMILARITY_THRESHOLD:
                versions.append({
                    'session': cb['session'],
                    'node_id': cb['node_id'],
                    'block_idx': cb['block_idx'],
                    'timestamp_utc': datetime.fromtimestamp(cb['timestamp_utc'], tz=timezone.utc).isoformat(),
                    'delay_s': delay,
                    'similarity': round(similarity, 3),
                    'hash': cb['hash'],
                    'snippet': cb['text'][:200]
                })
    if versions:
        versions.sort(key=lambda v: v['delay_s'])
        file_versions[fname] = versions

print(f"Files with true versions: {len(file_versions)}")

# --- Stats ---
all_iter_counts = []
all_first_delays = []
all_total_spans = []
for versions in file_versions.values():
    count = len(versions)
    all_iter_counts.append(count)
    all_first_delays.append(versions[0]['delay_s'])
    if count >= 2:
        span = versions[-1]['delay_s'] - versions[0]['delay_s']
        all_total_spans.append(span)

with open(OUT / "true_versions.json", 'w') as f:
    json.dump(file_versions, f, indent=2)

stats = {
    'files_with_versions': len(file_versions),
    'iterations': {
        'min': min(all_iter_counts) if all_iter_counts else 0,
        'max': max(all_iter_counts) if all_iter_counts else 0,
        'mean': statistics.mean(all_iter_counts) if all_iter_counts else 0,
        'median': statistics.median(all_iter_counts) if all_iter_counts else 0,
    },
    'first_write_delay_s': {
        'min': min(all_first_delays) if all_first_delays else None,
        'max': max(all_first_delays) if all_first_delays else None,
        'mean': statistics.mean(all_first_delays) if all_first_delays else None,
        'median': statistics.median(all_first_delays) if all_first_delays else None,
    },
    'total_evolution_span_s': {
        'min': min(all_total_spans) if all_total_spans else None,
        'max': max(all_total_spans) if all_total_spans else None,
        'mean': statistics.mean(all_total_spans) if all_total_spans else None,
        'median': statistics.median(all_total_spans) if all_total_spans else None,
    }
}
with open(OUT / "true_versions_stats.json", 'w') as f:
    json.dump(stats, f, indent=2)

print("\nTrue versioning stats:")
print(f"  Iterations per file (median): {stats['iterations']['median']}")
print(f"  First-write delay (median): {stats['first_write_delay_s']['median']:.0f}s")
if all_total_spans:
    print(f"  Evolution span (median): {stats['total_evolution_span_s']['median']:.0f}s")