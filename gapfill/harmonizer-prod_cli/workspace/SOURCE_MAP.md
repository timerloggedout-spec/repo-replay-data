# Source Map – harmonizer-prod

| Workspace Path | Original Location | Purpose |
|---------------|------------------|---------|
| commands/live_export.py | ~/cli-synthegration/live_export.py | Single session live API export |
| commands/live_search.py | ~/cli-synthegration/live_search.py | Cross-session code block search |
| commands/live_message_search.py | ~/cli-synthegration/live_message_search.py | Full-text message search across exports |
| export/export_all.py | ~/cli-synthegration/export_all.py | Batch export all sessions |
| export/batch_export_all.py | ~/cli-synthegration/batch_export_all.py | Batch export with dedup |
| search/conv_explorer.py | ~/cli-synthegration/conv_explorer.py | Session search, export, listing |
| search/conv_branching.py | ~/cli-synthegration/conv_branching.py | Branch/fork detection and DAG |
| search/conv_versioner.py | ~/cli-synthegration/conv_versioner.py | Conversation versioning |
| auth/token_provider.py | ~/cli-synthegration/token_provider.py | Unified token provider |
| auth/account_manager.py | ~/cli-synthegration/account_manager.py | Multi-account token management |
| auth/deepcli_core.py | ~/deepcli/deepcli/core.py | DeepSeek internal API wrapper |
| auth/extract-token.js | ~/deepcli/extract-token.js | Puppeteer token extraction |
| index/synthegration_index.py | ~/cli-synthegration/synthegration_index.py | Codex blob store + MessageIndex |
| multi_agent/orchestrator.py | ~/termux-multi-agent/src/orchestrator.py | Multi-agent refactoring orchestrator |
| multi_agent/run.py | ~/termux-multi-agent/run.py | Multi-agent entry point |
| harvest/harvest.py | ~/deepseek_harvest_work/harvest.py | Recursive code block extraction + dedup |
| harvest/batch_merge.py | ~/deepseek_harvest_work/batch_merge.py | Batch merge of harvested blocks |
| commands/main.rs.reference | ~/synthegration-cli/src/main.rs | Rust CLI (reference for port) |
| rules/ | ~/cli-synthegration/rules/ | ast-grep rules |

## External Dependencies (not copied)
- ~/deepcli/deepcli/cli.py – Main CLI entry (import-session, chat, export, etc.)
- ~/deepcli-tui/tui.py – Terminal UI
- ~/deepseek-cli/ – Browser automation + cookies
- ~/synthegration-cli/ – Rust binary project
- ~/termux-multi-agent/ – Multi-agent refactoring project
- ~/deepseek_harvest_work/ – Code block extraction pipeline