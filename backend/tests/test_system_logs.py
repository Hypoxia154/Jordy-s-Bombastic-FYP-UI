"""
test_system_logs.py — Tests for the LogsRepository and /admin/logs endpoint.

Covers:
- Inserting a log entry directly via LogsRepository
- Fetching logs returns inserted entries
- Clear logs empties the table
"""
import pytest
from tests.conftest import get_conn


def test_log_error_inserts_record():
    """log_error() should insert a new row into system_logs."""
    from app.db.repositories.logs import LogsRepository
    repo = LogsRepository()
    repo.log_error(
        level="ERROR",
        endpoint="/crag/query",
        username="stafftest",
        request_payload='{"question": "What is the rent?"}',
        error_message="TimeoutError: LLM timed out",
        traceback_str="Traceback (most recent call last):\n  File 'crag_service.py'..."
    )
    logs = repo.get_logs(limit=10)
    assert len(logs) >= 1
    latest = logs[0]
    assert latest["level"] == "ERROR"
    assert latest["username"] == "stafftest"
    assert latest["endpoint"] == "/crag/query"
    assert "TimeoutError" in latest["error_message"]


def test_get_logs_returns_most_recent_first():
    """Logs should be returned newest-first (descending by id)."""
    from app.db.repositories.logs import LogsRepository
    repo = LogsRepository()
    repo.log_error("INFO", "/auth/login", "userA", None, "First event", None)
    repo.log_error("ERROR", "/crag/query", "userB", None, "Second event", None)

    logs = repo.get_logs(limit=5)
    # Most recent (Second event) should be first
    assert logs[0]["error_message"] == "Second event"


def test_clear_logs_empties_table():
    """clear_logs() should remove all records from system_logs."""
    from app.db.repositories.logs import LogsRepository
    repo = LogsRepository()
    repo.log_error("ERROR", "/test", "user", None, "test entry", None)
    repo.clear_logs()
    logs = repo.get_logs(limit=10)
    assert logs == []


def test_admin_logs_endpoint_accessible(authed_client):
    """GET /admin/logs should return 200 for the master user."""
    r = authed_client.get("/admin/logs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
