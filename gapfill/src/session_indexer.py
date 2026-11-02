#!/usr/bin/env python3
import json, hashlib, sqlite3, os
from pathlib import Path

DB_PATH = Path.home() / "termux-multi-agent" / "local_repo.db"
SOURCE_DIRS = [
    Path.home() / "deepseek-cli" / "test-reports",
    Path.home() / "storage" / "downloads" / "_doing" / "_1-build" / "DeepSeek" / "exports",
]

def index():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    for src_dir in SOURCE_DIRS:
        for f in src_dir.rglob("*.json"):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            sessions = data if isinstance(data, list) else [data]
            for sess in sessions:
                sid = sess.get("id")
                if not sid:
                    continue
                title = sess.get("title", "Untitled")
                ts = sess.get("inserted_at", sess.get("update_time", 0))
                content = json.dumps(sess)  # store full session as JSON? Could be heavy; store only message texts later
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                # Skip if already indexed and unchanged
                existing = c.execute("SELECT content_hash FROM sessions WHERE session_id=?", (sid,)).fetchone()
                if existing and existing[0] == content_hash:
                    continue
                c.execute(
                    "INSERT OR REPLACE INTO sessions (session_id, source_file, title, created_at, content_hash) VALUES (?,?,?,?,?)",
                    (sid, str(f), title, ts, content_hash)
                )
    conn.commit()
    conn.close()
    print("Sessions indexed without duplication.")

if __name__ == "__main__":
    index()