#!/bin/bash
source ~/.bashrc 2>/dev/null || true

echo "============================================"
echo " ECOSYSTEM MAPPER — STATE RESEARCH"
echo "============================================"

echo ""
echo ">> Active Profile: ${LLM_PROFILE:-none (default)}"

echo ""
echo ">> Profiles on disk:"
ls -1 ~/.config/llm_map/profiles/ 2>/dev/null || echo "(no custom profiles)"

cd ~/workspace/llm_map || { echo "ERROR: ~/workspace/llm_map not found"; exit 1; }

echo ""
echo ">> [1/6] Rebuilding master index..."
time map-build

echo ""
echo ">> [2/6] Extracting function definitions..."
time map-func

echo ""
echo ">> [3/6] Key output files:"
ls -lh *.jsonl *.json *.md 2>/dev/null | head -20

echo ""
echo ">> Master index entries:"
wc -l llm_index_compact.jsonl

echo ""
echo ">> Function definitions:"
wc -l func_index.jsonl

echo ""
echo ">> [4/6] Most 'used_by' files (top 5):"
jq -r 'select(.used_by != null) | "\(.used_by)\t\(.file)"' llm_index_compact.jsonl | sort -nr | head -5

echo ""
echo ">> Sample master index entry:"
head -1 llm_index_compact.jsonl | jq .

echo ""
echo ">> Functions in build_final_all_profile.py (using funcfind):"
funcfind workspace/llm_map/build_final_all_profile.py

echo ""
echo ">> Functions in func_indexer.py:"
funcfind workspace/llm_map/func_indexer.py

echo ""
echo ">> [5/6] Dependencies of build_final_all_profile.py:"
dep workspace/llm_map/build_final_all_profile.py

echo ""
echo ">> Dependencies of graph_query.py:"
dep workspace/llm_map/graph_query.py

echo ""
echo ">> Function kinds summary:"
jq -r '.kind' func_index.jsonl | sort | uniq -c | sort -rn

echo ""
echo ">> Files with most definitions (top 10):"
jq -r '.file' func_index.jsonl | sort | uniq -c | sort -rn | head -10

echo ""
echo ">> [6/6] CaveMan Index preview (first 20 lines):"
head -20 CAVEMAN_INDEX.md 2>/dev/null || echo "(CAVEMAN_INDEX.md missing)"

echo ""
echo ">> SYSTEM_MAP preview (first 30 lines):"
head -30 SYSTEM_MAP.md 2>/dev/null || echo "(SYSTEM_MAP.md missing)"

echo ""
echo "=== RESEARCH COMPLETE ==="