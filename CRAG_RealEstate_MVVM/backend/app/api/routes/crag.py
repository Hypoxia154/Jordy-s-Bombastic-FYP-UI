from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.schemas import QueryRequest, QueryResponse
from app.services.crag_service import CRAGService
from app.db.repositories.chat import ChatRepository

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, current=Depends(get_current_user)) -> QueryResponse:
    service = CRAGService()
    result = service.answer(question=payload.question, user_role=current["role"])

    repo = ChatRepository()
    session_id = payload.session_id
    if session_id is None:
        session = repo.create_session(current["username"], payload.question)
        session_id = session.id

    repo.append_message(session_id, {"role": "user", "content": payload.question})
    repo.append_message(
        session_id,
        {
            "role": "assistant",
            "content": result.answer,
            "sources": result.sources,
            "confidence": result.confidence,
        },
    )

    return QueryResponse(
        session_id=session_id,
        answer=result.answer,
        sources=result.sources,
        confidence=result.confidence,
    )
