#!/usr/bin/env python3
"""
provenance_mapper_cli.py – Code‑block → file provenance via the synthegration CLI.
Uses `synthegration sessions`, `synthegration export`, and `synthegration offline-export`
to extract code blocks, then matches against project files by SHA‑256.
"""
import subprocess, json, sys, os, hashlib, re
from pathlib import Path

# ---------- CONFIG ----------
SYNTH_CMD = "synthegration"
EXPORT_DIR = Path.home() / "synthegration_exports"   # fallback for offline exports
SOURCE_DIRS = [
    "deepcli", "deepcli-tui", "deepseek-cli", "cli-synthegration",
    "termux-multi-agent", "synthegration-cli", "harmonizer-prod_cli",
    "chronos_checkout"
]
BLOAT_PARTS = {"node_modules", "__pycache__", ".cache", ".git", "dist",
               "codex/blobs", "browser-data", ".blob", "logs", "tmp"}
OUTPUT_FILE = Path.home() / "cli-synthegration/workspace/provenance_index.json"
# ------------------------------

def run(cmd):
    """Run shell command, return stdout or None."""
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return None

def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def extract_blocks_from_text(text):
    """Pull fenced code blocks from arbitrary text."""
    return re.findall(r"```(?:\w+)?\n(.*?)\n```", text, re.DOTALL)

def get_online_sessions():
    """Return list of session IDs from the online database."""
    out = run(f"{SYNTH_CMD} sessions")
    if not out:
        return []
    # Parse the table output – assumes format like:
    # ID        Title           Messages ...
    # abc123    Some title      15 ...
    ids = []
    for line in out.splitlines():
        parts = line.split()
        if parts and not parts[0].startswith("ID") and not line.startswith("──"):
            # First token is the ID (alphanumeric hash)
            if re.match(r"^[a-f0-9]{6,}$", parts[0]):
                ids.append(parts[0])
    return ids

def get_offline_sessions():
    """List sessions from offline export directory."""
    out = run(f"{SYNTH_CMD} offline-sessions {EXPORT_DIR}")
    if not out:
        return []
    # Similar parsing – expects lines with session IDs
    ids = []
    for line in out.splitlines():
        parts = line.split()
        if parts and re.match(r"^[a-f0-9]{6,}$", parts[0]):
            ids.append(parts[0])
    return ids

def export_session(session_id, offline=False):
    """Return raw code blocks (as text) from a session.
    If offline, use offline-export, else online export."""
    if offline:
        cmd = f"{SYNTH_CMD} offline-export {EXPORT_DIR} {session_id}"
    else:
        cmd = f"{SYNTH_CMD} export {session_id}"
    out = run(cmd)
    if not out:
        return ""
    # The export command may output JSON with code blocks or plain text.
    # Try JSON first, then fallback to regex on plain text.
    try:
        data = json.loads(out)
        # Assume structure: data["messages"][...]["content"]
        blocks = []
        for msg in data.get("messages", []):
            blocks.extend(extract_blocks_from_text(msg.get("content", "")))
        return "\n".join(blocks)
    except json.JSONDecodeError:
        return out  # raw output, will extract blocks later

def is_bloat(parts):
    return any(p in BLOAT_PARTS for p in parts)

# ----- 1. Collect code blocks from all sessions -----
all_blocks = {}   # hash -> list of origin info

# Try online first, then offline
session_ids = get_online_sessions() + get_offline_sessions()
if not session_ids:
    # Final fallback: scan export JSON files directly
    if EXPORT_DIR.is_dir():
        for fpath in sorted(EXPORT_DIR.glob("*.json")):
            try:
                conv = json.loads(fpath.read_text())
            except:
                continue
            for msg_idx, msg in enumerate(conv.get("messages", [])):
                content = msg.get("content", "")
                for blk_idx, block in enumerate(extract_blocks_from_text(content)):
                    h = sha256(block.strip())
                    all_blocks.setdefault(h, []).append({
                        "session": fpath.stem,
                        "message_index": msg_idx,
                        "block_index": blk_idx,
                        "snippet": block[:200] + "..." if len(block) > 200 else block
                    })
else:
    for sid in session_ids:
        # Determine if offline (if sid came from offline list)
        offline = sid in get_offline_sessions()
        print(f"Exporting session {sid} ({'offline' if offline else 'online'})")
        text = export_session(sid, offline=offline)
        if not text:
            continue
        for blk_idx, block in enumerate(extract_blocks_from_text(text)):
            h = sha256(block.strip())
            all_blocks.setdefault(h, []).append({
                "session": sid,
                "block_index": blk_idx,
                "snippet": block[:200] + "..." if len(block) > 200 else block
            })

print(f"Unique code blocks extracted: {len(all_blocks)}")

# ----- 2. Hash source files -----
file_hashes = {}
for base in SOURCE_DIRS:
    base_path = Path.home() / base
    if not base_path.is_dir():
        continue
    for fpath in base_path.rglob("*"):
        if fpath.is_file() and not is_bloat(fpath.parts):
            try:
                h = sha256(fpath.read_text())
            except:
                continue
            file_hashes[h] = str(fpath.relative_to(Path.home()))
print(f"Source files hashed: {len(file_hashes)}")

# ----- 3. Match -----
matches = []
for h, origins in all_blocks.items():
    if h in file_hashes:
        matches.append({
            "code_block_hash": h,
            "origins": origins,
            "matched_file": file_hashes[h]
        })

# ----- 4. Write index -----
index = {
    "meta": {
        "sessions_scanned": len(session_ids),
        "unique_code_blocks": len(all_blocks),
        "source_files_hashed": len(file_hashes),
        "exact_matches": len(matches)
    },
    "matches": matches
}
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(index, f, indent=2)

print(f"Provenance index -> {OUTPUT_FILE}")
print(f"Matched {len(matches)} code blocks → files")