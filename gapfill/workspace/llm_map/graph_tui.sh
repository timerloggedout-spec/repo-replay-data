#!/bin/bash
MAP_DIR=~/workspace/llm_map
cd "$MAP_DIR"
while true; do
  CHOICE=$(python3 -c "
import json
with open('deps.jsonl') as f:
    edges = [json.loads(l) for l in f]
files = list(set(e['from'] for e in edges))
for i, f in enumerate(sorted(files)[:50]):
    print(f'{i} {f}')
" | dialog --menu "Pick a file to see its dependencies" 20 80 20 --stdout)
  [ -z "$CHOICE" ] && break
  FILE=$(echo "$CHOICE" | awk '{print $2}')
  python3 llm_mapper_pro.py graph-tree "$FILE" | dialog --textbox - 20 80
done