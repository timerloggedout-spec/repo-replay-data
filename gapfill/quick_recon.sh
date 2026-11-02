#!/usr/bin/env bash
out="quick_intel.txt"
: > "$out"
for item in *; do
  if [ -d "$item/.git" ]; then
    echo "### $item" >> "$out"
    pushd "$item" > /dev/null
    # Remote
    remote=$(git config --get remote.origin.url 2>/dev/null || echo "NO_REMOTE")
    echo "REMOTE: $remote" >> "$out"
    # README: line count + first 20 lines
    readme=$(find . -maxdepth 1 -iname "readme*" -print -quit)
    if [ -n "$readme" ]; then
      lines=$(wc -l < "$readme")
      echo "README_LINES: $lines" >> "$out"
      echo "README_FIRST_20:" >> "$out"
      head -20 "$readme" >> "$out"
      # Extract headers (##, ###, etc.)
      echo "README_HEADERS:" >> "$out"
      grep -oE '^#{1,4}\s+.*' "$readme" | head -20 >> "$out" || echo "(none)" >> "$out"
      # TOC marker
      grep -qi 'table of contents\|^-\s.*\]\(#' "$readme" && echo "TOC: yes" >> "$out" || echo "TOC: no" >> "$out"
    fi
    # Top-level dirs
    echo "TOP_DIRS:" >> "$out"
    ls -1d */ 2>/dev/null | head -15 >> "$out"
    # Ecosystem
    [ -f Cargo.toml ] && echo "RUST: yes" >> "$out"
    [ -f package.json ] && echo "NODE: yes" >> "$out"
    [ -f go.mod ] && echo "GO: yes" >> "$out"
    [ -f setup.py ] || [ -f pyproject.toml ] && echo "PYTHON: yes" >> "$out"
    echo "" >> "$out"
    popd > /dev/null
  elif [ -f "$item" ] && [ "$item" != "quick_intel.txt" ]; then
    echo "### FILE: $item" >> "$out"
    wc -l < "$item" >> "$out"
    echo "" >> "$out"
  fi
done