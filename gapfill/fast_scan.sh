#!/usr/bin/env bash
out="fast_intel.txt"
> "$out"
for d in */; do
  name="${d%/}"
  if [ -d "$name/.git" ]; then
    echo "### $name" >> "$out"
    pushd "$name" > /dev/null
    remote=$(git remote get-url origin 2>/dev/null || echo "NO_REMOTE")
    echo "REMOTE: $remote" >> "$out"
    for f in README.md README.rst README; do
      if [ -f "$f" ]; then
        echo "README: $f (lines: $(wc -l < "$f"))" >> "$out"
        echo "FIRST_20:" >> "$out"
        head -20 "$f" >> "$out"
        # extract markdown headers
        grep -E '^#{1,4} ' "$f" | head -20 >> "$out" || echo "(no headers)" >> "$out"
        # TOC check simple
        grep -qi 'table of contents' "$f" && echo "TOC: yes" >> "$out" || echo "TOC: no" >> "$out"
        break
      fi
    done
    echo "TOP_DIRS:" >> "$out"
    ls -1d */ 2>/dev/null | head -15 >> "$out"
    # ecosystem
    [ -f Cargo.toml ] && echo "RUST: yes" >> "$out"
    [ -f package.json ] && echo "NODE: yes" >> "$out"
    [ -f go.mod ] && echo "GO: yes" >> "$out"
    [ -f setup.py ] || [ -f pyproject.toml ] && echo "PYTHON: yes" >> "$out"
    echo "" >> "$out"
    popd > /dev/null
  fi
done
for f in *.txt *.sh; do
  [ -f "$f" ] && [ "$f" != "fast_intel.txt" ] && [ "$f" != "fast_scan.sh" ] && {
    echo "### FILE: $f" >> "$out"
    file "$f" >> "$out"
    echo "" >> "$out"
  }
done