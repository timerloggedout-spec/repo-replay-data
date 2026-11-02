import os, hashlib, sys
from collections import defaultdict

def hash_file(fpath):
    """Return SHA256 hex digest or None if file too large/error."""
    try:
        if os.path.getsize(fpath) > 10 * 1024 * 1024:  # skip >10MB
            return None
        h = hashlib.sha256()
        with open(fpath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except:
        return None

def scan_dir(path):
    """Return dict: hash -> list of relative file paths."""
    hmap = defaultdict(list)
    for root, dirs, files in os.walk(path):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, path)
            h = hash_file(full)
            if h:
                hmap[h].append(rel)
    return hmap

if len(sys.argv) != 3:
    print("Usage: python cmp_dirs.py <dir1> <dir2>")
    sys.exit(1)
a, b = sys.argv[1], sys.argv[2]
print(f"Scanning {a} ...")
ha = scan_dir(a)
print(f"Scanning {b} ...")
hb = scan_dir(b)

# Cross reference
print("\nIdentical files (by SHA256):")
for h in ha:
    if h in hb:
        for fa in ha[h]:
            for fb in hb[h]:
                print(f"  {a}/{fa}")
                print(f"  {b}/{fb}")
                print()