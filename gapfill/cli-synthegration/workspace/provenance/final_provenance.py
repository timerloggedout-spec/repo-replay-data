#!/usr/bin/env python3
"""
final_provenance.py – Termux-optimised, crash‑resistant provenance mapper.
Uses chunked hashing, persistent index, and streaming match output.
"""
import sys, os, json, hashlib, re, statistics, tempfile
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
INDEX_FILE = OUTPUT_DIR / "hash_index.json"   # persistent cache
MATCHES_FILE = OUTPUT_DIR / "matches.jsonl"
FINAL_INDEX = OUTPUT_DIR / "final_provenance_index.json"
MAX_FILE_SIZE = 5_000_000   # skip files larger than 5 MB
CHUNK_SIZE = 64 * 1024      # read 64 KB at a time

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
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    os.replace(tmp, path)

def sha256_file(path):
    """Chunked SHA-256 of a file, returns hex digest or None on error."""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

def extract_blocks(text):
    if not isinstance(text, str): return []
    return re.findall(r"```(?:\w+)?\n(.*?)\n```", text, re.DOTALL)

def normalize(text):
    return '\n'.join(line.rstrip() for line in text.splitlines())

def is_bloat(parts):
    return any(p in BLOAT_PARTS for p in parts)

# -------------------------------------------------------------------
# 1. Build / load hash index
# -------------------------------------------------------------------
exact_hash_to_path = {}
norm_hash_to_path = {}

def build_hash_index():
    """Walk source dirs, hash files chunked, store mapping."""
    global exact_hash_to_path, norm_hash_to_path
    file_count = 0
    for base in SOURCE_DIRS:
        base_path = HOME / base
        if not base_path.is_dir(): continue
        for fp in base_path.rglob('*'):
            if fp.is_file() and not is_bloat(fp.parts):
                try:
                    if fp.stat().st_size > MAX_FILE_SIZE:
                        continue   # skip large
                    h = sha256_file(str(fp))
                    if h is None:
                        continue
                    # For normalized hash we still need to read text, but we can do it only for small-ish files
                    if fp.stat().st_size < 1_000_000:  # only normalize files < 1 MB
                        try:
                            content = fp.read_text()
                            nh = sha256(normalize(content))
                            norm_hash_to_path[nh] = str(fp.relative_to(HOME))
                        except:
                            pass
                    exact_hash_to_path[h] = str(fp.relative_to(HOME))
                    file_count += 1
                except Exception:
                    continue
    print(f"Indexed {file_count} files.")
    # Save to disk for future runs
    cache = {
        'exact': exact_hash_to_path,
        'norm': norm_hash_to_path
    }
    safe_write(INDEX_FILE, json.dumps(cache))

# Try to load existing index
if INDEX_FILE.exists():
    try:
        with open(INDEX_FILE) as f:
            cache = json.load(f)
        exact_hash_to_path = cache.get('exact', {})
        norm_hash_to_path = cache.get('norm', {})
        print(f"Loaded cached hash index: {len(exact_hash_to_path)} files.")
    except:
        print("Corrupt cache, rebuilding...")
        build_hash_index()
else:
    print("Building hash index (this may take a minute)...")
    build_hash_index()

# Try to merge existing synthegration_index hash lookup
try:
    from synthegration_index import hash_to_path
    existing = hash_to_path()
    if isinstance(existing, dict):
        for h, path in existing.items():
            exact_hash_to_path[h] = path
        print("Merged synthegration_index hash map.")
except Exception:
    pass

# Build a reverse map for time-based lookup
file_mtimes = {}
for path_str in exact_hash_to_path.values():
    full_path = HOME / path_str
    if full_path.exists():
        file_mtimes[path_str] = full_path.stat().st_mtime

# -------------------------------------------------------------------
# 2. Stream conversations and write matches
# -------------------------------------------------------------------
export_dir = HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports"
conv_files = [
    export_dir / "deepseek_data-2026-05-26/conversations.json",
    export_dir / "deepseek_data-2026-05-17/conversations.json",
]
harvest_export = HOME / "deepseek_harvest_work/export.json"
if harvest_export.exists():
    conv_files.append(harvest_export)

delays = []
matches_count = 0

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
with open(MATCHES_FILE, 'w') as matches_fh:
    for conv_file in conv_files:
        if not conv_file.exists():
            continue
        print(f"Processing {conv_file.name}...")
        try:
            with open(conv_file) as f:
                data = json.load(f)
        except:
            print("  Failed to load, skipping.")
            continue

        conversations = data if isinstance(data, list) else [data]
        for conv in conversations:
            session_id = conv.get('id') or conv.get('title', 'unknown')
            mapping = conv.get('mapping', {})
            if not mapping:
                continue
            for node_id, node in mapping.items():
                msg_obj = node.get('message')
                if not isinstance(msg_obj, dict):
                    continue
                # timestamp
                ts = msg_obj.get('inserted_at')
                utc_ts = None
                if ts:
                    try:
                        dt = datetime.fromisoformat(str(ts).replace('Z','+00:00'))
                        utc_ts = dt.timestamp()
                    except:
                        pass
                # content from fragments
                fragments = msg_obj.get('fragments', [])
                full_content = ''
                for frag in fragments:
                    if isinstance(frag, dict):
                        full_content += frag.get('content', '') + '\n'

                for bi, block in enumerate(extract_blocks(full_content)):
                    h = sha256(block.strip())
                    nh = sha256(normalize(block))
                    # match
                    matched_path = exact_hash_to_path.get(h) or norm_hash_to_path.get(nh)
                    if not matched_path and utc_ts:
                        # time window backup
                        best = None
                        best_diff = float('inf')
                        for path, mtime in file_mtimes.items():
                            diff = abs(mtime - utc_ts)
                            if diff < best_diff:
                                best_diff = diff
                                best = path
                        if best_diff <= 2 * 86400:  # 2 days
                            matched_path = best
                    if matched_path:
                        match_entry = {
                            'file': matched_path,
                            'file_mtime_utc': datetime.fromtimestamp(file_mtimes.get(matched_path, 0), tz=timezone.utc).isoformat(),
                            'code_block': {
                                'hash': h,
                                'session': str(session_id),
                                'node_id': node_id,
                                'block_idx': bi,
                                'timestamp_utc': datetime.fromtimestamp(utc_ts, tz=timezone.utc).isoformat() if utc_ts else None,
                                'snippet': block[:200] + ('...' if len(block)>200 else '')
                            }
                        }
                        matches_fh.write(json.dumps(match_entry) + '\n')
                        matches_count += 1
                        if utc_ts:
                            delays.append(file_mtimes.get(matched_path, 0) - utc_ts)

print(f"Matches written: {matches_count}")

# -------------------------------------------------------------------
# 3. Final stats and summary
# -------------------------------------------------------------------
stats = {}
if delays:
    stats = {
        'count': len(delays),
        'min_seconds': min(delays),
        'max_seconds': max(delays),
        'mean_seconds': statistics.mean(delays),
        'median_seconds': statistics.median(delays)
    }
    print(f"Delay stats: min={stats['min_seconds']:.0f}s, max={stats['max_seconds']:.0f}s, mean={stats['mean_seconds']:.0f}s")

final_index = {
    'meta': {
        'source_files_indexed': len(exact_hash_to_path),
        'matches_total': matches_count,
        'delays': stats
    },
    'matches_file': str(MATCHES_FILE)
}
safe_write(FINAL_INDEX, json.dumps(final_index, indent=2))
print(f"Final index written to {FINAL_INDEX}")