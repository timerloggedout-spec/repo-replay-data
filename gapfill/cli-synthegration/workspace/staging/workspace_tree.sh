#!/data/data/com.termux/files/usr/bin/bash
echo "=== Harmonizer Workspace Tree ==="
echo ""
for proj in deepcli deepcli-tui termux-multi-agent deepseek_harvest_work deepseek-cli synthegration-cli cli-synthegration harmonizer-prod_cli; do
    D="$HOME/$proj/workspace"
    if [ -d "$D" ]; then
        echo "$proj/"
        find "$D" -maxdepth 2 -type d | sed "s|$D/|  ├─ |" | sort
        echo ""
    fi
done