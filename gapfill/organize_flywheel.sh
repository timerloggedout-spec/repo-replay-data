#!/usr/bin/env bash
set -euo pipefail
cd ~/refTemplates

LOG="move_log.txt"
REVERT="revert.sh"
: > "$LOG"
cat > "$REVERT" <<'REVERT_HEADER'
#!/usr/bin/env bash
set -euo pipefail
cd ~/refTemplates
# ===== AUTO-GENERATED REVERT SCRIPT =====
# Run this to undo ALL moves and restore original flat layout.
REVERT_HEADER
chmod +x "$REVERT"

move_item() {
  local src="$1"
  local dst_dir="$2"
  if [[ ! -e "$src" ]]; then
    echo "SKIP (not found): $src" | tee -a "$LOG"
    return
  fi
  mkdir -p "$dst_dir"
  local dst="$dst_dir/$src"
  echo "MOVE: $src -> $dst" | tee -a "$LOG"
  mv "$src" "$dst"
  echo "mv '$dst' '$src'" >> "$REVERT"
}

# === 01_Flywheel_Core ===
move_item "frankenterm" "01_Flywheel_Core"
move_item "pi_agent_rust" "01_Flywheel_Core"

# === 02_Memory_Session ===
move_item "cass_memory_system" "02_Memory_Session"
move_item "coding_agent_session_search" "02_Memory_Session"

# === 03_Coordination ===
move_item "mcp_agent_mail_rust" "03_Coordination"

# === 04_CedarScript_Lang ===
move_item "cedarscript-grammar" "04_CedarScript_Lang"
move_item "cedarscript-ast-parser-python" "04_CedarScript_Lang"
move_item "cedarscript-editor-python" "04_CedarScript_Lang"
move_item "cedarscript-mcp" "04_CedarScript_Lang"

# === 05_Safety_Guardrails ===
move_item "destructive_command_guard" "05_Safety_Guardrails"
move_item "process_triage" "05_Safety_Guardrails"
move_item "system_resource_protection_script" "05_Safety_Guardrails"

# === 06_Observability ===
move_item "rano" "06_Observability"

# === 07_Task_Management ===
move_item "beads_rust" "07_Task_Management"
move_item "beads_viewer" "07_Task_Management"

# === 08_Prompt_Engineering ===
move_item "source_to_prompt_tui" "08_Prompt_Engineering"
move_item "markdown_web_browser" "08_Prompt_Engineering"

# === 09_Swarm_Orchestration ===
move_item "swarms" "09_Swarm_Orchestration"
move_item "swarms-rs" "09_Swarm_Orchestration"
move_item "swarm-ecosystem" "09_Swarm_Orchestration"

# === 10_Account_Identity ===
move_item "coding_agent_account_manager" "10_Account_Identity"
move_item "openclaw-zero-token" "10_Account_Identity"

# === 11_Infrastructure ===
move_item "rust_proxy" "11_Infrastructure"
move_item "repo_updater" "11_Infrastructure"
move_item "ntm" "11_Infrastructure"

# === 12_Quality_Benchmarks ===
move_item "Approxination-Benchmark" "12_Quality_Benchmarks"
move_item "Inverse-Arena" "12_Quality_Benchmarks"
move_item "ultimate_bug_scanner" "12_Quality_Benchmarks"

# === 13_External_Siblings ===
move_item "AiShell" "13_External_Siblings"
move_item "YGK-a" "13_External_Siblings"
move_item "lazycodex" "13_External_Siblings"
move_item "oh-my-openagent" "13_External_Siblings"
move_item "senpi" "13_External_Siblings"
move_item "brenner_bot" "13_External_Siblings"
move_item "llm_fallbacks" "13_External_Siblings"

# === 14_Third_Party_Refs ===
move_item "TradingAgents" "14_Third_Party_Refs"
move_item "My-Jogyo" "14_Third_Party_Refs"
move_item "CloudBooter" "14_Third_Party_Refs"
move_item "ChapitoAI-main" "14_Third_Party_Refs"
move_item "aadc" "14_Third_Party_Refs"
move_item "orca" "14_Third_Party_Refs"
move_item "opencode" "14_Third_Party_Refs"
move_item "openskill.lua" "14_Third_Party_Refs"
move_item "ffa-brackets" "14_Third_Party_Refs"
move_item "insane-search" "14_Third_Party_Refs"
move_item "Termux" "14_Third_Party_Refs"
move_item "toon_rust" "14_Third_Party_Refs"

# === 99_Raw_Files ===
move_item "approxination.txt" "99_Raw_Files"
move_item "ranking_research-concept-_.txt" "99_Raw_Files"

echo ""
echo "============================================"
echo " Organization complete."
echo " Move log:   $LOG"
echo " Revert all: bash $REVERT"
echo "============================================"