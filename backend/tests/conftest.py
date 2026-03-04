"""
conftest.py - Shared test fixtures for the entire pytest test suite.

Architecture:
  - All SQLite database calls are redirected to a shared in-memory SQLite3 instance.
  - CRAGService (Qdrant + Ollama) is mocked so tests run offline.
  - Casbin is stubbed to allow all requests.
  - master_token fixture creates a user + token DIRECTLY in the in-memory DB,
    bypassing HTTP so we don't need the auth route live during session setup.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# ─── Shared In-Memory SQLite Connection ────────────────────────────────────
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(":memory:", check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


class FakeDB:
    """Drop-in context manager replacing app.db.sqlite.db()"""
    def __enter__(self):
        return get_conn()
    def __exit__(self, *_):
        get_conn().commit()


# ─── Create all tables in in-memory DB ─────────────────────────────────────
def _create_tables():
    c = get_conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'staff',
            name TEXT, email TEXT,
            created_at TEXT, last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_tokens (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            pinned INTEGER DEFAULT 0,
            state_json TEXT
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT,
            sources TEXT,
            confidence REAL
        );
        CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            endpoint TEXT,
            username TEXT,
            request_payload TEXT,
            error_message TEXT NOT NULL,
            traceback TEXT
        );
        CREATE TABLE IF NOT EXISTS doc_access (
            file_name TEXT NOT NULL,
            username TEXT NOT NULL,
            PRIMARY KEY (file_name, username)
        );
        CREATE TABLE IF NOT EXISTS doc_texts (
            file_name TEXT PRIMARY KEY,
            content_text TEXT,
            updated_at TEXT
        );
    """)
    c.commit()


# ─── Global Patches ────────────────────────────────────────────────────────
# Patch every db() import before any app module is loaded.
_patches = []


def pytest_configure(config):
    """Called very early by pytest — before any test files are imported."""
    _create_tables()
    for target in [
        "app.db.sqlite.db",
        "app.db.repositories.users.db",
        "app.db.repositories.tokens.db",
        "app.db.repositories.chat.db",
        "app.db.repositories.logs.db",
        "app.db.repositories.docs.db",
    ]:
        try:
            p = patch(target, new=FakeDB)
            p.start()
            _patches.append(p)
        except Exception:
            pass


def pytest_unconfigure(config):
    for p in _patches:
        try:
            p.stop()
        except Exception:
            pass


# ─── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Returns the FastAPI app with Casbin and CRAGService mocked."""
    with patch("app.core.security_casbin.enforcer") as mock_enforcer, \
         patch("app.core.deps.get_crag_service") as mock_get_crag:

        mock_enforcer.enforce.return_value = True
        mock_crag = MagicMock()
        mock_get_crag.return_value = mock_crag

        from app.main import app as fa
        yield fa


@pytest.fixture(scope="session")
def client(app):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="session")
def master_token():
    """
    Creates master user and issues a real opaque token DIRECTLY via
    TokensRepository.issue_token(), bypassing the HTTP login endpoint.
    """
    from app.core.security import hash_password
    from app.db.repositories.tokens import TokensRepository

    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users "
        "(username, password_hash, role, name, email, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("master", hash_password("master123"), "master",
         "Master Admin", "master@test.com", "2026-01-01")
    )
    conn.commit()

    repo = TokensRepository()
    return repo.issue_token("master")


@pytest.fixture(scope="session")
def authed_client(client, master_token):
    client.headers.update({"Authorization": f"Bearer {master_token}"})
    return client
