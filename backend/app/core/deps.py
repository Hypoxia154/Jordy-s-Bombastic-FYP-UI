from fastapi import Header, HTTPException, Request, Depends
from app.core.security_casbin import enforcer

from app.db.repositories.tokens import TokensRepository
from app.db.repositories.users import UsersRepository
from functools import lru_cache

# --- Service singletons (cached dependencies) ---
# CRAGService is heavy (loads embedding model, reranker, vector index, etc.).
# Caching it prevents re-initializing on every request.
@lru_cache(maxsize=1)
def get_crag_service():
    # Local import avoids any potential import cycles during app startup.
    from app.services.crag_service import CRAGService
    return CRAGService()

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

def check_permission(request: Request, current_user: dict = Depends(get_current_user)) -> None:
    role = current_user.get("role", "user")
    
    # Extract path template matching strict policy (e.g. /users/{username}) or fallback to raw path
    obj = request.scope.get("route").path if request.scope.get("route") else request.url.path
    act = request.method
    
    if not enforcer.enforce(role, obj, act):
        raise HTTPException(status_code=403, detail="Forbidden by Casbin.")
