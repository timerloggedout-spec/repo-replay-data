#!/usr/bin/env bash
out="surgical_intel.txt"
: > "$out"
names="AiShell|Approxination-Benchmark|ChapitoAI-main|CloudBooter|Inverse-Arena|My-Jogyo|Termux|TradingAgents|YGK-a|aadc|beads_rust|beads_viewer|brenner_bot|cass_memory_system|cedarscript-ast-parser-python|cedarscript-editor-python|cedarscript-grammar|cedarscript-mcp|coding_agent_account_manager|coding_agent_session_search|destructive_command_guard|ffa-brackets|frankenterm|insane-search|lazycodex|llm_fallbacks|markdown_web_browser|mcp_agent_mail_rust|ntm|oh-my-openagent|openclaw-zero-token|opencode|openskill.lua|orca|pi_agent_rust|process_triage|rano|repo_updater|rust_proxy|senpi|source_to_prompt_tui|swarm-ecosystem|swarms|swarms-rs|system_resource_protection_script|toon_rust|ultimate_bug_scanner"

for item in *; do
  if [ -d "$item/.git" ]; then
    echo "### $item" >> "$out"
    pushd "$item" > /dev/null
    remote=$(git config --get remote.origin.url 2>/dev/null || echo "NO_REMOTE")
    echo "REMOTE: $remote" >> "$out"
    # README
    for f in README.md README.rst README; do
      [ -f "$f" ] && { echo "README (first 20 lines):" >> "$out"; head -20 "$f" >> "$out"; break; }
    done
    # Ecosystem markers
    [ -f Cargo.toml ] && echo "RUST: yes" >> "$out"
    [ -f package.json ] && echo "NODE: yes" >> "$out"
    [ -f setup.py ] && echo "PYTHON_SETUP: yes" >> "$out"
    [ -f pyproject.toml ] && echo "PYPROJECT: yes" >> "$out"
    [ -f requirements.txt ] && echo "REQUIREMENTS: yes" >> "$out"
    [ -f go.mod ] && echo "GO: yes" >> "$out"
    [ -f Makefile ] && echo "MAKEFILE: yes" >> "$out"
    # Key entry points (first 5 lines)
    for ep in main.py main.rs main.go index.ts index.js src/main.rs src/main.py src/index.ts src/index.js app.py run.py cmd/main.go; do
      [ -f "$ep" ] && { echo "ENTRY $ep (first 5 lines):" >> "$out"; head -5 "$ep" >> "$out"; }
    done
    # Top-level directory listing (first 15)
    echo "TOP DIRS:" >> "$out"
    ls -1d */ 2>/dev/null | head -15 >> "$out"
    # Cross-ref mentions (surgical: only count, max 5)
    echo "CROSS-REF MENTIONS (counts):" >> "$out"
    grep -rI -o -w -E "$names" . --exclude-dir={node_modules,target,.git,dist,build,__pycache__} 2>/dev/null | cut -d: -f2 | sort | uniq -c | sort -rn | head -10 >> "$out" || echo "(none)" >> "$out"
    echo "" >> "$out"
    popd > /dev/null
  elif [ -f "$item" ] && [ "$item" != "surgical_intel.txt" ]; then
    echo "### FILE: $item" >> "$out"
    file "$item" >> "$out"
    echo "" >> "$out"
  fi
done