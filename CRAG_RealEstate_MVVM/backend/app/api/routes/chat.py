from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.schemas import (
    ChatSessionCreateRequest,
    ChatSessionPublic,
    ChatMessageCreateRequest,
    ChatMessagePublic,
)
from app.db.repositories.chat import ChatRepository

router = APIRouter()

@router.get("/sessions", response_model=list[ChatSessionPublic])
def list_sessions(current=Depends(get_current_user)) -> list[ChatSessionPublic]:
    return ChatRepository().list_sessions(current["username"])

@router.post("/sessions", response_model=ChatSessionPublic)
def create_session(payload: ChatSessionCreateRequest, current=Depends(get_current_user)) -> ChatSessionPublic:
    return ChatRepository().create_session(current["username"], payload.first_user_message)

@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessagePublic])
def get_messages(session_id: int, current=Depends(get_current_user)) -> list[ChatMessagePublic]:
    repo = ChatRepository()
    if not repo.session_belongs_to_user(session_id, current["username"]):
        raise HTTPException(status_code=404, detail="Session not found.")
    return repo.get_messages(session_id)

@router.post("/sessions/{session_id}/messages", response_model=ChatMessagePublic)
def append_message(session_id: int, payload: ChatMessageCreateRequest, current=Depends(get_current_user)) -> ChatMessagePublic:
    repo = ChatRepository()
    if not repo.session_belongs_to_user(session_id, current["username"]):
        raise HTTPException(status_code=404, detail="Session not found.")
    return repo.append_message(session_id, payload.model_dump())

@router.delete("/sessions")
def clear_my_sessions(current=Depends(get_current_user)) -> dict:
    ChatRepository().clear_sessions(current["username"])
    return {"status": "ok"}
