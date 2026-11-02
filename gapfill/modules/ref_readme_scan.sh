#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
REFDIR=~/refTemplates
[ -d "$REFDIR" ] || exit 0
find "$REFDIR" -maxdepth 2 -name "README.md" | while read -r readme; do
    dir=$(dirname "$readme")
    toolname=$(basename "$dir")
    desc=$(grep -m1 '^#' "$readme" | sed 's/^#\+\s*//')
    echo "{\"name\":\"$toolname\",\"path\":\"$dir\",\"source\":\"refTemplates\",\"description\":\"$desc\"}"
done