#!/usr/bin/env python3
"""Extract cookies from Chromium profile for claude.ai domain."""
import sqlite3, json, os, shutil
from pathlib import Path

COOKIE_DB = Path.home() / "browser-data-claude" / "Default" / "Cookies"
OUT = Path.home() / ".multi-ai-tokens" / "claude_cookies.json"
TOKEN_OUT = Path.home() / ".multi-ai-tokens" / "claude_token.txt"

if not COOKIE_DB.exists():
    print(f"Cookie database not found at {COOKIE_DB}")
    print("Launch Chromium first with: ~/multi-ai-cli/harvesters/launch-claude.sh")
    exit(1)

tmp_db = "/tmp/claude_cookies_tmp.db"
shutil.copy2(COOKIE_DB, tmp_db)

conn = sqlite3.connect(tmp_db)
conn.row_factory = sqlite3.Row
cookies = []
for row in conn.execute("SELECT * FROM cookies WHERE host_key LIKE '%claude%' OR host_key LIKE '%anthropic%'"):
    cookies.append({
        "name": row["name"],
        "value": row["encrypted_value"] if row["encrypted_value"] else row["value"],
        "domain": row["host_key"],
        "path": row["path"],
        "expires": row["expires_utc"],
        "httpOnly": bool(row["is_httponly"]),
        "secure": bool(row["is_secure"]),
    })
conn.close()
os.unlink(tmp_db)

with open(OUT, "w") as f:
    json.dump(cookies, f, indent=2)
print(f"Extracted {len(cookies)} Claude cookies → {OUT}")

for c in cookies:
    if c["name"] in ("sessionKey", "session", "__Secure-next-auth.session-token", "token"):
        TOKEN_OUT.write_text(c["value"])
        print(f"Auth token saved → {TOKEN_OUT}")
        break
else:
    print("No obvious auth token cookie found.")