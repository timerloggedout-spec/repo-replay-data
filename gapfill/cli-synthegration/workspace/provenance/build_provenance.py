#!/usr/bin/env python3
"""
build_provenance.py – Extract code blocks from DeepSeek mapping/fragments format.
Writes provenance index and copy‑paste stats using CEDARScriptEditor.
"""
import sys, os, json, hashlib, re, statistics
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
sys.path.insert(0, str(HOME / "cli-synthegration"))

SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT_PARTS = {"node_modules","__pycache__",".cache",".git","dist",
               "codex/blobs","browser-data",".blob","logs","tmp"}
TIME_WINDOW_MINUTES = 10
OUTPUT_DIR = HOME / "cli-synthegration/workspace/provenance"
OUTPUT_FILE = OUTPUT_DIR / "provenance_time_index.json"
DELAY_STATS_FILE = OUTPUT_DIR / "copy_paste_stats.json"

# CEDARscript
cedar_editor = None
try:
    from cedarscript_editor import CEDARScriptEditor
    cedar_editor = CEDARScriptEditor(root_path=str(OUTPUT_DIR))
    print("CEDARScriptEditor loaded")
except ImportError:
    print("CEDARscript not available, using standard writes")

def safe_write(path, content):
    if cedar_editor:
        try:
            cedar_editor.write_file(str(path), content)
            return
        except AttributeError:
            pass
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    os.replace(tmp, path)

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

def extract_blocks(text):
    if not isinstance(text, str):
        return []
    return re.findall(r"```(?:\w+)?\n(.*?)\n```", text, re.DOTALL)

def is_bloat(parts):
    return any(p in BLOAT_PARTS for p in parts)

# --- 1. Load conversations ---
def get_conversations():
    sessions = []
    try:
        import conv_explorer
        for fn in ['load_all_sessions','list_sessions','get_sessions','offline_sessions','load_conversations']:
            func = getattr(conv_explorer, fn, None)
            if not func: continue
            try:
                result = func()
                if isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict): sessions.append(item)
                        elif isinstance(item, str):
                            loader = getattr(conv_explorer, 'load_conversation', None) or \
                                     getattr(conv_explorer, 'get_conversation', None)
                            if loader:
                                conv = loader(item)
                                if isinstance(conv, dict): sessions.append(conv)
                elif isinstance(result, dict): sessions.append(result)
            except Exception as e: print(f"  {fn}: {e}")
    except Exception as e: print(f"conv_explorer import: {e}")
    if not sessions:
        for d in ['synthegration_exports', 'deepseek_harvest_work']:
            exp_dir = HOME / d
            if not exp_dir.is_dir(): continue
            for f in exp_dir.glob('*.json'):
                try:
                    conv = json.loads(f.read_text())
                    if isinstance(conv, dict): sessions.append(conv)
                    elif isinstance(conv, list):
                        sessions.extend([c for c in conv if isinstance(c, dict)])
                except: pass
    return [s for s in sessions if isinstance(s, dict)]

conversations = get_conversations()
print(f"Loaded {len(conversations)} conversations")

# --- 2. Extract code blocks from mapping/fragments ---
code_blocks = []

for conv in conversations:
    session_id = conv.get('id') or conv.get('session_id') or conv.get('title', 'unknown')
    mapping = conv.get('mapping', {})
    if not isinstance(mapping, dict):
        continue
    for node_id, node in mapping.items():
        # node is a dict with 'id','parent','children','message'
        msg_obj = node.get('message')
        if not isinstance(msg_obj, dict):
            continue
        # Timestamp: msg_obj['inserted_at']
        ts = msg_obj.get('inserted_at')
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
        except:
            continue
        utc_ts = dt.timestamp()

        # Content: msg_obj['fragments'][...]['content']
        fragments = msg_obj.get('fragments', [])
        if not isinstance(fragments, list):
            continue
        combined_content = ''
        for frag in fragments:
            if not isinstance(frag, dict):
                continue
            c = frag.get('content', '')
            if isinstance(c, str):
                combined_content += c + '\n'
        if not combined_content.strip():
            continue

        for bi, block in enumerate(extract_blocks(combined_content)):
            code_blocks.append({
                'hash': sha256(block.strip()),
                'session': str(session_id),
                'node_id': node_id,
                'block_idx': bi,
                'timestamp_utc': utc_ts,
                'snippet': block[:200] + ('...' if len(block) > 200 else '')
            })

print(f"Extracted {len(code_blocks)} code blocks")

# --- 3. Hash source files ---
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
print(f"Hashed {len(file_records)} source files")

# --- 4. Match ---
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
                'node_id': cb['node_id'],
                'block_index': cb['block_idx'],
                'timestamp_utc': datetime.fromtimestamp(cb['timestamp_utc'], tz=timezone.utc).isoformat(),
                'snippet': cb['snippet']
            } for cb in matched]
        })

# --- 5. Write outputs ---
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
index = {
    'meta': {
        'conversations_loaded': len(conversations),
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
    print("No delays computed.")