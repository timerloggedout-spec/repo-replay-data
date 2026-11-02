#!/usr/bin/env python3
"""Build TOOL_INDEX.md – curated list of all installed pkgs + custom tools."""

import subprocess, json, os
from pathlib import Path
from datetime import datetime

HOME = Path.home()
OUT = HOME / "archwiz/TOOL_INDEX.md"
SECONDARY = HOME / "workspace/llm_map/TOOL_INDEX.md"

def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.stdout.strip()

lines = []
lines.append("# 🪄 Tool Index — Auto‑Generated")
lines.append(f"**Updated:** {datetime.now().isoformat()}")
lines.append("")

# ── System packages ──
lines.append("## 📦 System Packages (pkg)")
pkgs = run("pkg list-installed")
for line in pkgs.splitlines():
    if line.startswith("Listing"): continue
    parts = line.split("/")
    if parts:
        name_ver = parts[0].split(",")[0]  # "name/stable,now version"
        lines.append(f"- `{name_ver}`")

lines.append("")

# ── Custom Tools (Python scripts with argparse) ──
lines.append("## 🧰 Custom Tools")
tool_dirs = [
    HOME / "archwiz",
    HOME / "workspace/llm_map",
    HOME / "harmony_hub/src",
    HOME / "harmony_hub/utility_belt",
    HOME / "deepcli",
    HOME / "deepseek-cli",
    HOME / "termux-multi-agent",
]
for d in tool_dirs:
    if not d.exists(): continue
    for f in sorted(d.glob("*.py")):
        if f.name.startswith("_"): continue
        # Try to read first 3 lines for docstring
        desc = ""
        try:
            with open(f) as fh:
                for _ in range(5):
                    line = fh.readline()
                    if '"""' in line or "'''" in line:
                        desc = line.strip().replace('"""','').replace("'''","")[:80]
                        break
        except: pass
        lines.append(f"- **{f.name}** — `{f}` — {desc}")
    for sh in sorted(d.glob("*.sh")):
        lines.append(f"- **{sh.name}** — `{sh}`")

lines.append("")

# ── Python packages (pip) ──
lines.append("## 🐍 Python Packages (pip)")
pip_list = run("pip list 2>/dev/null")
for line in pip_list.splitlines()[2:]:  # skip header
    lines.append(f"- {line}")

lines.append("")

# Write
with open(OUT, "w") as f:
    f.write("\n".join(lines))

# Sync to secondary location
if SECONDARY.parent.exists():
    SECONDARY.parent.mkdir(parents=True, exist_ok=True)
    with open(SECONDARY, "w") as f:
        f.write("\n".join(lines))
    print(f"✅ Written {OUT} and {SECONDARY}")
else:
    print(f"✅ Written {OUT}")