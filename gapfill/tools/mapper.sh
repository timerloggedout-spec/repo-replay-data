#!/bin/bash
# Quick mapping between sessions, files, and exports
PROV_JSON=~/cli-synthegration/workspace/provenance/comprehensive_provenance.json
jq '.[] | {session: .session_id, file: .file, strategy: .strategy}' "$PROV_JSON" | head -50