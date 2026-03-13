from app.db.sqlite import db


def _has_column(conn, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def ensure_schema() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('master','admin','staff')),
              name TEXT NOT NULL,
              email TEXT NOT NULL,
              created_at TEXT NOT NULL,
              last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS auth_tokens (
              token TEXT PRIMARY KEY,
              username TEXT NOT NULL,
              issued_at TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL,
              title TEXT NOT NULL,
              created_at TEXT NOT NULL,
              pinned INTEGER NOT NULL DEFAULT 0,
              FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id INTEGER NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
              content TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              sources TEXT,
              confidence REAL,
              bleu_score REAL,
              evidence TEXT,
              FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS knowledge_docs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              content TEXT NOT NULL,
              tags TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS doc_texts (
              file_name TEXT PRIMARY KEY,
              content_text TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS document_access (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              file_name TEXT NOT NULL,
              username TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_document_access_unique
              ON document_access(file_name, username);
            """
        )

        # Lightweight migrations for older DBs
        if not _has_column(conn, "chat_sessions", "pinned"):
            conn.execute("ALTER TABLE chat_sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")

        if not _has_column(conn, "chat_messages", "bleu_score"):
            conn.execute("ALTER TABLE chat_messages ADD COLUMN bleu_score REAL")

        if not _has_column(conn, "chat_messages", "evidence"):
            conn.execute("ALTER TABLE chat_messages ADD COLUMN evidence TEXT")

        conn.commit()