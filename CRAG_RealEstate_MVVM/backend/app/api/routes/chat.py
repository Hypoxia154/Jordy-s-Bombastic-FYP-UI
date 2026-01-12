from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.schemas import (
    ChatSessionCreateRequest,
    ChatSessionPublic,
    ChatMessageCreateRequest,
    ChatMessagePublic,
)
from app.db.repositories.chat import ChatRepository

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

# Import your new service
from app.services.crag_service import CRAGService

router = APIRouter()
# Initialize Service (Singleton pattern recommended for production)
crag_service = CRAGService()

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[str]] = []

@router.post("/stream")
async def stream_chat(request: ChatRequest):
    """
    Endpoint that streams the answer back to the frontend.
    Matches the MVVM frontend's expectation of a stream.
    """
    # Create a generator that yields text chunks
    def response_generator():
        stream = crag_service.answer_stream(
            question=request.message,
            history=request.history
        )
        for chunk in stream:
            yield chunk

    # Return as a valid Server-Sent Event (SSE) or raw stream
    return StreamingResponse(response_generator(), media_type="text/plain")

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
