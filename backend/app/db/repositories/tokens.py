from datetime import datetime, timedelta
import secrets

from app.core.config import settings
from app.db.sqlite import db


class TokensRepository:
    def issue_token(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        exp = now + timedelta(minutes=settings.token_ttl_minutes)
        with db() as conn:
            conn.execute(
                "INSERT INTO auth_tokens (token, username, issued_at, expires_at) VALUES (?,?,?,?)",
                (token, username, now.isoformat(), exp.isoformat()),
            )
        return token

    def validate_token(self, token: str) -> str | None:
        with db() as conn:
            row = conn.execute(
                "SELECT username, expires_at FROM auth_tokens WHERE token=?", (token,)
            ).fetchone()
            if not row:
                return None
            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.utcnow() > expires_at:
                conn.execute("DELETE FROM auth_tokens WHERE token=?", (token,))
                return None
            return row["username"]
