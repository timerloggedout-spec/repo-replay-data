#!/usr/bin/env python3
"""Sample current matches and optionally re‑match with tunable parameters."""
import json, sys, random, hashlib, re, difflib, statistics
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
OUT = HOME / "cli-synthegration/workspace/provenance"
TRUE_VERSIONS = OUT / "true_versions.json"

# --- Print samples ---
if TRUE_VERSIONS.exists():
    with open(TRUE_VERSIONS) as f:
        data = json.load(f)
    items = list(data.items())
    print(f"Current true matches: {len(items)}")
    random.shuffle(items)
    print("=== Sample matches ===")
    for fname, versions in items[:8]:
        first = versions[0]
        delay = first['delay_s']
        snippet = first['snippet'][:80].replace('\n',' ')
        print(f"File: {fname}")
        print(f"  Session: {first['session'][:30]}  |  Delay: {delay:.0f}s  |  Iterations: {len(versions)}")
        print(f"  Snippet: {snippet}...")
        print()
else:
    print("No true_versions.json found. Run true_versions_fast.py first.")
    sys.exit(1)

# --- Optionally re‑match with different settings ---
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--similarity', type=float, default=0.6, help='Similarity threshold (0-1)')
parser.add_argument('--max-delay', type=int, default=6*3600, help='Max delay seconds (default 6h)')
parser.add_argument('--re-run', action='store_true', help='Actually re‑run matching')
args = parser.parse_args()

if not args.re_run:
    print("\nTo re‑match with different thresholds, run:")
    print(f"  python3 tune_and_sample.py --re-run --similarity {args.similarity} --max-delay {args.max_delay}")
else:
    print(f"\nRe‑matching with similarity={args.similarity}, max_delay={args.max_delay}s...")
    # (same logic as true_versions_fast.py, but with parameters)
    SOURCE_DIRS = [
        "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
        "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
        "chronos_checkout"
    ]
    BLOAT_PARTS = {"node_modules","__pycache__",".cache",".git","dist",
                   "codex","blobs","browser-data",".blob","logs","tmp",
                   "target","release",".fingerprint","deps","build"}
    def sha256(text): return hashlib.sha256(text.encode()).hexdigest()
    def normalize(text): return '\n'.join(line.rstrip() for line in text.splitlines())
    def is_bloat(parts): return any(p in BLOAT_PARTS for p in parts)

    file_info = {}
    for base in SOURCE_DIRS:
        for fp in (HOME / base).rglob('*'):
            if fp.is_file() and not is_bloat(fp.parts):
                if fp.stat().st_size > 1_000_000: continue
                try:
                    content = fp.read_text()
                    file_info[str(fp.relative_to(HOME))] = {
                        'mtime': fp.stat().st_mtime,
                        'content': content,
                        'hash': sha256(content),
                        'norm_hash': sha256(normalize(content))
                    }
                except: pass
    print(f"Files: {len(file_info)}")

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
                        'hash': sha256(block.strip()), 'norm_hash': sha256(normalize(block))
                    })
    print(f"Code blocks: {len(code_blocks)}")

    file_versions = {}
    for fname, finfo in file_info.items():
        versions = []
        for cb in code_blocks:
            if cb['timestamp_utc'] is None: continue
            delay = finfo['mtime'] - cb['timestamp_utc']
            if 0 <= delay <= args.max_delay:
                if cb['hash'] == finfo['hash'] or cb['norm_hash'] == finfo['norm_hash']:
                    matched = True
                    sim = 1.0
                else:
                    # Quick line count filter
                    fl = len(finfo['content'].splitlines())
                    bl = len(cb['text'].splitlines())
                    if max(fl,bl)/(min(fl,bl)+1) > 3: continue
                    sim = difflib.SequenceMatcher(None, finfo['content'], cb['text']).ratio()
                    matched = sim >= args.similarity
                if matched:
                    versions.append({
                        'session': cb['session'], 'node_id': cb['node_id'],
                        'block_idx': cb['block_idx'],
                        'timestamp_utc': datetime.fromtimestamp(cb['timestamp_utc'], tz=timezone.utc).isoformat(),
                        'delay_s': delay, 'similarity': round(sim,3), 'hash': cb['hash'], 'snippet': cb['text'][:200]
                    })
        if versions:
            versions.sort(key=lambda v: v['delay_s'])
            file_versions[fname] = versions

    with open(OUT / "true_versions.json", 'w') as f:
        json.dump(file_versions, f, indent=2)
    print(f"Updated true_versions.json: {len(file_versions)} files")
    if file_versions:
        first_delays = [v[0]['delay_s'] for v in file_versions.values()]
        print(f"First-write median: {statistics.median(first_delays):.0f}s")