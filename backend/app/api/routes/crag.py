from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import StreamingResponse
import json
import requests
import re

from app.models.schemas import QueryRequest, QueryResponse
from app.services.chart_service import ChartService
from app.db.repositories.chat import ChatRepository
from app.db.repositories.docs import DocsRepository
from app.core.deps import get_current_user, check_permission, get_crag_service
from app.core.config import settings

router = APIRouter()


class VisualizeRequest(BaseModel):
    text: str
    hint: str = "visualize this data as a chart"


class AccessUpdateRequest(BaseModel):
    usernames: list[str]


class DocSummaryRequest(BaseModel):
    file_name: str
    focus: Optional[str] = None
    mode: str = "infographic"


@router.post("/visualize")
def visualize(payload: VisualizeRequest, current=Depends(get_current_user)):
    svc = ChartService()
    if not svc.enabled:
        raise HTTPException(status_code=503, detail="Gemini chart service not configured.")

    result_dict = svc.extract_chart_data(payload.text, payload.hint)
    if not result_dict or not result_dict.get("data"):
        raise HTTPException(status_code=422, detail="No chartable numerical data found in this response.")

    return {
        "chart_data": result_dict["data"],
        "summary": result_dict["summary"],
    }


@router.post("/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    current=Depends(get_current_user),
    service=Depends(get_crag_service),
) -> QueryResponse:
    if payload.question.strip() == "CRASH_TEST":
        raise Exception("This is a deliberate crash triggered for the System Logs!")

    repo = ChatRepository()

    history_messages: List[str] = []
    if payload.session_id:
        raw_msgs = repo.get_messages(payload.session_id)
        for m in raw_msgs:
            role = m["role"].capitalize()
            content = m["content"]
            history_messages.append(f"{role}: {content}")

    docs_repo = DocsRepository()
    all_files = service.list_documents()
    accessible_files = docs_repo.get_accessible_files(
        username=current["username"],
        role=current["role"],
        all_files=all_files,
    )

    session_state = {}
    if payload.session_id:
        session_state = repo.get_session_state(payload.session_id)

    result_dict = service.generate_response(
        query=payload.question,
        history=history_messages,
        user_context={
            "username": current["username"],
            "role": current["role"],
            "session_state": session_state,
            "accessible_files": accessible_files,
            "file_filter": payload.file_filter if hasattr(payload, "file_filter") else None,
        },
    )

    answer_text = result_dict.get("answer", "")
    sources_list = result_dict.get("sources", [])
    evidence = result_dict.get("evidence", [])
    bleu_score = float(result_dict.get("bleu_score", 0.0) or 0.0)
    chart_data = result_dict.get("chart_data", None)
    confidence = result_dict.get("confidence", 0.0)

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
            "bleu_score": bleu_score,
        },
    )

    return QueryResponse(
        session_id=session_id,
        answer=answer_text,
        sources=sources_list,
        evidence=evidence,
        bleu_score=bleu_score,
        confidence=confidence,
        chart_data=chart_data,
    )


@router.post("/ingest")
def ingest_document(
    file: UploadFile = File(...),
    current=Depends(get_current_user),
    service=Depends(get_crag_service),
    _=Depends(check_permission),
):
    try:
        content = file.file.read()
        res = service.ingest_file(filename=file.filename, content=content)
        return {"message": res, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
def list_documents(
    current=Depends(get_current_user),
    service=Depends(get_crag_service),
    _=Depends(check_permission),
):
    return {"files": service.list_documents()}


@router.get("/documents/my")
def list_my_documents(
    current=Depends(get_current_user),
    service=Depends(get_crag_service),
):
    all_files = service.list_documents()
    accessible = DocsRepository().get_accessible_files(
        username=current["username"],
        role=current["role"],
        all_files=all_files,
    )
    return {"files": accessible}


@router.get("/documents/{filename}/access")
def get_document_access(
    filename: str,
    current=Depends(get_current_user),
):
    if current["role"] not in ("admin", "master"):
        raise HTTPException(status_code=403, detail="Forbidden.")
    usernames = DocsRepository().get_access(filename)
    return {"file_name": filename, "usernames": usernames}


@router.put("/documents/{filename}/access")
def set_document_access(
    filename: str,
    payload: AccessUpdateRequest,
    current=Depends(get_current_user),
):
    if current["role"] not in ("admin", "master"):
        raise HTTPException(status_code=403, detail="Forbidden.")
    DocsRepository().set_access(filename, payload.usernames)
    return {"file_name": filename, "usernames": payload.usernames}


@router.delete("/documents/{filename}")
def delete_document(
    filename: str,
    current=Depends(get_current_user),
    service=Depends(get_crag_service),
    _=Depends(check_permission),
):
    success = service.delete_document(filename)
    if not success:
        raise HTTPException(status_code=404, detail="File not found or deletion failed.")
    return {"message": f"Deleted {filename}"}


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def ollama_stream_chat(
    model: str,
    messages: list[dict],
    base_url: str = "http://localhost:11434",
):
    url = f"{base_url.rstrip('/')}/api/chat"

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.1,
            "num_predict": 700,
            "stop": [
                "<|end|>",
                "<|user|>",
                "<|assistant|>",
                "---------------------",
            ],
        },
    }

    with requests.post(url, json=payload, stream=True, timeout=600) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            msg = data.get("message") or {}
            chunk = msg.get("content", "")
            if chunk:
                yield chunk
            if data.get("done"):
                break


def _extract_name_simple(text: str) -> str | None:
    t = (text or "").strip().lower()
    patterns = [
        r"\bmy name is\s+([a-zA-Z][\w\-]{1,30})\b",
        r"\bi am\s+([a-zA-Z][\w\-]{1,30})\b",
        r"\bcall me\s+([a-zA-Z][\w\-]{1,30})\b",
    ]
    for p in patterns:
        m = re.search(p, t)
        if m:
            return m.group(1)
    return None


@router.post("/query_stream")
def query_stream(
    payload: QueryRequest,
    current=Depends(get_current_user),
    service=Depends(get_crag_service),
):
    if payload.question.strip() == "CRASH_TEST":
        raise Exception("This is a deliberate crash triggered for the System Logs!")

    repo = ChatRepository()

    history_messages: List[str] = []
    if payload.session_id:
        raw_msgs = repo.get_messages(payload.session_id)
        for m in raw_msgs:
            role = m["role"].capitalize()
            content = m["content"]
            history_messages.append(f"{role}: {content}")

    session_state = {}
    if payload.session_id:
        session_state = repo.get_session_state(payload.session_id)

    def event_gen():
        yield ": connected\n\n"
        yield sse({"type": "status", "stage": "started", "message": "Thinking..."})

        session_id = payload.session_id
        if session_id is None:
            session = repo.create_session(current["username"], payload.question)
            session_id = session.id
        else:
            _ = session_state or {}

        extracted = _extract_name_simple(payload.question)
        if extracted:
            repo.patch_session_state(session_id, {"user_name": extracted})

        all_files = service.list_documents()
        accessible_files = DocsRepository().get_accessible_files(
            username=current["username"],
            role=current["role"],
            all_files=all_files,
        )

        plan = service.build_rag_plan(
            query=payload.question,
            history=history_messages,
            session_state=repo.get_session_state(session_id),
            file_filter=payload.file_filter if hasattr(payload, "file_filter") else None,
            accessible_files=accessible_files,
        )

        intent = plan.get("intent", "UNKNOWN")
        prompt = plan.get("prompt", payload.question)
        sources_list = plan.get("sources", [])
        confidence = float(plan.get("confidence", 0.0) or 0.0)
        chart_data = plan.get("chart_data", None)

        yield sse({"type": "status", "stage": "classified", "message": f"Intent: {intent}"})
        yield sse({"type": "status", "stage": "generating", "message": "Generating answer..."})

        running = ""
        model_name = settings.LLM_MODEL

        for chunk in ollama_stream_chat(model_name, [{"role": "user", "content": prompt}]):
            running += chunk
            yield sse({"type": "delta", "text": chunk})

        running = service._enforce_safe_output(running)

        repo.append_message(session_id, {"role": "user", "content": payload.question})
        repo.append_message(
            session_id,
            {
                "role": "assistant",
                "content": running,
                "sources": sources_list,
                "confidence": confidence,
            },
        )

        repo.patch_session_state(session_id, {"last_intent": intent})

        yield sse(
            {
                "type": "final",
                "session_id": session_id,
                "answer": running,
                "sources": sources_list,
                "confidence": confidence,
                "chart_data": chart_data,
            }
        )

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/document_summary")
def document_summary(
    payload: DocSummaryRequest,
    current=Depends(get_current_user),
    service=Depends(get_crag_service),
):
    all_files = service.list_documents()
    accessible_files = DocsRepository().get_accessible_files(
        username=current["username"],
        role=current["role"],
        all_files=all_files,
    )

    if payload.file_name not in accessible_files:
        raise HTTPException(status_code=403, detail="You do not have access to this document.")

    return service.summarize_document(
        file_name=payload.file_name,
        focus=payload.focus,
        mode=payload.mode,
    )