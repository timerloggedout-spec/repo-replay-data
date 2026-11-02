# Synthegration Harmonized Architecture v0.1
*Iteratively updated – last: $(date)*

## Objectives
- Unify token acquisition (Puppeteer, cookies.json, ~/.deepseek_api_key) into a **secure vault** with zero plaintext log leakage.
- Provide a single CLI `synthegrate` dispatching to deepcli, TUI, termux-multi-agent, and code harvesters.
- Build a **hierarchical taxonomy search** over conversation sessions, auto-populating commands to minimize LLM bandwidth.

## Token Security
**Problem:** `get_token()` prints tokens in logs and heredocs.  
**Solution:** All tokens read from encrypted `vault.json` (age-encrypted) or environment variable `$DEEPSEEK_API_KEY`.  
**Migration:** 
- `upload-api.json` tokens → moved to `~/.synthegration/vault.age`.
- deepcli/core.py `get_token()` patched to read from vault.
- TUI and multi-agent import from unified `synthegrate.token_vault`.

## Component Command Map
| Tool | Entry | Available Commands |
|------|-------|-------------------|
| deepcli | `deep` | *(to be harvested)* |
| deepseek-cli | `deepseek-cli` | *(to be harvested)* |
| deepcli-tui | `node ~/deepcli-tui` | interactive TUI |
| termux-multi-agent | `python3 run.py` | orchestrate agents |
| deepseek_harmonizer | `bash deepseek_harmonizer.sh` | extract code blocks |

## New synthegrate Commands (planned)
- `token` – retrieve token securely (only when explicitly asked, never logged)
- `search <keyword>` – full-text search across all conversation JSONs
- `harvest <json>` – extract code blocks from export
- `agent <task>` – delegate to multi-agent framework
- `chat` – launch TUI
- `plan` – update this document from discovered changes

## Hierarchical Taxonomy for Session Search
- Sessions will be indexed nightly into SQLite (termux-multi-agent db).
- Taxonomy: `domain > topic > subtopic > session_id`
- User `synthegrate find python error` walks taxonomy to narrow search.

## CedrLang Integration
- CEDARscript (CedrLang) found in ??? *(to be filled after research)*
- Will be used as the DSL for command chaining and agent task definitions.

## Next Steps
1. Complete research dump and fill missing command lists.
2. Patch token flow to never echo sensitive values.
3. Build taxonomy indexer.