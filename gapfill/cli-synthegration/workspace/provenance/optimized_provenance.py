#!/usr/bin/env python3
"""
optimized_provenance.py – Memory‑safe provenance for Termux.
Streams code blocks directly from conversation files, matches on the fly.
"""
import sys, os, json, hashlib, re, statistics, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
sys.path.insert(0, str(HOME / "cli-synthegration"))

# --- Config ---
SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT_PARTS = {"node_modules","__pycache__",".cache",".git","dist",
               "codex/blobs","browser-data",".blob","logs","tmp"}
OUTPUT_DIR = HOME / "cli-synthegration/workspace/provenance"
MATCHES_FILE = OUTPUT_DIR / "matches.jsonl"          # one JSON line per match
STATS_FILE = OUTPUT_DIR / "final_stats.json"
EXPORT_DIR = HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports"

# CEDARScript
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

def normalize(text):
    return '\n'.join(line.rstrip() for line in text.splitlines())

def is_bloat(parts):
    return any(p in BLOAT_PARTS for p in parts)

# --- 1. Build file hash dictionaries (only once) ---
print("Hashing source files...")
exact_map = {}   # hash -> {path, mtime}
norm_map = {}    # norm_hash -> {path, mtime}
for base in SOURCE_DIRS:
    base_path = HOME / base
    if not base_path.is_dir(): continue
    for fp in base_path.rglob('*'):
        if fp.is_file() and not is_bloat(fp.parts):
            try:
                content = fp.read_text()
                mtime = fp.stat().st_mtime
                h = sha256(content)
                nh = sha256(normalize(content))
                rel = str(fp.relative_to(HOME))
                info = {'path': rel, 'mtime': mtime}
                exact_map[h] = info
                norm_map[nh] = info
            except: pass
print(f"  {len(exact_map)} files hashed")

# --- 2. Process conversation files sequentially ---
total_blocks = 0
match_count = 0
delays = []

# We'll write matches line-by-line as JSONL
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
with open(MATCHES_FILE, 'w') as out_f:
    for version in ["deepseek_data-2026-05-26", "deepseek_data-2026-05-17"]:
        conv_file = EXPORT_DIR / version / "conversations.json"
        if not conv_file.exists():
            continue
        print(f"\nProcessing {conv_file.name} ({conv_file.stat().st_size//1024//1024} MB)...")
        try:
            with open(conv_file) as f:
                data = json.load(f)
        except Exception as e:
            print(f"  Error loading: {e}")
            continue

        # data might be a list or dict
        conversations = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
        for conv in conversations:
            session_id = conv.get('id') or conv.get('title', 'unknown')
            mapping = conv.get('mapping', {})
            if not mapping: continue

            for node_id, node in mapping.items():
                msg_obj = node.get('message')
                if not isinstance(msg_obj, dict): continue

                # timestamp
                ts = msg_obj.get('inserted_at')
                utc_ts = None
                if ts:
                    try:
                        dt = datetime.fromisoformat(str(ts).replace('Z','+00:00'))
                        utc_ts = dt.timestamp()
                    except: pass

                # content fragments
                fragments = msg_obj.get('fragments', [])
                full_content = ''
                for frag in fragments:
                    if isinstance(frag, dict):
                        full_content += frag.get('content', '') + '\n'

                # extract code blocks one by one
                for bi, block_text in enumerate(extract_blocks(full_content)):
                    total_blocks += 1
                    h = sha256(block_text.strip())
                    nh = sha256(normalize(block_text))
                    matched_info = exact_map.get(h) or norm_map.get(nh)
                    if matched_info:
                        match_count += 1
                        if utc_ts:
                            delay = matched_info['mtime'] - utc_ts
                            delays.append(delay)
                        # write match as JSON line
                        match_line = json.dumps({
                            'file': matched_info['path'],
                            'session': session_id,
                            'node_id': node_id,
                            'block_idx': bi,
                            'timestamp_utc': datetime.fromtimestamp(utc_ts, tz=timezone.utc).isoformat() if utc_ts else None,
                            'delay_seconds': delay if utc_ts else None
                        })
                        out_f.write(match_line + '\n')

                    # progress every 500 blocks
                    if total_blocks % 500 == 0:
                        print(f"  {total_blocks} blocks scanned, {match_count} matches...", end='\r')

print(f"\nTotal blocks scanned: {total_blocks}, matches: {match_count}")

# --- 3. Compute final statistics ---
stats = {
    'total_blocks': total_blocks,
    'matches': match_count,
    'delays': [] if not delays else {
        'count': len(delays),
        'min_seconds': min(delays),
        'max_seconds': max(delays),
        'mean_seconds': statistics.mean(delays),
        'median_seconds': statistics.median(delays)
    }
}
safe_write(STATS_FILE, json.dumps(stats, indent=2))
print(f"Stats -> {STATS_FILE}")
if delays:
    print(f"  Min: {stats['delays']['min_seconds']:.0f}s, Max: {stats['delays']['max_seconds']:.0f}s, Mean: {stats['delays']['mean_seconds']:.0f}s")
else:
    print("  No delays recorded.")