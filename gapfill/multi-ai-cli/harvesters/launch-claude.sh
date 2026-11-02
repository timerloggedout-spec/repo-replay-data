#!/data/data/com.termux/files/usr/bin/bash
export DISPLAY=:1
chromium --user-data-dir=$HOME/browser-data-claude \
         --no-first-run \
         --no-default-browser-check \
         https://claude.ai/login &
echo "Chromium launched for Claude. Log in, then close the browser."
echo "After closing, run: python3 ~/multi-ai-cli/harvesters/extract_claude_cookies.py"