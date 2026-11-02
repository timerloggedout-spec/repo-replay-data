#!/bin/bash
# Usage: session_search.sh <keyword> [<directory>]
KEYWORD="${1?}"
DIR="${2:-$HOME/deepseek-cli/test-reports}"
jq -r --arg kw "$KEYWORD" '
  def walk:
    if type == "object" then
      to_entries[] | .value | walk
    elif type == "array" then
      .[] | walk
    elif type == "string" and (contains($kw)) then
      .
    else
      empty
    end;
  walk
' "$DIR"/*.json 2>/dev/null | head -100