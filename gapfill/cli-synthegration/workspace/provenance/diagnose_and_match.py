#!/usr/bin/env python3
"""
diagnose_and_match.py – Scan all projects for code-block databases,
dump sample timestamps/hashes, and attempt multiple matching strategies.
"""
import sys, os, json, hashlib, re, statistics
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
sys.path.insert(0, str(HOME / "cli-synthegration"))

# --- Config ---
ALL_PROJECTS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
# Also scan these extra directories for any JSON/export files
EXTRA_SCAN_DIRS = [
    "synthegration_exports",
    "deepseek_harvest_work",
    "cli-synthegration/exports",        # possible
    "termux-multi-agent/exports",
    "deepseek-cli/exports",
    "deepcli/exports",
]
BLOAT_PARTS = {"node_modules","__pycache__",".cache",".git","dist",
               "codex/blobs","browser-data",".blob","logs","tmp"}
OUTPUT_DIR = HOME / "cli-synthegration/workspace/provenance"
DIAG_REPORT = OUTPUT_DIR / "diagnostic_report.json"

# CEDARscript
cedar_editor = None
try:
    from cedarscript_editor import CEDARScriptEditor
    cedar_editor = CEDARScriptEditor(root_path=str(OUTPUT_DIR))
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

# --- 1. Discover all conversation data sources ---
data_sources = []

# 1a. Use conv_explorer
try:
    import conv_explorer
    for fn in ['load_all_sessions','list_sessions','get_sessions','offline_sessions','load_conversations']:
        func = getattr(conv_explorer, fn, None)
        if not func: continue
        try:
            result = func()
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict): data_sources.append({'source': f'conv_explorer.{fn}', 'data': item})
                    elif isinstance(item, str):
                        loader = getattr(conv_explorer, 'load_conversation', None) or \
                                 getattr(conv_explorer, 'get_conversation', None)
                        if loader:
                            conv = loader(item)
                            if isinstance(conv, dict): data_sources.append({'source': f'conv_explorer.{fn}', 'data': conv})
            elif isinstance(result, dict): data_sources.append({'source': f'conv_explorer.{fn}', 'data': result})
        except Exception as e: pass
except Exception as e: pass

# 1b. Scan project directories for JSON files that look like conversations
for base in ALL_PROJECTS + EXTRA_SCAN_DIRS:
    base_path = HOME / base
    if not base_path.is_dir(): continue
    for fpath in base_path.rglob('*.json'):
        if is_bloat(fpath.parts): continue
        try:
            with open(fpath) as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and ('mapping' in item or 'messages' in item):
                        data_sources.append({'source': str(fpath), 'data': item})
            elif isinstance(data, dict) and ('mapping' in data or 'messages' in data):
                data_sources.append({'source': str(fpath), 'data': data})
        except: pass

print(f"Found {len(data_sources)} total data sources")

# --- 2. Extract code blocks from all sources ---
def extract_from_data(data):
    """Extract code blocks from a conversation dict."""
    blocks = []
    session_id = data.get('id') or data.get('session_id') or data.get('title', 'unknown')
    # Try mapping/fragments first (DeepSeek format)
    mapping = data.get('mapping', {})
    messages = data.get('messages', [])
    if isinstance(mapping, dict) and not messages:
        for node_id, node in mapping.items():
            msg_obj = node.get('message')
            if not isinstance(msg_obj, dict): continue
            ts = msg_obj.get('inserted_at') or msg_obj.get('created_at')
            fragments = msg_obj.get('fragments', [])
            content = ''
            for frag in fragments:
                if isinstance(frag, dict):
                    content += frag.get('content', '') + '\n'
            if ts:
                try:
                    utc_ts = datetime.fromisoformat(str(ts).replace('Z','+00:00')).timestamp()
                except: continue
            else: utc_ts = None
            for bi, block in enumerate(extract_blocks(content)):
                blocks.append({
                    'hash': sha256(block.strip()),
                    'session': str(session_id),
                    'node_id': node_id,
                    'block_idx': bi,
                    'timestamp_utc': utc_ts,
                    'snippet': block[:200] + ('...' if len(block) > 200 else '')
                })
    elif isinstance(messages, list):
        for mi, msg in enumerate(messages):
            if not isinstance(msg, dict): continue
            content = msg.get('content') or msg.get('text') or ''
            ts = msg.get('created_at') or msg.get('timestamp') or msg.get('date') or data.get('updated_at')
            if ts:
                try:
                    if isinstance(ts, (int,float)): utc_ts = ts
                    else: utc_ts = datetime.fromisoformat(str(ts).replace('Z','+00:00')).timestamp()
                except: continue
            else: utc_ts = None
            for bi, block in enumerate(extract_blocks(content)):
                blocks.append({
                    'hash': sha256(block.strip()),
                    'session': str(session_id),
                    'msg_idx': mi,
                    'block_idx': bi,
                    'timestamp_utc': utc_ts,
                    'snippet': block[:200] + ('...' if len(block) > 200 else '')
                })
    return blocks

all_code_blocks = []
for src in data_sources:
    all_code_blocks.extend(extract_from_data(src['data']))
print(f"Total code blocks extracted: {len(all_code_blocks)}")

# --- 3. Hash source files (all projects) ---
file_records = {}
for base in ALL_PROJECTS:
    base_path = HOME / base
    if not base_path.is_dir(): continue
    for fp in base_path.rglob('*'):
        if fp.is_file() and not is_bloat(fp.parts):
            try:
                content = fp.read_text()
                mtime = fp.stat().st_mtime
                h = sha256(content)
                rel = str(fp.relative_to(HOME))
                file_records[rel] = {'hash': h, 'mtime': mtime, 'content': content}
            except: pass
print(f"Files hashed: {len(file_records)}")

# --- 4. Diagnostic: sample timestamps and hashes ---
sample_blocks = all_code_blocks[:5]
sample_files = list(file_records.items())[:5]
diag = {
    'sample_code_blocks': [{
        'hash': b['hash'],
        'timestamp_utc': b['timestamp_utc'],
        'snippet': b['snippet'][:100]
    } for b in sample_blocks],
    'sample_files': [{
        'path': rel,
        'hash': finfo['hash'],
        'mtime': finfo['mtime'],
        'mtime_utc': datetime.fromtimestamp(finfo['mtime'], tz=timezone.utc).isoformat(),
        'content_head': finfo['content'][:200]
    } for rel, finfo in sample_files],
    'timestamp_ranges': {
        'code_blocks': {
            'min': min(b['timestamp_utc'] for b in all_code_blocks if b['timestamp_utc']),
            'max': max(b['timestamp_utc'] for b in all_code_blocks if b['timestamp_utc'])
        } if all_code_blocks else {},
        'files': {
            'min': min(f['mtime'] for f in file_records.values()),
            'max': max(f['mtime'] for f in file_records.values())
        } if file_records else {}
    }
}

# --- 5. Matching with multiple strategies ---
matches_exact = []
matches_normalized = []
matches_time = []
delays = []

def normalize(text):
    return '\n'.join(line.strip() for line in text.splitlines()).strip()

# Build a normalized hash index for code blocks
norm_block_hashes = {}
for cb in all_code_blocks:
    norm_h = sha256(normalize(cb['snippet']) if len(cb['snippet']) <= 200 else normalize(cb['snippet']))  # need full text for hash; we only stored snippet. Recompute from source? For now, skip normalization match because we only have snippet. We'll do time-based only.
    # Actually we can't recompute full text from snippet. We'll skip normalized exact match for now, but we can do a time match with a very wide window.

for rel, finfo in file_records.items():
    file_mtime = finfo['mtime']
    file_hash = finfo['hash']
    # Exact hash match
    for cb in all_code_blocks:
        if cb['hash'] == file_hash:
            matches_exact.append({'file': rel, 'code_block': cb})
            if cb['timestamp_utc']:
                delays.append(file_mtime - cb['timestamp_utc'])
    # Time proximity match (wide window: 1 day for diagnostic)
    if not any(cb['hash'] == file_hash for cb in all_code_blocks):
        for cb in all_code_blocks:
            if cb['timestamp_utc'] and abs(file_mtime - cb['timestamp_utc']) <= 86400:  # 1 day
                matches_time.append({'file': rel, 'code_block': cb})
                delays.append(file_mtime - cb['timestamp_utc'])

diag['matches_exact'] = len(matches_exact)
diag['matches_time_1day'] = len(matches_time)
diag['matches_sample'] = (matches_exact + matches_time)[:5]

# --- 6. Write report ---
diag['delays'] = delays
safe_write(DIAG_REPORT, json.dumps(diag, indent=2))
print(f"Diagnostic report -> {DIAG_REPORT}")
print(f"Exact matches: {len(matches_exact)}, Time matches (1 day): {len(matches_time)}")
if delays:
    print(f"Delay stats: min={min(delays):.0f}s, max={max(delays):.0f}s, mean={statistics.mean(delays):.0f}s")
else:
    print("No delays computed.")