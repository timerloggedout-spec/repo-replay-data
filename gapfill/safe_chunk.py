import json, subprocess, gzip, sys
from pathlib import Path

def safe_chunk(input_file, output_dir):
    input_path = Path(input_file).expanduser()
    out_dir = Path(output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}

    # Stream every key-value pair as a single JSON object per line
    proc = subprocess.Popen(
        ['jq', '-c', 'to_entries[]', str(input_path)],
        stdout=subprocess.PIPE,
        text=True
    )

    count = 0
    for line in proc.stdout:
        entry = json.loads(line)
        key = entry['key']
        value = entry['value']
        key_clean = str(key).replace('/', '_').replace(' ', '_')[:80]
        chunk_path = out_dir / f'{key_clean}.json.gz'
        with gzip.open(chunk_path, 'wb') as gf:
            gf.write(json.dumps(value, indent=2).encode())
        sz = chunk_path.stat().st_size
        manifest[key] = {"file": str(chunk_path), "size": sz}
        count += 1
        if count % 100 == 0:
            print(f"  {count} keys chunked …", end='\r')

    proc.wait()
    with open(out_dir / 'chunks.idx.json', 'w') as mf:
        json.dump(manifest, mf, indent=2)
    print(f"\n✅ {count} chunks written to {out_dir}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 safe_chunk.py <source.json> <output_dir>")
        sys.exit(1)
    safe_chunk(sys.argv[1], sys.argv[2])