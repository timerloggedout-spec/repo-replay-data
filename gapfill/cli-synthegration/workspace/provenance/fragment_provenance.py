#!/usr/bin/env python3
"""
fragment_provenance.py – Match code blocks to fragments (functions/classes) of source files.
Computes true iteration acceleration using message‑to‑message intervals.
"""
import json, sys, re, hashlib, statistics, difflib
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
MAX_DELAY = 6 * 3600       # 6 hours
SIMILARITY = 0.6
MIN_FRAGMENT_LINES = 4

SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT_PARTS = {"node_modules","__pycache__",".cache",".git","dist",
               "codex","blobs","browser-data",".blob","logs","tmp",
               "target","release",".fingerprint","deps","build"}

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()
def normalize(text):
    return '\n'.join(line.rstrip() for line in text.splitlines())
def is_bloat(parts):
    return any(p in BLOAT_PARTS for p in parts)

# --- 1. Extract top‑level definitions from Python files ---
def extract_definitions(content):
    """Return list of (def_name, def_body) tuples for Python functions/classes."""
    defs = []
    lines = content.splitlines()
    pattern = r'^\s*(def |class )(\w+)'
    i = 0
    while i < len(lines):
        m = re.match(pattern, lines[i])
        if m:
            name = m.group(2)
            # capture body until next top‑level def/class or end
            body_lines = [lines[i]]
            j = i + 1
            while j < len(lines) and not re.match(r'^\s*(def |class |\S)', lines[j]):
                body_lines.append(lines[j])
                j += 1
            body = '\n'.join(body_lines)
            if len(body_lines) >= MIN_FRAGMENT_LINES:
                defs.append((name, body))
            i = j
        else:
            i += 1
    return defs

# --- 2. Load source files ---
file_fragments = {}   # file -> list of (name, body)
for base in SOURCE_DIRS:
    for fp in (HOME / base).rglob('*.py'):
        if fp.is_file() and not is_bloat(fp.parts):
            if fp.stat().st_size > 1_000_000: continue
            try:
                content = fp.read_text()
                defs = extract_definitions(content)
                if defs:
                    rel = str(fp.relative_to(HOME))
                    file_fragments[rel] = {'mtime': fp.stat().st_mtime, 'fragments': defs}
            except: pass
print(f"Python files with definitions: {len(file_fragments)}")

# --- 3. Extract code blocks from 2026 exports ---
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

# --- 4. Match code blocks to file fragments ---
file_versions = {}  # file -> list of versions, each with fragment name, delay, etc.
for fname, finfo in file_fragments.items():
    versions = []
    for cb in code_blocks:
        if cb['timestamp_utc'] is None: continue
        delay = finfo['mtime'] - cb['timestamp_utc']
        if 0 <= delay <= MAX_DELAY:
            # Try to match each fragment
            for def_name, def_body in finfo['fragments']:
                sim = difflib.SequenceMatcher(None, def_body, cb['text']).ratio()
                if sim >= SIMILARITY:
                    versions.append({
                        'fragment': def_name,
                        'session': cb['session'],
                        'node_id': cb['node_id'],
                        'block_idx': cb['block_idx'],
                        'timestamp_utc': datetime.fromtimestamp(cb['timestamp_utc'], tz=timezone.utc).isoformat(),
                        'delay_s': delay,
                        'similarity': round(sim, 3),
                        'snippet': cb['text'][:200]
                    })
    if versions:
        versions.sort(key=lambda v: v['delay_s'])
        file_versions[fname] = versions

with open(OUT / "fragment_provenance.json", 'w') as f:
    json.dump(file_versions, f, indent=2)
print(f"Files with fragment‑level provenance: {len(file_versions)}")

# --- 5. True iteration speedup (message‑to‑message intervals) ---
# Group versions by (file, session) and compute intervals between consecutive messages
session_intervals = []
for fname, versions in file_versions.items():
    # Group by session
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
    true_speedup = statistics.median(session_intervals)
    print(f"Message‑to‑message intervals (n={len(session_intervals)}):")
    print(f"  Median interval: {true_speedup:.0f}s")
    print(f"  Min: {min(session_intervals):.0f}s, Max: {max(session_intervals):.0f}s")
    
    stats = {
        'fragment_matched_files': len(file_versions),
        'total_fragment_versions': sum(len(v) for v in file_versions.values()),
        'message_interval_median_s': true_speedup,
        'message_interval_min_s': min(session_intervals),
        'message_interval_max_s': max(session_intervals),
        'interpretation': f"Median {true_speedup:.0f}s between successive code blocks in the same session."
    }
    with open(OUT / "true_iteration_stats.json", 'w') as f:
        json.dump(stats, f, indent=2)
    print("Stats saved to true_iteration_stats.json")
else:
    print("No multi‑version files in the same session — try lowering SIMILARITY.")