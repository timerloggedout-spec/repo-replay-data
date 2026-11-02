#!/usr/bin/env bash
set -euo pipefail
cd ~/refTemplates

LOG="move_log.txt"
REVERT="revert.sh"
: > "$LOG"
cat > "$REVERT" <<'HEAD'
#!/usr/bin/env bash
set -euo pipefail
cd ~/refTemplates
# Auto-generated revert script – undoes all moves
HEAD
chmod +x "$REVERT"

move() {
  local src="$1"; local dst_dir="$2"; local why="$3"
  if [[ ! -e "$src" ]]; then echo "SKIP $src (not found)" >> "$LOG"; return; fi
  mkdir -p "$dst_dir"
  mv "$src" "$dst_dir/"
  echo "$(date -Iseconds): $src → $dst_dir/   # $why" >> "$LOG"
  echo "mv '$dst_dir/$src' './'" >> "$REVERT"
}

# 01 — Core
move "frankenterm" "01_Flywheel_Terminal_&_Agent_Runtime" "Swarm-native terminal; hosts pi_agent_rust"
move "pi_agent_rust" "01_Flywheel_Terminal_&_Agent_Runtime" "High-perf coding agent CLI; runs inside frankenterm"

# 02 — Memory
move "cass_memory_system" "02_Agent_Memory_&_Session" "Procedural memory; consumed by pi_agent_rust & coding_agent_session_search"
move "coding_agent_session_search" "02_Agent_Memory_&_Session" "Cross-session search index; queried by pi_agent_rust"

# 03 — Coordination
move "mcp_agent_mail_rust" "03_Agent_Coordination" "Mail-like coordination for agents; used by frankenterm & pi_agent_rust"

# 04 — CedarScript
move "cedarscript-grammar" "04_CedarScript_Code_Manipulation" "SQL-like language grammar"
move "cedarscript-ast-parser-python" "04_CedarScript_Code_Manipulation" "AST parser for CedarScript"
move "cedarscript-editor-python" "04_CedarScript_Code_Manipulation" "Runtime engine; used by pi_agent_rust"
move "cedarscript-mcp" "04_CedarScript_Code_Manipulation" "MCP server exposing CedarScript tools"

# 05 — Safety
move "destructive_command_guard" "05_Safety_&_Guardrails" "Blocks dangerous shell commands; hooked into pi_agent_rust"
move "process_triage" "05_Safety_&_Guardrails" "Bayesian process triage; protects system under agent load"
move "system_resource_protection_script" "05_Safety_&_Guardrails" "Sysctl/resource tunables; used by process_triage"

# 06 — Observability
move "rano" "06_Observability" "Network observer; feeds telemetry to frankenterm dashboard"

# 07 — Task tracking
move "beads_rust" "07_Task_&_Issue_Tracking" "Local-first issue tracker; integrated with frankenterm"
move "beads_viewer" "07_Task_&_Issue_Tracking" "TUI for beads; used by frankenterm"

# 08 — Prompt & Context
move "source_to_prompt_tui" "08_Prompt_&_Context_Engineering" "Builds LLM prompts from code; used with pi_agent_rust"
move "markdown_web_browser" "08_Prompt_&_Context_Engineering" "Web→Markdown for agent context"

# 09 — Swarm refs
move "swarms" "09_Swarm_Orchestration_References" "Python multi-agent orchestration"
move "swarms-rs" "09_Swarm_Orchestration_References" "Rust multi-agent orchestration (inspiration for frankenterm)"
move "swarm-ecosystem" "09_Swarm_Orchestration_References" "Ecosystem of swarm tools"

# 10 — Account/Auth
move "coding_agent_account_manager" "10_Account_&_Auth" "API key management for agents"
move "openclaw-zero-token" "10_Account_&_Auth" "Token-free LLM access for agents"

# 11 — Infrastructure
move "rust_proxy" "11_Infrastructure_&_DevOps" "Transparent proxy; used by rano"
move "repo_updater" "11_Infrastructure_&_DevOps" "Bulk git update tool"
move "ntm" "11_Infrastructure_&_DevOps" "Named Tmux Manager; session persistence"

# 12 — Eval & Quality
move "Approxination-Benchmark" "12_Evaluation_&_Quality" "Tool-calling benchmark for agents"
move "Inverse-Arena" "12_Evaluation_&_Quality" "Execution-evidence skill ranking"
move "ultimate_bug_scanner" "12_Evaluation_&_Quality" "Bug scanner used by pi_agent_rust"

# 13 — External agent projects
move "AiShell" "13_External_Agent_Shells" "Natural language shell (inspiration)"
move "YGK-a" "13_External_Agent_Shells" "ChatGPT shell client (pipelines)"
move "lazycodex" "13_External_Agent_Shells" "Agent harness for complex codebases"
move "oh-my-openagent" "13_External_Agent_Shells" "OpenAgent predecessor"
move "senpi" "13_External_Agent_Shells" "Pi coding agent (Node.js)"
move "brenner_bot" "13_External_Agent_Shells" "Scientific methods AI agent"
move "llm_fallbacks" "13_External_Agent_Shells" "LLM fallback library"

# 14 — Third party refs
move "TradingAgents" "14_Third_Party_References" "Multi-agent trading framework"
move "My-Jogyo" "14_Third_Party_References" "Research lab for OpenCode"
move "CloudBooter" "14_Third_Party_References" "Cloud bootstrapper"
move "ChapitoAI-main" "14_Third_Party_References" "AI chat app"
move "aadc" "14_Third_Party_References" "ASCII art aligner"
move "orca" "14_Third_Party_References" "Desktop AI assistant"
move "opencode" "14_Third_Party_References" "Open source coding agent"
move "openskill.lua" "14_Third_Party_References" "Skill rating for games"
move "ffa-brackets" "14_Third_Party_References" "Free-for-all brackets"
move "insane-search" "14_Third_Party_References" "Resistant web search"
move "Termux" "14_Third_Party_References" "Termux config"
move "toon_rust" "14_Third_Party_References" "TOON spec reference"

# 99 — Raw files
move "approxination.txt" "99_Raw_Files" "Notes on approximation"
move "ranking_research-concept-_.txt" "99_Raw_Files" "Ranking research concept"

echo "Organization complete. Log: $LOG"
echo "To revert: bash $REVERT"