"""
test_users.py — Tests for the /users endpoints.

Covers:
- Creating a staff user
- Listing users
- Deleting a user
- Duplicate user creation is rejected
"""
import pytest


def test_create_staff_user(authed_client):
    """Creating a new staff user should return 200 and the user's data."""
    r = authed_client.post("/users", json={
        "username": "stafftest",
        "password": "staffpass123",
        "role": "staff",
        "name": "Staff Tester",
        "email": "staff@test.com"
    })
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "stafftest"
    assert body["role"] == "staff"


def test_list_users_contains_created(authed_client):
    """After creating a user, listing users should include them."""
    r = authed_client.get("/users")
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "stafftest" in usernames


def test_create_duplicate_user_rejected(authed_client):
    """Attempting to create a user with an existing username should fail with 400."""
    r = authed_client.post("/users", json={
        "username": "stafftest",
        "password": "anotherpassword",
        "role": "staff",
        "name": "Duplicate",
        "email": "dup@test.com"
    })
    assert r.status_code == 400


def test_delete_user(authed_client):
    """Deleting an existing user should succeed and return status ok."""
    r = authed_client.delete("/users/stafftest")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_delete_nonexistent_user(authed_client):
    """Deleting a user that doesn't exist should return 404."""
    r = authed_client.delete("/users/ghost_user_xyz")
    assert r.status_code == 404
