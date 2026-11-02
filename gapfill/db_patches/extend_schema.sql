-- Add to existing local_repo.db without losing current data
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    source_file TEXT,
    title TEXT,
    created_at REAL,
    indexed_at REAL DEFAULT (datetime('now')),
    content_hash TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS sessions_fts USING fts5(
    title,
    content,
    content=sessions,
    content_rowid=rowid
);
-- Triggers for sync
CREATE TRIGGER IF NOT EXISTS sessions_ai AFTER INSERT ON sessions BEGIN
    INSERT INTO sessions_fts(rowid, title, content) VALUES (new.rowid, new.title, '');
END;
CREATE TRIGGER IF NOT EXISTS sessions_ad AFTER DELETE ON sessions BEGIN
    INSERT INTO sessions_fts(sessions_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, '');
END;
CREATE TRIGGER IF NOT EXISTS sessions_au AFTER UPDATE ON sessions BEGIN
    INSERT INTO sessions_fts(sessions_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, '');
    INSERT INTO sessions_fts(rowid, title, content) VALUES (new.rowid, new.title, '');
END;