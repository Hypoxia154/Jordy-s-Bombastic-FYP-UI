from fastapi import Header, HTTPException

from app.db.repositories.tokens import TokensRepository
from app.db.repositories.users import UsersRepository


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    token = authorization.split(" ", 1)[1].strip()

    tokens = TokensRepository()
    username = tokens.validate_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    user = UsersRepository().get_user(username)
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists.")
    return user


def require_role(current_user: dict, allowed: set[str]) -> None:
    if current_user.get("role") not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden.")
