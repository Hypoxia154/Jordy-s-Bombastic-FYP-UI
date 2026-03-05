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


def ensure_session_state_column() -> None:
    """
    Safe one-time migration:
    Adds chat_sessions.state_json if it doesn't exist.
    """
    with db() as conn:
        columns = conn.execute("PRAGMA table_info(chat_sessions)").fetchall()
        column_names = [col["name"] for col in columns]

        if "state_json" not in column_names:
            print("🛠 Adding state_json column to chat_sessions...")
            conn.execute("ALTER TABLE chat_sessions ADD COLUMN state_json TEXT")

def ensure_doc_text_table():
    """
    Stores full extracted text once (Option A).
    """
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doc_texts (
                file_name TEXT PRIMARY KEY,
                content_text TEXT,
                updated_at TEXT
            )
            """
        )


def ensure_doc_access_table():
    """
    Maps documents to staff users allowed to access them.
    If no entries exist for a file, admin/master can still see it freely.
    Staff only see files that have their username listed.
    """
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doc_access (
                file_name TEXT NOT NULL,
                username  TEXT NOT NULL,
                PRIMARY KEY (file_name, username)
            )
            """
        )


def ensure_session_pin_column() -> None:
    """Adds pinned column to chat_sessions if it doesn't exist."""
    with db() as conn:
        columns = conn.execute("PRAGMA table_info(chat_sessions)").fetchall()
        column_names = [col["name"] for col in columns]
        if "pinned" not in column_names:
            print("🛠 Adding pinned column to chat_sessions...")
            conn.execute("ALTER TABLE chat_sessions ADD COLUMN pinned INTEGER DEFAULT 0")

def ensure_system_logs_table() -> None:
    """Creates a durable table for capturing backend 500 errors."""
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
    """Creates a table to log all Casbin authorization decisions (Allowed/Denied)."""
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

def init_db_migrations():
    ensure_session_state_column()
    ensure_doc_text_table()
    ensure_doc_access_table()
    ensure_session_pin_column()
    ensure_system_logs_table()
    ensure_rbac_logs_table()