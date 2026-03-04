from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user, check_permission
from app.models.schemas import (
    ChatSessionCreateRequest,
    ChatSessionPublic,
    ChatMessageCreateRequest,
    ChatMessagePublic,
)
from app.db.repositories.chat import ChatRepository

router = APIRouter()

@router.get("/sessions", response_model=list[ChatSessionPublic])
def list_sessions(current=Depends(get_current_user), _=Depends(check_permission)) -> list[ChatSessionPublic]:
    return ChatRepository().list_sessions(current["username"])

@router.post("/sessions", response_model=ChatSessionPublic)
def create_session(payload: ChatSessionCreateRequest, current=Depends(get_current_user), _=Depends(check_permission)) -> ChatSessionPublic:
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

@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, current=Depends(get_current_user)) -> dict:
    ok = ChatRepository().delete_session(session_id, current["username"])
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"status": "ok"}

class PinRequest(BaseModel):
    pinned: bool

@router.put("/sessions/{session_id}/pin")
def pin_session(session_id: int, payload: PinRequest, current=Depends(get_current_user)) -> dict:
    ok = ChatRepository().pin_session(session_id, current["username"], payload.pinned)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"status": "ok", "pinned": payload.pinned}

class RenameRequest(BaseModel):
    title: str

@router.put("/sessions/{session_id}/title")
def rename_session(session_id: int, payload: RenameRequest, current=Depends(get_current_user)) -> dict:
    ok = ChatRepository().rename_session(session_id, current["username"], payload.title)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"status": "ok", "title": payload.title}

@router.delete("/sessions")
def clear_my_sessions(current=Depends(get_current_user)) -> dict:
    ChatRepository().clear_sessions(current["username"])
    return {"status": "ok"}
