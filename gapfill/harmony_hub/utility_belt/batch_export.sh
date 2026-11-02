#!/bin/bash
# Export all cached sessions that don't have an export yet
CACHE="$HOME/.deepcli/session_store"
EXPORTS="$HOME/storage/downloads/synthegration_exports"
count=0
for f in "$CACHE"/*.json; do
  sid=$(basename "$f" .json)
  if [ ! -d "$EXPORTS/$sid" ]; then
    echo "📤 Exporting $sid..."
    python3 "$HOME/cli-synthegration/synthegration_index.py" export "$sid" 2>/dev/null && count=$((count+1))
  fi
done
echo "✅ Exported $count new sessions."