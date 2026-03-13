"""
test_auth.py — Tests for the /auth endpoints.

Covers:
- Valid login returns a token
- Invalid password returns 401
- Missing credentials returns 422
"""
import pytest
from tests.conftest import get_conn
from app.core.security import hash_password


@pytest.fixture(autouse=True, scope="module")
def seed_auth_user():
    """Ensure the master user exists in the in-memory DB before auth tests run."""
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users "
        "(username, password_hash, role, name, email, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("master", hash_password("master123"), "master",
         "Master Admin", "master@test.com", "2026-01-01")
    )
    conn.commit()


def test_login_valid(client):
    """A valid login should return HTTP 200 and an access_token."""
    r = client.post("/auth/login", json={"username": "master", "password": "master123"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["access_token"] != ""


def test_login_wrong_password(client):
    """An incorrect password should return HTTP 401."""
    r = client.post("/auth/login", json={"username": "master", "password": "wrongpassword"})
    assert r.status_code == 401


def test_login_nonexistent_user(client):
    """A username that doesn't exist should return HTTP 401."""
    r = client.post("/auth/login", json={"username": "ghost_user", "password": "anypassword"})
    assert r.status_code == 401


def test_login_missing_fields(client):
    """A request with missing fields should return HTTP 422 (Unprocessable Entity)."""
    r = client.post("/auth/login", json={"username": "master"})
    assert r.status_code == 422
