#!/usr/bin/env python3
"""Fast function‑level provenance – hash‑first, difflib only within 2h, progress."""
import json, re, hashlib, difflib, sys, time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
PROV = HOME / "cli-synthegration/workspace/provenance/comprehensive_provenance.json"
MAX_DELAY_TIGHT = 2 * 3600
MAX_DELAY_LOOSE = 7 * 86400
SIMILARITY_FRAG = 0.6
MIN_LINES = 4

def sha256(text): return hashlib.sha256(text.encode()).hexdigest()

def extract_definitions(content):
    defs = []
    lines = content.splitlines()
    pat = re.compile(r'^(?P<indent>\s*)(def |class )(?P<name>\w+)')
    i = 0
    while i < len(lines):
        m = pat.match(lines[i])
        if m:
            name, indent = m.group('name'), m.group('indent')
            body_lines = [lines[i]]; i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == '': body_lines.append(nxt); i += 1; continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= len(indent) and nxt_indent > 0:
                    if re.match(r'^\s*(def |class |@)', nxt): break
                body_lines.append(nxt); i += 1
            body = '\n'.join(body_lines)
            if len(body_lines) >= MIN_LINES:
                defs.append((name, body, sha256(body.strip())))
        else: i += 1
    return defs

with open(PROV) as f: comp = json.load(f)
print(f"Loaded {len(comp)} files")

EXPORT_SOURCES = [
    (HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-26/conversations.json","2026"),
    (HOME / "storage/downloads/_doing/_1-build/DeepSeek/exports/deepseek_data-2026-05-17/conversations.json","2026"),
    (HOME / "deepseek_harvest_work/export.json","2025"),
]
code_blocks = []
for cf, era in EXPORT_SOURCES:
    if not cf.exists(): continue
    with open(cf) as f: data = json.load(f)
    for conv in (data if isinstance(data,list) else [data]):
        sid = conv.get('id') or conv.get('title','?')
        for nid, node in conv.get('mapping',{}).items():
            msg = node.get('message')
            if not isinstance(msg, dict): continue
            ts = msg.get('inserted_at'); utc_ts = None
            if ts:
                try: utc_ts = datetime.fromisoformat(str(ts).replace('Z','+00:00')).timestamp()
                except: pass
            content = ''
            for frag in msg.get('fragments',[]):
                if isinstance(frag, dict): content += frag.get('content','') + '\n'
            for bi, block in enumerate(re.findall(r"```(?:\w+)?\n(.*?)\n```", content, re.DOTALL)):
                code_blocks.append({'session':str(sid),'node_id':nid,'block_idx':bi,'timestamp_utc':utc_ts,'text':block,'hash':sha256(block.strip()),'era':era})
print(f"Code blocks: {len(code_blocks)}")

cb_by_hash = {}
for cb in code_blocks: cb_by_hash.setdefault(cb['hash'],[]).append(cb)

new_matches = 0; files_checked = 0; t_start = time.time()
for fname, versions in comp.items():
    if not fname.endswith('.py'): continue
    if any(v['strategy'] in ('hash','similarity') for v in versions): continue
    fpath = HOME / fname
    if not fpath.exists() or fpath.stat().st_size > 1_000_000: continue
    try: content = fpath.read_text()
    except: continue
    mtime = fpath.stat().st_mtime
    defs = extract_definitions(content)
    if not defs: continue
    files_checked += 1
    if files_checked % 5 == 0:
        elapsed = time.time()-t_start
        rate = files_checked/elapsed if elapsed>0 else 0
        print(f"  Fragment: {files_checked} files, {new_matches} matched")
    new_versions = []
    for def_name, def_body, def_hash in defs:
        best = None; best_delay = float('inf'); best_sim = 0.0
        if def_hash in cb_by_hash:
            for cb in cb_by_hash[def_hash]:
                if cb['timestamp_utc'] is None: continue
                delay = mtime - cb['timestamp_utc']
                if 0 <= delay <= MAX_DELAY_LOOSE and delay < best_delay:
                    best = cb; best_delay = delay; best_sim = 1.0
        if not best:
            for cb in code_blocks:
                if cb['timestamp_utc'] is None: continue
                delay = mtime - cb['timestamp_utc']
                if not (0 <= delay <= MAX_DELAY_TIGHT): continue
                sim = difflib.SequenceMatcher(None, def_body, cb['text']).ratio()
                if sim >= SIMILARITY_FRAG and delay < best_delay:
                    best = cb; best_delay = delay; best_sim = sim
        if best:
            new_versions.append({'strategy':'fragment','fragment':def_name,'session':best['session'],'node_id':best['node_id'],'block_idx':best['block_idx'],'timestamp_utc':datetime.fromtimestamp(best['timestamp_utc'],tz=timezone.utc).isoformat(),'delay_s':best_delay,'similarity':round(best_sim,3),'snippet':best['text'][:200],'era':best['era']})
    if new_versions:
        time_vers = [v for v in versions if v['strategy']=='time']
        comp[fname] = time_vers + new_versions
        new_matches += 1

with open(PROV,'w') as f: json.dump(comp, f, indent=2)
print(f"Fragment matches added to {new_matches} files. Index updated.")