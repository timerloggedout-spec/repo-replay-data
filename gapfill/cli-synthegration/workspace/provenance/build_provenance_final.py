#!/usr/bin/env python3
"""
build_provenance_final.py – Final provenance mapper using DeepSeek exports.
Parses large conversations.json files, extracts code blocks with UTC timestamps,
matches to project files by content hash, and computes copy‑paste delays.
Writes output via CEDARScriptEditor.
"""
import json, hashlib, re, statistics, os, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUTPUT_DIR = HOME / "cli-synthegration/workspace/provenance"
EXPORT_PATHS = [
    HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-26/conversations.json",
    HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-17/conversations.json",
    # also try the zipped content if already unzipped
]
SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT_PARTS = {"node_modules","__pycache__",".cache",".git","dist",
               "codex/blobs","browser-data",".blob","logs","tmp"}
TIME_WINDOW_MINUTES = 10
OUTPUT_FILE = OUTPUT_DIR / "provenance_time_index.json"
DELAY_STATS_FILE = OUTPUT_DIR / "copy_paste_stats.json"

# CEDARscript
cedar_editor = None
try:
    from cedarscript_editor import CEDARScriptEditor
    cedar_editor = CEDARScriptEditor(root_path=str(OUTPUT_DIR))
    print("CEDARScriptEditor loaded")
except: pass

def safe_write(path, content):
    if cedar_editor:
        try:
            cedar_editor.write_file(str(path), content)
            return
        except: pass
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    os.replace(tmp, path)

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

def extract_blocks(text):
    if not isinstance(text, str): return []
    return re.findall(r"```(?:\w+)?\n(.*?)\n```", text, re.DOTALL)

def is_bloat(parts):
    return any(p in BLOAT_PARTS for p in parts)

# --- 1. Parse DeepSeek exports ---
code_blocks = []
for exp_path in EXPORT_PATHS:
    if not exp_path.exists():
        print(f"Not found: {exp_path}")
        continue
    print(f"Loading {exp_path} ({exp_path.stat().st_size/1024/1024:.1f} MB)...")
    with open(exp_path, 'r') as f:
        data = json.load(f)
    if isinstance(data, dict):
        conversations = [data]
    elif isinstance(data, list):
        conversations = data
    else:
        print("Unexpected format, skipping")
        continue
    print(f"Loaded {len(conversations)} conversations")
    for conv in conversations:
        session_id = conv.get('id') or conv.get('session_id') or conv.get('title', 'unknown')
        # Handle DeepSeek mapping format
        mapping = conv.get('mapping', {})
        messages = conv.get('messages', [])
        if isinstance(mapping, dict):
            for node_id, node in mapping.items():
                msg_obj = node.get('message')
                if not isinstance(msg_obj, dict): continue
                ts = msg_obj.get('inserted_at') or msg_obj.get('created_at')
                fragments = msg_obj.get('fragments', [])
                content = ''
                for frag in fragments:
                    if isinstance(frag, dict):
                        content += frag.get('content', '') + '\n'
                if ts and content:
                    try:
                        utc_ts = datetime.fromisoformat(str(ts).replace('Z','+00:00')).timestamp()
                    except: continue
                    for bi, block in enumerate(extract_blocks(content)):
                        code_blocks.append({
                            'hash': sha256(block.strip()),
                            'session': str(session_id),
                            'node_id': node_id,
                            'block_idx': bi,
                            'timestamp_utc': utc_ts,
                            'snippet': block[:200] + ('...' if len(block) > 200 else '')
                        })
        elif isinstance(messages, list):
            for mi, msg in enumerate(messages):
                content = msg.get('content') or msg.get('text') or ''
                ts = msg.get('created_at') or msg.get('timestamp') or msg.get('date') or conv.get('updated_at')
                if not ts: continue
                try:
                    if isinstance(ts, (int,float)): utc_ts = ts
                    else: utc_ts = datetime.fromisoformat(str(ts).replace('Z','+00:00')).timestamp()
                except: continue
                for bi, block in enumerate(extract_blocks(content)):
                    code_blocks.append({
                        'hash': sha256(block.strip()),
                        'session': str(session_id),
                        'msg_idx': mi,
                        'block_idx': bi,
                        'timestamp_utc': utc_ts,
                        'snippet': block[:200] + ('...' if len(block) > 200 else '')
                    })
print(f"Total code blocks extracted: {len(code_blocks)}")

# --- 2. Hash source files ---
file_records = {}
for base in SOURCE_DIRS:
    base_path = HOME / base
    if not base_path.is_dir(): continue
    for fp in base_path.rglob('*'):
        if fp.is_file() and not is_bloat(fp.parts):
            try:
                content = fp.read_text()
                mtime = fp.stat().st_mtime
                h = sha256(content)
                rel = str(fp.relative_to(HOME))
                file_records[rel] = {'hash': h, 'mtime': mtime}
            except: pass
print(f"Files hashed: {len(file_records)}")

# --- 3. Match ---
matches = []
delays = []
for rel, finfo in file_records.items():
    matched = []
    for cb in code_blocks:
        if cb['hash'] == finfo['hash']:
            matched.append(cb)
            delays.append(finfo['mtime'] - cb['timestamp_utc'])
        elif abs(finfo['mtime'] - cb['timestamp_utc']) <= TIME_WINDOW_MINUTES * 60:
            matched.append(cb)
            delays.append(finfo['mtime'] - cb['timestamp_utc'])
    if matched:
        matches.append({
            'file': rel,
            'file_hash': finfo['hash'],
            'file_mtime_utc': datetime.fromtimestamp(finfo['mtime'], tz=timezone.utc).isoformat(),
            'matched_code_blocks': [{
                'hash': cb['hash'],
                'session': cb['session'],
                'node_id': cb.get('node_id', ''),
                'message_index': cb.get('msg_idx', ''),
                'block_index': cb['block_idx'],
                'timestamp_utc': datetime.fromtimestamp(cb['timestamp_utc'], tz=timezone.utc).isoformat(),
                'snippet': cb['snippet']
            } for cb in matched]
        })

# --- 4. Write outputs ---
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
index = {
    'meta': {
        'exports_loaded': len(EXPORT_PATHS),
        'code_blocks_extracted': len(code_blocks),
        'source_files_hashed': len(file_records),
        'time_window_minutes': TIME_WINDOW_MINUTES,
        'files_with_matches': len(matches),
        'delays_recorded': len(delays)
    },
    'matches': matches
}
safe_write(OUTPUT_FILE, json.dumps(index, indent=2))
print(f"Provenance index -> {OUTPUT_FILE}")

if delays:
    stats = {
        'count': len(delays),
        'min_seconds': min(delays),
        'max_seconds': max(delays),
        'mean_seconds': statistics.mean(delays),
        'median_seconds': statistics.median(delays),
        'histogram_10s_buckets': {}
    }
    for d in delays:
        bucket = int(d // 10) * 10
        stats['histogram_10s_buckets'][str(bucket)] = stats['histogram_10s_buckets'].get(str(bucket), 0) + 1
    safe_write(DELAY_STATS_FILE, json.dumps(stats, indent=2))
    print(f"Delay stats -> {DELAY_STATS_FILE}")
    print(f"  Min: {stats['min_seconds']:.0f}s, Max: {stats['max_seconds']:.0f}s, Mean: {stats['mean_seconds']:.0f}s, Median: {stats['median_seconds']:.0f}s")
else:
    print("No matches found.")