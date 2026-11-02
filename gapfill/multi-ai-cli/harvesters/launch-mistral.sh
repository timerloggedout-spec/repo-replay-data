#!/data/data/com.termux/files/usr/bin/bash
# Launch Chromium with isolated profile for Mistral login
# After logging in, close the browser. Cookies are stored in ~/browser-data-mistral/
export DISPLAY=:1
chromium --user-data-dir=$HOME/browser-data-mistral \
         --no-first-run \
         --no-default-browser-check \
         https://chat.mistral.ai &
echo "Chromium launched for Mistral. Log in, then close the browser."
echo "After closing, run: python3 ~/multi-ai-cli/harvesters/extract_mistral_cookies.py"