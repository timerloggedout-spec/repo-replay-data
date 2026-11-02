#!/data/data/com.termux/files/usr/bin/bash
# Export code blocks from ALL live sessions or offline manifest
set -euo pipefail
OUT="${1:-$HOME/storage/downloads/synthegration_batch}"
mkdir -p "$OUT"

if [ "${2:-}" = "--offline" ] && [ -n "${3:-}" ]; then
    python3 ~/cli-synthegration/conv_explorer.py --offline "$3" --list | while read -r line; do
        sid=$(echo "$line" | cut -d'|' -f1 | tr -d ' ')
        [ -z "$sid" ] && continue
        echo "Exporting offline: $sid"
        python3 ~/cli-synthegration/conv_explorer.py --offline "$3" --export "$sid" --output "$OUT/$sid"
    done
else
    python3 ~/cli-synthegration/conv_explorer.py --list | head -100 | while read -r line; do
        sid=$(echo "$line" | cut -d'|' -f1 | tr -d ' ')
        [ -z "$sid" ] && continue
        echo "Exporting live: $sid"
        python3 ~/cli-synthegration/conv_explorer.py --export "$sid" --output "$OUT/$sid"
    done
fi
echo "Done: $OUT"