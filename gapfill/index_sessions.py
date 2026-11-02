#!/usr/bin/env python3
import json, sqlite3, os, sys
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path.home() / "synthegration-cli" / "sessions.db"
SEARCH_DIRS = [
    Path.home() / "deepseek-cli" / "test-reports",
    Path.home() / "storage" / "downloads" / "_doing" / "_1-build" / "DeepSeek" / "exports",
    Path.home() / "deepseek_harvest_work",
]

def init_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at REAL,
            updated_at REAL,
            source_file TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conv_id TEXT REFERENCES conversations(id),
            role TEXT,
            content TEXT,
            timestamp REAL,
            search_text TEXT
        )
    ''')
    c.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            content,
            search_text,
            content=messages,
            content_rowid=id
        )
    ''')
    # Triggers to keep FTS in sync
    c.execute('''
        CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, content, search_text) VALUES (new.id, new.content, new.search_text);
        END
    ''')
    c.execute('''
        CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content, search_text) VALUES('delete', old.id, old.content, old.search_text);
        END
    ''')
    c.execute('''
        CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, content, search_text) VALUES('delete', old.id, old.content, old.search_text);
            INSERT INTO messages_fts(rowid, content, search_text) VALUES (new.id, new.content, new.search_text);
        END
    ''')
    conn.commit()
    return conn

def extract_metadata(obj, conv_id=None, title=None, ts=None):
    """Recursively pull id, title, inserted_at from DeepSeek export format."""
    if isinstance(obj, dict):
        if "id" in obj and not conv_id:
            conv_id = str(obj["id"])
        if "title" in obj:
            title = obj["title"]
        if "inserted_at" in obj and not ts:
            ts = obj["inserted_at"]
        if "message" in obj:
            msg = obj["message"]
            role = msg.get("author", {}).get("role") or msg.get("role", "unknown")
            content = msg.get("content", {}).get("text") or msg.get("content", "")
            msg_ts = msg.get("create_time") or msg.get("timestamp") or ts
            return conv_id, title, ts, role, content, msg_ts
        for v in obj.values():
            res = extract_metadata(v, conv_id, title, ts)
            if res[0]:
                return res
    elif isinstance(obj, list):
        for item in obj:
            res = extract_metadata(item, conv_id, title, ts)
            if res[0]:
                return res
    return conv_id, title, ts, None, None, None

def index_file(filepath, conn):
    with open(filepath, encoding='utf-8') as f:
        data = json.load(f)
    c = conn.cursor()
    convs = data if isinstance(data, list) else [data]
    for conv in convs:
        conv_id, title, ts, _, _, _ = extract_metadata(conv)
        if conv_id:
            c.execute(
                "INSERT OR IGNORE INTO conversations (id, title, created_at, updated_at, source_file) VALUES (?,?,?,?,?)",
                (conv_id, title or "Untitled", ts or 0, ts or 0, str(filepath))
            )
            # Extract messages individually
            extract_messages(conv, conv_id, conn)
    conn.commit()

def extract_messages(obj, conv_id, conn):
    if isinstance(obj, dict):
        if "messages" in obj:
            for msg in obj["messages"]:
                if isinstance(msg, dict):
                    role = msg.get("author", {}).get("role") or msg.get("role", "unknown")
                    content = msg.get("content", {}).get("text") or msg.get("content", "")
                    ts = msg.get("create_time") or msg.get("timestamp") or 0
                    if content:
                        conn.execute(
                            "INSERT INTO messages (conv_id, role, content, timestamp, search_text) VALUES (?,?,?,?,?)",
                            (conv_id, role, str(content), ts, str(content)[:1000])
                        )
        else:
            for v in obj.values():
                extract_messages(v, conv_id, conn)
    elif isinstance(obj, list):
        for item in obj:
            extract_messages(item, conv_id, conn)

def main():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = init_db(DB_PATH)
    for search_dir in SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for f in search_dir.rglob("*.json"):
            if f.name.startswith("report-") or "conversations" in f.name or "export" in f.name:
                print(f"Indexing {f}")
                index_file(f, conn)
    conn.close()
    print("Indexing complete.")

if __name__ == "__main__":
    main()