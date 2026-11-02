#!/usr/bin/env python3
"""Print random samples from tight_provenance.json for manual verification."""
import json, random
from pathlib import Path

PROV = Path.home() / "cli-synthegration/workspace/provenance/tight_provenance.json"
with open(PROV) as f:
    data = json.load(f)

items = list(data.items())
random.shuffle(items)
print("=== Sample matches ===")
for fname, entry in items[:15]:
    delay = entry.get('delay_seconds', '?')
    delay_str = f"{delay:.0f}s" if isinstance(delay, (int,float)) else "?"
    session = entry.get('session','?')[:30]
    snippet = entry.get('snippet','')[:80].replace('\n',' ')
    print(f"File: {fname}")
    print(f"  Session: {session}  |  Delay: {delay_str}")
    print(f"  Snippet: {snippet}...")
    print()