from fastapi import APIRouter, HTTPException

from app.models.schemas import LoginRequest, AuthResponse
from app.db.repositories.users import UsersRepository
from app.db.repositories.tokens import TokensRepository

router = APIRouter()

@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    users = UsersRepository()
    user = users.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    tokens = TokensRepository()
    token = tokens.issue_token(user["username"])
    return AuthResponse(access_token=token, user=user)
