#!/data/data/com.termux/files/usr/bin/bash
# synthegration version <session_id> – commit conversation DAG
# synthegration diff <session_id> <old_version> <new_version>
set -euo pipefail
PY="$HOME/cli-synthegration/conv_versioner.py"
REPO="$HOME/cli-synthegration/repo"

case "${1:-}" in
    commit)
        sid="${2:?Usage: synth_version commit <session_id>}"
        python3 -c "
import sys; sys.path.insert(0,'$HOME/deepcli'); sys.path.insert(0,'$HOME/cli-synthegration')
from deepcli.core import get_token, get_history
from conv_versioner import ConversationDAG
from pathlib import Path
t = get_token()
msgs = get_history(t, '$sid')
dag = ConversationDAG('$sid', msgs[0].get('title','') if msgs else '')
for m in msgs: dag.add_message(m)
v = dag.commit(Path('$REPO/$sid'))
print(f'Version: {v} ({len(dag.nodes)} nodes)')
"
        ;;
    diff)
        old="${2:?}" new="${3:?}"
        python3 -c "
from conv_versioner import ConversationDAG
from pathlib import Path
old_dag = ConversationDAG.load(Path('$REPO/$old'))
new_dag = ConversationDAG.load(Path('$REPO/$new'))
print('Diff:', old_dag.diff(new_dag) if old_dag and new_dag else 'DAG not found')
"
        ;;
    graph)
        sid="${2:?}"
        python3 -c "
from conv_versioner import ConversationDAG
from pathlib import Path
dag = ConversationDAG.load(Path('$REPO/$sid'))
print(dag.to_graphviz() if dag else 'No DAG')
"
        ;;
    *) echo "Usage: synth_version {commit|diff|graph} ..." ;;
esac