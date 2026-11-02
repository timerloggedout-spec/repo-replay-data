#!/usr/bin/env python3
"""
fragment_matcher.py – Function‑level provenance for Python files.
Fixes the regex and merges fragment matches into the comprehensive index.
"""
import json, re, hashlib, difflib, sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
PROV = HOME / "cli-synthegration/workspace/provenance/comprehensive_provenance.json"
HASH_INDEX = HOME / "cli-synthegration/workspace/provenance/hash_index.json"
OUT = HOME / "cli-synthegration/workspace/provenance/comprehensive_provenance.json"

MAX_DELAY = 7 * 86400
SIMILARITY_FRAG = 0.7
MIN_LINES = 3

SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT = {"node_modules","__pycache__",".cache",".git","dist","codex","blobs","browser-data",".blob","logs","tmp","target","release",".fingerprint","deps","build"}

def is_bloat(parts):
    return any(p in BLOAT for p in parts)

def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

# --- Extract functions/classes reliably ---
def extract_definitions(content):
    """Return list of (name, body) for top-level defs and classes."""
    defs = []
    lines = content.splitlines()
    pattern = re.compile(r'^(?P<indent>\s*)(def |class )(?P<name>\w+)')
    i = 0
    while i < len(lines):
        m = pattern.match(lines[i])
        if m:
            name = m.group('name')
            indent = m.group('indent')
            body_lines = [lines[i]]
            i += 1
            # capture until line with same or less indent (that is not just whitespace)
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == '':
                    body_lines.append(nxt)
                    i += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= len(indent):
                    # check if it's a new top-level def/class
                    if re.match(r'^\s*(def |class |@)', nxt) or nxt_indent == 0:
                        break
                body_lines.append(nxt)
                i += 1
            body = '\n'.join(body_lines)
            if len(body_lines) >= MIN_LINES:
                defs.append((name, body))
        else:
            i += 1
    return defs

# --- Load comprehensive provenance ---
with open(PROV) as f:
    comp = json.load(f)
print(f"Loaded {len(comp)} files in comprehensive index.")

# --- Load hash index for fast path ---
with open(HASH_INDEX) as f:
    cache = json.load(f)
exact = cache.get('exact', {})
norm = cache.get('norm', {})
hash_to_file = {}
for h, path in exact.items():
    hash_to_file[h] = path
for h, path in norm.items():
    if h not in hash_to_file:
        hash_to_file[h] = path

# --- Extract code blocks from all sessions (same as comprehensive) ---
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
                inner = block  # we'll hash the raw block; strip heredoc later if needed
                code_blocks.append({
                    'session': str(sid), 'node_id': nid, 'block_idx': bi,
                    'timestamp_utc': utc_ts, 'text': block,
                    'hash': sha256(block.strip()), 'era': era
                })
print(f"Code blocks: {len(code_blocks)}")

# --- Fragment matching for Python files not yet matched ---
new_fragment_matches = 0
for fname, versions in comp.items():
    if not fname.endswith('.py'):
        continue
    # Check if already has a hash or similarity match (skip time-only ones that are uncertain)
    if any(v['strategy'] in ('hash','similarity') for v in versions):
        continue
    # Load file content
    fpath = HOME / fname
    if not fpath.exists() or fpath.stat().st_size > 1_000_000:
        continue
    try:
        content = fpath.read_text()
    except:
        continue
    mtime = fpath.stat().st_mtime
    defs = extract_definitions(content)
    if not defs:
        continue
    # For each function, try to find a matching code block
    new_versions = []
    for def_name, def_body in defs:
        best = None
        best_delay = float('inf')
        best_sim = 0.0
        for cb in code_blocks:
            if cb['timestamp_utc'] is None: continue
            delay = mtime - cb['timestamp_utc']
            if 0 <= delay <= MAX_DELAY:
                sim = difflib.SequenceMatcher(None, def_body, cb['text']).ratio()
                if sim >= SIMILARITY_FRAG and delay < best_delay:
                    best = cb
                    best_delay = delay
                    best_sim = sim
        if best:
            new_versions.append({
                'strategy': 'fragment',
                'fragment': def_name,
                'session': best['session'],
                'node_id': best['node_id'],
                'block_idx': best['block_idx'],
                'timestamp_utc': datetime.fromtimestamp(best['timestamp_utc'], tz=timezone.utc).isoformat(),
                'delay_s': best_delay,
                'similarity': round(best_sim, 3),
                'snippet': best['text'][:200],
                'era': best['era']
            })
    if new_versions:
        # Merge with existing time matches, preferring fragment evidence
        # We'll replace the time-only versions with fragment versions if any
        time_versions = [v for v in versions if v['strategy'] == 'time']
        comp[fname] = time_versions + new_versions  # keep time as fallback, but fragment first
        new_fragment_matches += 1

# Save updated comprehensive index
with open(OUT, 'w') as f:
    json.dump(comp, f, indent=2)
print(f"Fragment matches added to {new_fragment_matches} files.")
print(f"Comprehensive index updated.")