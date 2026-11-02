#!/bin/bash
PROV_FILE="$HOME/cli-synthegration/workspace/provenance/real_provenance.json"
if [ ! -f "$PROV_FILE" ]; then
    PROV_FILE="$HOME/cli-synthegration/workspace/provenance/true_file_provenance.json"
fi
if [ ! -f "$PROV_FILE" ]; then
    echo "No provenance file found."
    exit 1
fi
echo "=== Provenance Viewer ==="
echo "Format: file | session | delay"
echo ""
python3 -c "
import json
with open('$PROV_FILE') as f:
    data = json.load(f)
for fname, entry in data.items():
    delay = entry.get('delay_seconds')
    delay_str = f'{delay:.0f}s' if delay is not None else 'N/A'
    print(f'{fname} | {entry.get(\"session\",\"?\")} | {delay_str}')
" | less