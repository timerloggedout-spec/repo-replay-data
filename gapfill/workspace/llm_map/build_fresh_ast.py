import json, hashlib, re
from pathlib import Path
from collections import defaultdict

HOME = Path.home()
WS = HOME / 'workspace/llm_map'

# Load bloat list (now updated)
bloat_set = set()
with open(HOME/'cli-synthegration/workspace/caveman_map/bloat_exclusions.lst') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('*'):
            bloat_set.add(line)

# Load central index (with bloat flags already)
central = []
with open(WS/'step5_bloat.jsonl') as f:
    for line in f:
        try: central.append(json.loads(line))
        except: pass
file_paths = {e['path'] for e in central}

# Parse map_final_with_watch.sh output: lines like "file.py: def func(...)"
ast_snippets = {}
ast_files = defaultdict(list)
sig_line = re.compile(r'^(.+?):\s*(def |async function |function |class )')

with open(WS/'full_map_output.txt', errors='ignore') as f:
    for line in f:
        line = line.strip()
        m = sig_line.match(line)
        if not m:
            continue
        rel_path = m.group(1)
        # Make sure path is relative
        if rel_path.startswith('./'):
            rel_path = rel_path[2:]
        elif rel_path.startswith(HOME.as_posix()):
            rel_path = str(Path(rel_path).relative_to(HOME))
        if rel_path not in file_paths:
            continue
        text = line.split(':', 1)[1].strip()
        h = hashlib.sha256(text.encode()).hexdigest()[:8]
        ast_snippets[h] = text
        ast_files[rel_path].append(h)

# Enrich central
for e in central:
    fp = e['path']
    hashes = ast_files.get(fp, [])
    e['ast_hashes'] = hashes
    e['ast_summary'] = '; '.join(ast_snippets[h].split('\n')[0][:40] for h in hashes[:3]) if hashes else ''

# Save snippets
with open(WS/'ast_snippets.json','w') as f:
    json.dump(ast_snippets, f, indent=2)

# Rebuild final compact index (same as before but with AST)
graph = {}
if (WS/'file_graph.json').exists():
    with open(WS/'file_graph.json') as f:
        graph = json.load(f)

dependents_map = defaultdict(set)
for src, deps in graph.items():
    for dep in deps:
        dependents_map[dep].add(src)

final = []
for e in central:
    fp = e['path']
    deps = graph.get(fp, [])[:5]
    dep_count = len(dependents_map.get(fp, set()))
    entry = {
        'p': fp, 's': e['size'], 'l': e.get('lang','?'),
        'h': e.get('sha','')[:8], 'b': e.get('bloat', False),
        'ts': e.get('session',''), 'as': e.get('ast_summary','')[:80],
        'ah': e.get('ast_hashes', [])[:3],
        'fr': len(e.get('fragments', [])),
        'vr': len(e.get('versions', [])),
        'd': deps, 'by': dep_count
    }
    final.append(entry)

final.sort(key=lambda x: (x['b'], -x['by'], x['p']))

with open(WS/'llm_index_compact.jsonl','w') as f:
    for rec in final:
        f.write(json.dumps(rec, ensure_ascii=False)+'\n')

# Update CAVEMAN_INDEX.md
top = final[:15]
md = f"""# Caveman Ecosystem – LLM Index v4.0

**{len(central)} files** indexed. **{len(graph)}** files with dependency edges. **{len(ast_snippets)}** AST signatures. **{sum(1 for e in central if e.get('session'))}** time‑correlated. **{sum(1 for e in central if e['bloat'])}** bloat‑flagged.

## Projects (>10 files)
"""
dir_counts = defaultdict(int)
for e in central:
    root = e['path'].split('/')[0]
    if not root.startswith('.'): dir_counts[root] += 1
for d,c in sorted(dir_counts.items(), key=lambda x:-x[1])[:15]:
    md += f"- `{d}/` ({c})\n"

md += "\n## Most‑Used Files\n"
for e in top:
    md += f"- `{e['p']}` (used by {e['by']})"
    if e['as']: md += f" – {e['as'][:60]}"
    md += "\n"

md += "\n## AST Signatures\n"
md += f"- {sum(1 for e in final if e['ah'])} files have AST hash pointers.\n"
md += "- Snippet dict: `ast_snippets.json`.\n"

with open(WS/'CAVEMAN_INDEX.md','w') as f:
    f.write(md)

print(f"✅ Index rebuilt with {len(ast_snippets)} AST snippets.")
print(f"   llm_index_compact.jsonl: {len(final)} entries")
print(f"   CAVEMAN_INDEX.md updated")