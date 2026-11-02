import re, json, hashlib, sys
from pathlib import Path

def extract_blocks(text):
    fence = re.compile(r"```(\w*)\s*\n(.*?)```", re.DOTALL)
    blocks = []
    for m in fence.finditer(text):
        lang = m.group(1) or "text"
        code = m.group(2).rstrip("\n")
        if not code.strip():
            continue
        blocks.append({
            "lang": lang,
            "code": code,
            "hash": hashlib.sha256(code.encode()).hexdigest()[:12]
        })
    return blocks

def process_file(path):
    with open(path) as f:
        data = json.load(f)
    def strings(obj):
        if isinstance(obj, str):
            yield obj
        elif isinstance(obj, dict):
            for v in obj.values():
                yield from strings(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from strings(v)
    all_blocks = []
    for s in strings(data):
        all_blocks.extend(extract_blocks(s))
    return all_blocks

if __name__ == "__main__":
    path = sys.argv[1]
    blocks = process_file(path)
    json.dump(blocks, sys.stdout, indent=2)