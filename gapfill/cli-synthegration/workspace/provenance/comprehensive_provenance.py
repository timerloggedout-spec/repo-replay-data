#!/usr/bin/env python3
"""
comprehensive_provenance.py – Multi‑strategy provenance with era tagging,
fragment matching, and message‑to‑message iteration timing.
"""
import json, sys, re, hashlib, statistics, difflib
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
MAX_DELAY = 7 * 86400          # 7 days before file mtime
SIMILARITY_WHOLE = 0.4         # whole‑file similarity threshold
SIMILARITY_FRAGMENT = 0.6      # fragment similarity threshold
MIN_FRAGMENT_LINES = 4

SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
# Exact directory names to skip
BLOAT_NAMES = {"node_modules","__pycache__",".cache",".git","dist",
               "codex","blobs","browser-data",".blob","logs","tmp",
               "target","release",".fingerprint","deps","build"}

def is_bloat(parts):
    return any(p in BLOAT_NAMES for p in parts)

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()
def norm_hash(text):
    return sha256('\n'.join(line.rstrip() for line in text.splitlines()))

# --- 1. Load all source files (whole content) ---
file_info = {}
for base in SOURCE_DIRS:
    for fp in (HOME / base).rglob('*'):
        if fp.is_file() and not is_bloat(fp.parts):
            if fp.stat().st_size > 1_000_000: continue
            try:
                content = fp.read_text()
                rel = str(fp.relative_to(HOME))
                file_info[rel] = {
                    'mtime': fp.stat().st_mtime,
                    'content': content,
                    'hash': sha256(content),
                    'norm_hash': norm_hash(content),
                    'is_python': fp.suffix == '.py'
                }
            except: pass
print(f"Loaded {len(file_info)} source files.")

# --- 2. Load code blocks from all exports, tag era ---
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
            for bi, block in enumerate(re.findall(r"```(?:\w+)?\n(.*?)\n```", content, re.DOTALL)):
                code_blocks.append({
                    'session': str(sid), 'node_id': nid, 'block_idx': bi,
                    'timestamp_utc': utc_ts, 'text': block,
                    'hash': sha256(block.strip()), 'norm_hash': norm_hash(block),
                    'era': era
                })
print(f"Code blocks extracted: {len(code_blocks)}")

# --- 3. Fragment extraction for Python files ---
def extract_definitions(content):
    defs = []
    lines = content.splitlines()
    pattern = r'^\s*(def |class )(\w+)'
    i = 0
    while i < len(lines):
        m = re.match(pattern, lines[i])
        if m:
            name = m.group(2)
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

# Pre‑compute fragments for Python files
file_fragments = {}
for fname, finfo in file_info.items():
    if finfo['is_python']:
        defs = extract_definitions(finfo['content'])
        if defs:
            file_fragments[fname] = defs
print(f"Python files with fragments: {len(file_fragments)}")

# --- 4. Multi‑strategy matching ---
file_versions = {}
for fname, finfo in file_info.items():
    mtime = finfo['mtime']
    fhash = finfo['hash']
    fnhash = finfo['norm_hash']
    versions = []

    # First pass: whole‑file exact/norm hash + similarity
    for cb in code_blocks:
        if cb['timestamp_utc'] is None: continue
        delay = mtime - cb['timestamp_utc']
        if 0 <= delay <= MAX_DELAY:
            matched = False
            sim = 0.0
            if cb['hash'] == fhash or cb['norm_hash'] == fnhash:
                matched = True
                sim = 1.0
            else:
                # Quick line‑count filter
                fl = len(finfo['content'].splitlines())
                bl = len(cb['text'].splitlines())
                if max(fl, bl) / (min(fl, bl) + 1) <= 4:
                    sim = difflib.SequenceMatcher(None, finfo['content'], cb['text']).ratio()
                    matched = sim >= SIMILARITY_WHOLE
            if matched:
                versions.append({
                    'strategy': 'hash' if sim == 1.0 else 'similarity',
                    'session': cb['session'], 'node_id': cb['node_id'],
                    'block_idx': cb['block_idx'],
                    'timestamp_utc': datetime.fromtimestamp(cb['timestamp_utc'], tz=timezone.utc).isoformat(),
                    'delay_s': delay, 'similarity': round(sim, 3),
                    'snippet': cb['text'][:200], 'era': cb['era']
                })

    # Second pass: fragment matching for Python files
    if fname in file_fragments and len(versions) == 0:
        for def_name, def_body in file_fragments[fname]:
            for cb in code_blocks:
                if cb['timestamp_utc'] is None: continue
                delay = mtime - cb['timestamp_utc']
                if 0 <= delay <= MAX_DELAY:
                    sim = difflib.SequenceMatcher(None, def_body, cb['text']).ratio()
                    if sim >= SIMILARITY_FRAGMENT:
                        versions.append({
                            'strategy': 'fragment',
                            'fragment': def_name,
                            'session': cb['session'], 'node_id': cb['node_id'],
                            'block_idx': cb['block_idx'],
                            'timestamp_utc': datetime.fromtimestamp(cb['timestamp_utc'], tz=timezone.utc).isoformat(),
                            'delay_s': delay, 'similarity': round(sim, 3),
                            'snippet': cb['text'][:200], 'era': cb['era']
                        })
                        break  # one match per fragment is enough

    # Third pass: if still nothing, keep the time‑window best (from tight_provenance logic)
    if not versions:
        best_delay = float('inf')
        best_cb = None
        for cb in code_blocks:
            if cb['timestamp_utc'] is None: continue
            delay = mtime - cb['timestamp_utc']
            if 0 <= delay <= MAX_DELAY and delay < best_delay:
                best_delay = delay
                best_cb = cb
        if best_cb:
            versions.append({
                'strategy': 'time',
                'session': best_cb['session'], 'node_id': best_cb['node_id'],
                'block_idx': best_cb['block_idx'],
                'timestamp_utc': datetime.fromtimestamp(best_cb['timestamp_utc'], tz=timezone.utc).isoformat(),
                'delay_s': best_delay, 'similarity': 0.0,
                'snippet': best_cb['text'][:200], 'era': best_cb['era']
            })

    if versions:
        versions.sort(key=lambda v: v['delay_s'])
        file_versions[fname] = versions

print(f"Files with provenance: {len(file_versions)}")

# --- 5. Message‑to‑message intervals (iteration speed) ---
session_intervals = []
for fname, versions in file_versions.items():
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
    median_int = statistics.median(session_intervals)
    print(f"Message‑to‑message intervals: median {median_int:.0f}s (n={len(session_intervals)})")
else:
    median_int = None

# --- 6. Save outputs ---
with open(OUT / "comprehensive_provenance.json", 'w') as f:
    json.dump(file_versions, f, indent=2)

stats = {
    'files_with_provenance': len(file_versions),
    'strategies': {
        'hash': sum(1 for v in file_versions.values() if v[0]['strategy'] == 'hash'),
        'similarity': sum(1 for v in file_versions.values() if v[0]['strategy'] == 'similarity'),
        'fragment': sum(1 for v in file_versions.values() if v[0]['strategy'] == 'fragment'),
        'time': sum(1 for v in file_versions.values() if v[0]['strategy'] == 'time'),
    },
    'message_interval_median_s': median_int,
    'interpretation': f"Median {median_int:.0f}s between successive code blocks in the same session."
}
with open(OUT / "comprehensive_stats.json", 'w') as f:
    json.dump(stats, f, indent=2)

print("Comprehensive provenance saved to comprehensive_provenance.json")
print("Stats saved to comprehensive_stats.json")