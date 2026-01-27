from fastapi import APIRouter, Depends, UploadFile, File, HTTPException

from app.core.deps import get_current_user
from app.models.schemas import QueryRequest, QueryResponse
from app.services.crag_service import CRAGService
from app.db.repositories.chat import ChatRepository

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, current=Depends(get_current_user)) -> QueryResponse:
    # Instantiate the real CRAG Service
    service = CRAGService()
    
    # We pass an empty history for now, or fetch from repo if needed
    # Ideally, we should fetch previous messages from ChatRepository to pass as history
    # For this migration, we kept it simple as per original design
    
    # generate_response returns a dict: {'answer': str, 'sources': List[str]}
    result_dict = service.generate_response(query=payload.question, history=[])
    
    answer_text = result_dict["answer"]
    sources_list = result_dict["sources"]
    confidence = 1.0 # Placeholder, as CRAGService doesn't return raw confidence score easily in this dict

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
            "content": answer_text,
            "sources": sources_list,
            "confidence": confidence,
        },
    )

    return QueryResponse(
        session_id=session_id,
        answer=answer_text,
        sources=sources_list, # List[str]
        confidence=confidence,
    )


@router.post("/ingest")
def ingest_document(file: UploadFile = File(...), current=Depends(get_current_user)):
    if not current.get("role") in ["admin", "master"]:
        raise HTTPException(status_code=403, detail="Admin/Master access required.")

    service = CRAGService()
    try:
        content = file.file.read()
        res = service.ingest_file(filename=file.filename, content=content)
        return {"message": res, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

