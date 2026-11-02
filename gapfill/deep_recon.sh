#!/usr/bin/env bash
out="deep_intel.txt"
: > "$out"
sep="############################################################"
# All known repo names (as alternation for grep)
repo_names="AiShell|Approxination-Benchmark|ChapitoAI-main|CloudBooter|Inverse-Arena|My-Jogyo|Termux|TradingAgents|YGK-a|aadc|beads_rust|beads_viewer|brenner_bot|cass_memory_system|cedarscript-ast-parser-python|cedarscript-editor-python|cedarscript-grammar|cedarscript-mcp|coding_agent_account_manager|coding_agent_session_search|destructive_command_guard|ffa-brackets|frankenterm|insane-search|lazycodex|llm_fallbacks|markdown_web_browser|mcp_agent_mail_rust|ntm|oh-my-openagent|openclaw-zero-token|opencode|openskill.lua|orca|pi_agent_rust|process_triage|rano|repo_updater|rust_proxy|senpi|source_to_prompt_tui|swarm-ecosystem|swarms|swarms-rs|system_resource_protection_script|toon_rust|ultimate_bug_scanner"

for item in *; do
  if [ -d "$item/.git" ]; then
    echo "$sep" >> "$out"
    echo "REPO: $item" >> "$out"
    pushd "$item" > /dev/null
    # 1. Top-level files (first 30 entries)
    echo "TOP_LEVEL_FILES:" >> "$out"
    ls -1 | head -30 >> "$out"
    # 2. Entry points
    echo "ENTRY_POINTS:" >> "$out"
    for f in main.py main.rs main.go index.js index.ts src/main.rs src/main.py src/index.ts src/index.js app.py run.py; do
      [ -f "$f" ] && { echo "--- $f (first 5 lines) ---" >> "$out"; head -5 "$f" >> "$out"; }
    done
    # 3. Cross-references: grep for other repo names in source/config/text files
    echo "CROSS_REFERENCES:" >> "$out"
    grep -rI -o -w -E "$repo_names" . 2>/dev/null | sort | uniq -c | sort -rn | head -20 >> "$out" || echo "(none)" >> "$out"
    # 4. Dependency files
    if [ -f package.json ]; then
      echo "PACKAGE_JSON_DEPS:" >> "$out"
      python3 -c "import json;d=json.load(open('package.json'));print('dependencies:',d.get('dependencies',''));print('devDependencies:',d.get('devDependencies',''))" 2>/dev/null >> "$out"
    fi
    if [ -f Cargo.toml ]; then
      echo "CARGO_TOML_DEPS:" >> "$out"
      grep -A 10 '\[dependencies\]' Cargo.toml >> "$out" || true
    fi
    if [ -f requirements.txt ]; then
      echo "REQUIREMENTS:" >> "$out"
      head -10 requirements.txt >> "$out"
    fi
    if [ -f pyproject.toml ]; then
      echo "PYPROJECT_TOML:" >> "$out"
      head -20 pyproject.toml >> "$out"
    fi
    popd > /dev/null
  elif [ -f "$item" ]; then
    echo "$sep" >> "$out"
    echo "FILE: $item" >> "$out"
    file "$item" >> "$out"
  fi
done
echo "$sep" >> "$out"
echo "Deep recon complete." >> "$out"