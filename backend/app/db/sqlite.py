import sqlite3
from contextlib import contextmanager

from app.core.config import settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db() -> sqlite3.Connection:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def ensure_session_state_column() -> None:
    with db() as conn:
        if not _has_column(conn, "chat_sessions", "state_json"):
            print("Adding state_json column to chat_sessions...")
            conn.execute("ALTER TABLE chat_sessions ADD COLUMN state_json TEXT")


def ensure_session_pin_column() -> None:
    with db() as conn:
        if not _has_column(conn, "chat_sessions", "pinned"):
            print("Adding pinned column to chat_sessions...")
            conn.execute("ALTER TABLE chat_sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")


def ensure_chat_message_columns() -> None:
    with db() as conn:
        if not _has_column(conn, "chat_messages", "bleu_score"):
            print("Adding bleu_score column to chat_messages...")
            conn.execute("ALTER TABLE chat_messages ADD COLUMN bleu_score REAL")

        if not _has_column(conn, "chat_messages", "evidence"):
            print("Adding evidence column to chat_messages...")
            conn.execute("ALTER TABLE chat_messages ADD COLUMN evidence TEXT")


def ensure_doc_text_table() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doc_texts (
                file_name TEXT PRIMARY KEY,
                content_text TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def ensure_document_access_table() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                username TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_document_access_unique
            ON document_access(file_name, username)
            """
        )


def ensure_system_logs_table() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                endpoint TEXT,
                username TEXT,
                request_payload TEXT,
                error_message TEXT NOT NULL,
                traceback TEXT
            )
            """
        )


def ensure_rbac_logs_table() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rbac_access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                action TEXT NOT NULL
            )
            """
        )


def init_db_migrations() -> None:
    ensure_session_state_column()
    ensure_session_pin_column()
    ensure_chat_message_columns()
    ensure_doc_text_table()
    ensure_document_access_table()
    ensure_system_logs_table()
    ensure_rbac_logs_table()