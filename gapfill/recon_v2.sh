#!/usr/bin/env bash
out="repo_intel.txt"
: > "$out"
sep="============================================================"
for item in *; do
  echo "$sep" >> "$out"
  echo "ITEM: $item" >> "$out"
  if [ -d "$item" ]; then
    if [ -d "$item/.git" ]; then
      echo "TYPE: Git repository" >> "$out"
      pushd "$item" > /dev/null
      remote=$(git config --get remote.origin.url 2>/dev/null || echo "NO_REMOTE")
      echo "REMOTE: $remote" >> "$out"
      # Extract owner/repo using grep -oP (Perl regex), fallback
      owner_repo=$(echo "$remote" | grep -oP 'github\.com[:/]\K[^/]+/[^/]+(?=\.git)?' 2>/dev/null || echo "")
      if [ -n "$owner_repo" ]; then
        echo "GITHUB: $owner_repo" >> "$out"
        desc=$(curl -fsS "https://api.github.com/repos/$owner_repo" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('description',''))" 2>/dev/null || echo "NO_DESC")
        [ -n "$desc" ] && echo "DESCRIPTION: $desc" >> "$out"
      fi
      # README
      for f in README.md README.rst README; do
        [ -f "$f" ] && { echo "README first 10 lines ($f):" >> "$out"; head -n 10 "$f" >> "$out"; break; }
      done
      # Ecosystem
      [ -f Cargo.toml ] && echo "ECOSYSTEM: Rust (Cargo.toml)" >> "$out"
      [ -f package.json ] && echo "ECOSYSTEM: Node.js (package.json)" >> "$out"
      [ -f setup.py ] && echo "ECOSYSTEM: Python (setup.py)" >> "$out"
      [ -f requirements.txt ] && echo "ECOSYSTEM: Python (requirements.txt)" >> "$out"
      [ -f pyproject.toml ] && echo "ECOSYSTEM: Python (pyproject.toml)" >> "$out"
      popd > /dev/null
    else
      echo "TYPE: Directory (no .git)" >> "$out"
      ls -1 "$item" >> "$out"
    fi
  elif [ -f "$item" ]; then
    echo "TYPE: File" >> "$out"
    file "$item" >> "$out"
  fi
done
echo "$sep" >> "$out"
echo "Intel complete." >> "$out"