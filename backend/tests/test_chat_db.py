"""
test_chat_db.py — Direct unit tests for ChatRepository database logic.

These tests bypass the HTTP layer entirely and call the repository methods
directly. This validates that the core data access layer is correct.
"""
import pytest
from tests.conftest import get_conn


def test_create_session_assigns_id():
    """create_session() should return a ChatSession with a numeric ID."""
    from app.db.repositories.chat import ChatRepository
    repo = ChatRepository()
    session = repo.create_session("testuser", "What is the lease period?")
    assert session.id is not None
    assert isinstance(session.id, int)
    assert session.id > 0


def test_create_session_title_truncated():
    """Titles longer than 40 chars should be truncated with '...'"""
    from app.db.repositories.chat import ChatRepository
    repo = ChatRepository()
    long_msg = "A" * 60
    session = repo.create_session("testuser", long_msg)
    assert len(session.title) <= 43  # 40 chars + '...'
    assert session.title.endswith("...")


def test_append_message_and_retrieve():
    """Messages appended to a session should be retrievable in order."""
    from app.db.repositories.chat import ChatRepository
    repo = ChatRepository()
    session = repo.create_session("testuser2", "Hello")

    repo.append_message(session.id, {
        "role": "user",
        "content": "What is the notice period?",
        "timestamp": None,
        "sources": None,
        "confidence": None
    })
    repo.append_message(session.id, {
        "role": "assistant",
        "content": "The notice period is typically 30 days.",
        "timestamp": None,
        "sources": ["doc1.pdf"],
        "confidence": 0.85
    })

    messages = repo.get_messages(session.id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["confidence"] == 0.85


def test_delete_session():
    """Deleted sessions should no longer appear in list_sessions."""
    from app.db.repositories.chat import ChatRepository
    repo = ChatRepository()
    session = repo.create_session("todelete", "A temporary question")
    result = repo.delete_session(session.id, "todelete")
    assert result is True

    sessions = repo.list_sessions("todelete")
    ids = [s["id"] for s in sessions]
    assert session.id not in ids


def test_pin_session():
    """Pinning a session should reflect in the list ordering (pinned first)."""
    from app.db.repositories.chat import ChatRepository
    repo = ChatRepository()
    s1 = repo.create_session("pinuser", "Unpinned question")
    s2 = repo.create_session("pinuser", "Pinned question")

    repo.pin_session(s2.id, "pinuser", True)
    sessions = repo.list_sessions("pinuser")
    # pinned session should appear first
    assert sessions[0]["id"] == s2.id


def test_rename_session():
    """rename_session() should change the title persisted in the DB."""
    from app.db.repositories.chat import ChatRepository
    repo = ChatRepository()
    session = repo.create_session("renameuser", "Original message")
    result = repo.rename_session(session.id, "renameuser", "Custom Title")
    assert result is True

    sessions = repo.list_sessions("renameuser")
    match = next(s for s in sessions if s["id"] == session.id)
    assert match["title"] == "Custom Title"
