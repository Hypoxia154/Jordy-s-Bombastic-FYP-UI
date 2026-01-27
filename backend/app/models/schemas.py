from pydantic import BaseModel, Field, EmailStr
from typing import Literal

Role = Literal["master", "admin", "staff"]


class UserPublic(BaseModel):
    username: str
    role: Role
    name: str
    email: EmailStr
    created_at: str
    last_login: str | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthResponse(BaseModel):
    access_token: str
    user: UserPublic


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    role: Role = "staff"
    name: str = Field(min_length=2, max_length=64)
    email: EmailStr


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=64)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class RoleUpdateRequest(BaseModel):
    role: Role


class ChatSessionPublic(BaseModel):
    id: int
    username: str
    title: str
    created_at: str


class ChatSessionCreateRequest(BaseModel):
    first_user_message: str


class ChatMessagePublic(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str
    sources: list[str] = []
    confidence: float | None = None


class ChatMessageCreateRequest(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str | None = None
    sources: list[str] | None = None
    confidence: float | None = None


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: int | None = None


class QueryResponse(BaseModel):
    session_id: int
    answer: str
    sources: list[str]
    confidence: float
