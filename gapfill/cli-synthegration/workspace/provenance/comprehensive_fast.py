#!/usr/bin/env python3
"""
comprehensive_fast.py – Robust, checkpointed, progress‑reporting provenance.
Strips heredoc wrappers from code blocks before hashing.
Writes results incrementally; resumes from checkpoint.
"""
import json, sys, re, hashlib, statistics, difflib, os, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
INDEX_FILE = OUT / "hash_index.json"
CHECKPOINT = OUT / ".comprehensive_checkpoint.json"
OUTPUT_JSONL = OUT / "comprehensive_provenance.jsonl"
FINAL_JSON = OUT / "comprehensive_provenance.json"
STATS_JSON = OUT / "comprehensive_stats.json"

MAX_DELAY_TIGHT = 4 * 3600       # 4h similarity window
MAX_DELAY_LOOSE = 7 * 86400      # 7d time fallback
SIMILARITY_WHOLE = 0.4

SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT_NAMES = {"node_modules","__pycache__",".cache",".git","dist",
               "codex","blobs","browser-data",".blob","logs","tmp",
               "target","release",".fingerprint","deps","build"}

def is_bloat(parts):
    return any(p in BLOAT_NAMES for p in parts)
def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()
def norm_hash(text):
    return sha256('\n'.join(line.rstrip() for line in text.splitlines()))

# --- Heredoc stripper: extract the actual file content ---
HEREDOC_RE = re.compile(
    r"(?:cat|tee)\s+(?:>>?\s+)?\S+\s*<<\s*'?(\w+)'?\s*\n(.*?)\n\1",
    re.DOTALL
)
def strip_heredoc(text):
    """If the code block is a heredoc, return the inner content. Otherwise original."""
    m = HEREDOC_RE.search(text)
    if m:
        return m.group(2)
    # Also try: the entire block might be the inner content of a heredoc
    # (some blocks have the wrapper stripped by the conversation export)
    return text

# --- 1. Load hash index ---
if not INDEX_FILE.exists():
    print("Hash index missing. Run final_provenance.py first.")
    sys.exit(1)
with open(INDEX_FILE) as f:
    cache = json.load(f)
exact_hashes = cache.get('exact', {})
norm_hashes = cache.get('norm', {})
hash_to_file = {}
for h, path in exact_hashes.items():
    hash_to_file[h] = path
for h, path in norm_hashes.items():
    if h not in hash_to_file:
        hash_to_file[h] = path
print(f"Hash index: {len(exact_hashes)} entries")

# --- 2. Load source file mtimes ---
file_mtimes = {}
for base in SOURCE_DIRS:
    for fp in (HOME / base).rglob('*'):
        if fp.is_file() and not is_bloat(fp.parts):
            if fp.stat().st_size > 1_000_000: continue
            file_mtimes[str(fp.relative_to(HOME))] = fp.stat().st_mtime
n_files = len(file_mtimes)
print(f"Source files: {n_files}")

# --- 3. Extract code blocks with heredoc-stripped content ---
EXPORT_SOURCES = [
    (HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-26/conversations.json", "2026"),
    (HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-17/conversations.json", "2026"),
    (HOME / "deepseek_harvest_work/export.json", "2025"),
]
code_blocks = []
for cf, era in EXPORT_SOURCES:
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
            for bi, block_text in enumerate(re.findall(r"```(?:\w+)?\n(.*?)\n```", content, re.DOTALL)):
                inner = strip_heredoc(block_text)
                code_blocks.append({
                    'session': str(sid), 'node_id': nid, 'block_idx': bi,
                    'timestamp_utc': utc_ts, 'text': block_text,
                    'inner': inner,
                    'hash': sha256(inner.strip()),
                    'norm_hash': norm_hash(inner),
                    'era': era
                })
n_cb = len(code_blocks)
print(f"Code blocks: {n_cb}")

# --- 4. Resume from checkpoint if exists ---
file_versions = {}  # fname -> list of version dicts
processed = set()
if CHECKPOINT.exists():
    try:
        with open(CHECKPOINT) as f:
            ck = json.load(f)
        file_versions = ck.get('file_versions', {})
        processed = set(ck.get('processed_files', []))
        print(f"Resumed from checkpoint: {len(file_versions)} files done, {len(processed)} processed")
    except:
        print("Corrupt checkpoint, starting fresh.")

# --- 5. Pass 1: hash match (instant, with stripped heredoc) ---
unmatched = set(file_mtimes.keys()) - processed
new_hash_matches = 0
t_start = time.time()
for i, cb in enumerate(code_blocks):
    if i % 500 == 0 and i > 0:
        elapsed = time.time() - t_start
        rate = i / elapsed
        remaining = (n_cb - i) / rate if rate > 0 else 0
        print(f"  Hash pass: {i}/{n_cb} blocks ({i*100//n_cb}%), {rate:.0f} blk/s, ~{remaining:.0f}s left")
    if cb['timestamp_utc'] is None: continue
    matched_path = hash_to_file.get(cb['hash']) or hash_to_file.get(cb['norm_hash'])
    if not matched_path or matched_path not in unmatched: continue
    mtime = file_mtimes.get(matched_path)
    if not mtime: continue
    delay = mtime - cb['timestamp_utc']
    if 0 <= delay <= MAX_DELAY_LOOSE:
        versions = file_versions.setdefault(matched_path, [])
        versions.append({
            'strategy': 'hash', 'session': cb['session'], 'node_id': cb['node_id'],
            'block_idx': cb['block_idx'],
            'timestamp_utc': datetime.fromtimestamp(cb['timestamp_utc'], tz=timezone.utc).isoformat(),
            'delay_s': delay, 'similarity': 1.0, 'snippet': cb['inner'][:200], 'era': cb['era']
        })
        unmatched.discard(matched_path)
        new_hash_matches += 1
        processed.add(matched_path)
        # Incremental JSONL write
        with open(OUTPUT_JSONL, 'a') as f:
            f.write(json.dumps({matched_path: versions}) + '\n')
print(f"Hash‑matched: {new_hash_matches} new, {len(file_versions)} total files.")

# --- Checkpoint after hash pass ---
with open(CHECKPOINT, 'w') as f:
    json.dump({'file_versions': file_versions, 'processed_files': list(processed)}, f)

# --- 6. Pass 2: similarity for remaining unmatched (4h window) ---
if unmatched:
    # Load content for unmatched
    unmatched_list = sorted(unmatched)
    total_un = len(unmatched_list)
    new_sim_matches = 0
    t_start = time.time()
    for idx, fname in enumerate(unmatched_list):
        if idx % 10 == 0:
            elapsed = time.time() - t_start
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            remaining = (total_un - idx) / rate if rate > 0 else 0
            print(f"  Sim pass: {idx}/{total_un} files, ~{remaining:.0f}s left")
        fpath = HOME / fname
        if not fpath.exists() or fpath.stat().st_size > 1_000_000: continue
        try:
            content = fpath.read_text()
        except:
            continue
        mtime = file_mtimes[fname]
        best, best_delay, best_sim = None, float('inf'), 0
        for cb in code_blocks:
            if cb['timestamp_utc'] is None: continue
            delay = mtime - cb['timestamp_utc']
            if not (0 <= delay <= MAX_DELAY_TIGHT): continue
            fl, bl = len(content.splitlines()), len(cb['inner'].splitlines())
            if max(fl, bl) / (min(fl, bl) + 1) > 4: continue
            sim = difflib.SequenceMatcher(None, content, cb['inner']).ratio()
            if sim >= SIMILARITY_WHOLE and delay < best_delay:
                best, best_delay, best_sim = cb, delay, sim
        if best:
            file_versions[fname] = [{
                'strategy': 'similarity', 'session': best['session'], 'node_id': best['node_id'],
                'block_idx': best['block_idx'],
                'timestamp_utc': datetime.fromtimestamp(best['timestamp_utc'], tz=timezone.utc).isoformat(),
                'delay_s': best_delay, 'similarity': round(best_sim, 3),
                'snippet': best['inner'][:200], 'era': best['era']
            }]
            unmatched.discard(fname)
            processed.add(fname)
            new_sim_matches += 1
            with open(OUTPUT_JSONL, 'a') as f:
                f.write(json.dumps({fname: file_versions[fname]}) + '\n')
            # Checkpoint every 50
            if new_sim_matches % 50 == 0:
                with open(CHECKPOINT, 'w') as f:
                    json.dump({'file_versions': file_versions, 'processed_files': list(processed)}, f)
    print(f"Similarity‑matched: {new_sim_matches} new, {len(file_versions)} total.")

# --- 7. Pass 3: time fallback for the rest ---
for fname in sorted(unmatched):
    mtime = file_mtimes[fname]
    best, best_delay = None, float('inf')
    for cb in code_blocks:
        if cb['timestamp_utc'] is None: continue
        delay = mtime - cb['timestamp_utc']
        if 0 <= delay <= MAX_DELAY_LOOSE and delay < best_delay:
            best, best_delay = cb, delay
    if best:
        file_versions[fname] = [{
            'strategy': 'time', 'session': best['session'], 'node_id': best['node_id'],
            'block_idx': best['block_idx'],
            'timestamp_utc': datetime.fromtimestamp(best['timestamp_utc'], tz=timezone.utc).isoformat(),
            'delay_s': best_delay, 'similarity': 0.0,
            'snippet': best['inner'][:200], 'era': best['era']
        }]
        processed.add(fname)
        with open(OUTPUT_JSONL, 'a') as f:
            f.write(json.dumps({fname: file_versions[fname]}) + '\n')

print(f"Final files with provenance: {len(file_versions)}")

# --- 8. Message‑to‑message intervals ---
session_intervals = []
for versions in file_versions.values():
    by_session = {}
    for v in versions:
        by_session.setdefault(v['session'], []).append(v)
    for sv in by_session.values():
        sv.sort(key=lambda v: v['timestamp_utc'])
        for i in range(1, len(sv)):
            t0 = datetime.fromisoformat(sv[i-1]['timestamp_utc']).timestamp()
            t1 = datetime.fromisoformat(sv[i]['timestamp_utc']).timestamp()
            if t1 - t0 > 0:
                session_intervals.append(t1 - t0)

median_int = statistics.median(session_intervals) if session_intervals else None

# --- 9. Write final outputs ---
with open(FINAL_JSON, 'w') as f:
    json.dump(file_versions, f, indent=2)
stats = {
    'files_with_provenance': len(file_versions),
    'strategies': {
        'hash': sum(1 for v in file_versions.values() if v[0]['strategy'] == 'hash'),
        'similarity': sum(1 for v in file_versions.values() if v[0]['strategy'] == 'similarity'),
        'time': sum(1 for v in file_versions.values() if v[0]['strategy'] == 'time'),
    },
    'message_interval_median_s': median_int,
    'total_code_blocks': n_cb,
    'total_source_files': n_files,
}
with open(STATS_JSON, 'w') as f:
    json.dump(stats, f, indent=2)
# Clear checkpoint on success
CHECKPOINT.unlink(missing_ok=True)

print("\n=== Complete ===")
print(f"Files: {len(file_versions)} ({stats['strategies']})")
if median_int:
    print(f"Message‑to‑message median: {median_int:.0f}s (n={len(session_intervals)})")