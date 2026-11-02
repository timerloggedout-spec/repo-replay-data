#!/bin/bash
# prov_query.sh – query file provenance from the command line
API="$HOME/cli-synthegration/workspace/provenance/provenance_api.py"
if [ "$1" = "-s" ] || [ "$1" = "--summary" ]; then
    python3 -c "from provenance_api import summary; import json; print(json.dumps(summary(), indent=2))"
elif [ "$1" = "-f" ] || [ "$1" = "--file" ]; then
    python3 -c "from provenance_api import get_origin; import json; print(json.dumps(get_origin('$2'), indent=2))"
elif [ "$1" = "-S" ] || [ "$1" = "--search" ]; then
    python3 -c "from provenance_api import search; import json; print(json.dumps(search('$2'), indent=2))"
else
    echo "Usage:"
    echo "  prov_query.sh --summary            Show delay statistics"
    echo "  prov_query.sh --file <path>        Show origin of a file"
    echo "  prov_query.sh --search <session>   List files from a session"
fi