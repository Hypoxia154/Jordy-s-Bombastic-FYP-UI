from datetime import datetime
from fastapi import HTTPException

from app.db.sqlite import db
from app.core.security import hash_password, verify_password
from app.models.schemas import UserCreateRequest, UserUpdateRequest, UserPublic


class UsersRepository:
    def authenticate(self, username: str, password: str) -> dict | None:
        with db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            if not row:
                return None
            if not verify_password(password, row["password_hash"]):
                return None

            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            conn.execute("UPDATE users SET last_login=? WHERE username=?", (now, username))
            return self._row_to_public_dict(row, last_login=now)

    def get_user(self, username: str) -> dict | None:
        with db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_public_dict(row)

    def list_users(self) -> list[UserPublic]:
        with db() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
            return [UserPublic(**self._row_to_public_dict(r)) for r in rows]

    def create_user(self, payload: UserCreateRequest) -> UserPublic:
        with db() as conn:
            exists = conn.execute(
                "SELECT 1 FROM users WHERE username=?", (payload.username,)
            ).fetchone()
            if exists:
                raise HTTPException(status_code=400, detail="Username already exists.")

            now = datetime.now().strftime("%Y-%m-%d")
            conn.execute(
                "INSERT INTO users (username,password_hash,role,name,email,created_at,last_login) VALUES (?,?,?,?,?,?,?)",
                (
                    payload.username,
                    hash_password(payload.password),
                    payload.role,
                    payload.name,
                    payload.email,
                    now,
                    None,
                ),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE username=?", (payload.username,)
            ).fetchone()
            return UserPublic(**self._row_to_public_dict(row))

    def update_user(self, username: str, payload: UserUpdateRequest) -> UserPublic:
        with db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found.")

            updates: list[str] = []
            params: list[object] = []

            if payload.name is not None:
                updates.append("name=?")
                params.append(payload.name)
            if payload.email is not None:
                updates.append("email=?")
                params.append(payload.email)
            if payload.password is not None:
                updates.append("password_hash=?")
                params.append(hash_password(payload.password))

            if updates:
                params.append(username)
                conn.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE username=?", params
                )

            updated = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            return UserPublic(**self._row_to_public_dict(updated))

    def update_role(self, username: str, role: str) -> UserPublic:
        with db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found.")
            conn.execute("UPDATE users SET role=? WHERE username=?", (role, username))
            updated = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
            return UserPublic(**self._row_to_public_dict(updated))

    def delete_user(self, username: str) -> bool:
        with db() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE username=?", (username,)
            ).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM users WHERE username=?", (username,))
            return True

    @staticmethod
    def _row_to_public_dict(row, last_login: str | None = None) -> dict:
        return {
            "username": row["username"],
            "role": row["role"],
            "name": row["name"],
            "email": row["email"],
            "created_at": row["created_at"],
            "last_login": last_login if last_login is not None else row["last_login"],
        }
