from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Any, List, Optional

from app.core.deps import get_current_user, check_permission
from app.models.schemas import QueryRequest, QueryResponse
from app.services.crag_service import CRAGService
from app.services.chart_service import ChartService
from app.db.repositories.chat import ChatRepository

router = APIRouter()


class VisualizeRequest(BaseModel):
    text: str
    hint: str = "visualize this data as a chart"


@router.post("/visualize")
def visualize(payload: VisualizeRequest, current=Depends(get_current_user)):
    """
    Calls Gemini directly to extract chart data from arbitrary text.
    Does NOT create a chat message or go through CRAG.
    """
    svc = ChartService()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="Gemini chart service not configured.")
    data = svc.extract_chart_data(payload.text, payload.hint)
    if not data:
        raise HTTPException(status_code=422, detail="No chartable numerical data found in this response.")
    return {"chart_data": data}


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, current=Depends(get_current_user)) -> QueryResponse:
    # Instantiate the real CRAG Service
    service = CRAGService()
    repo = ChatRepository()
    
    # Load history if session_id is provided
    history_messages = []
    if payload.session_id:
        # Check if session exists/belongs to user could be done here, 
        # but get_messages will just return empty if invalid or empty.
        # We might want to ensure the session belongs to 'current' user for security, 
        # but for now we trust the ID or let repo handle it.
        # Strict check:
        # if not repo.session_belongs_to_user(payload.session_id, current["username"]): ...
        
        raw_msgs = repo.get_messages(payload.session_id)
        # Format for CRAGService (List[str])
        # "User: ...", "Assistant: ..."
        for m in raw_msgs:
            role = m["role"].capitalize()
            content = m["content"]
            history_messages.append(f"{role}: {content}")

    # generate_response returns a dict: {'answer': str, 'sources': List[str]}
    result_dict = service.generate_response(query=payload.question, history=history_messages)
    
    answer_text = result_dict["answer"]
    sources_list = result_dict.get("sources", [])
    chart_data = result_dict.get("chart_data", None)
    confidence = result_dict.get("confidence", 0.0)

    # Save to DB
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
        chart_data=chart_data,
    )



@router.post("/ingest")
def ingest_document(file: UploadFile = File(...), current=Depends(get_current_user), _=Depends(check_permission)):
    # if not current.get("role") in ["admin", "master"]:
    #    raise HTTPException(status_code=403, detail="Admin/Master access required.")

    service = CRAGService()
    try:
        content = file.file.read()
        res = service.ingest_file(filename=file.filename, content=content)
        return {"message": res, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
def list_documents(current=Depends(get_current_user), _=Depends(check_permission)):
    service = CRAGService()
    return {"files": service.list_documents()}

@router.delete("/documents/{filename}")
def delete_document(filename: str, current=Depends(get_current_user), _=Depends(check_permission)):
    service = CRAGService()
    success = service.delete_document(filename)
    if not success:
        raise HTTPException(status_code=404, detail="File not found or deletion failed.")
    return {"message": f"Deleted {filename}"}
