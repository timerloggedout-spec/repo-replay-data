#!/usr/bin/env python3
import sqlite3, sys
from pathlib import Path

DB_PATH = Path.home() / "synthegration-cli" / "sessions.db"

def search(keyword, limit=5):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT m.rowid, m.role, snippet(messages_fts, 0, '<b>', '</b>', '...', 32) as snippet,
               c.title, c.id as conv_id, m.timestamp
        FROM messages_fts
        JOIN messages m ON m.id = messages_fts.rowid
        JOIN conversations c ON c.id = m.conv_id
        WHERE messages_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    ''', (keyword, limit))
    rows = c.fetchall()
    if not rows:
        print(f"No matches for '{keyword}'")
        return
    for r in rows:
        print(f"Conv: {r['title']} ({r['conv_id']})")
        print(f"  Role: {r['role']}")
        print(f"  Snippet: {r['snippet']}")
        print()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: search_sessions.py <keyword>")
        sys.exit(1)
    kw = sys.argv[1]
    search(kw)