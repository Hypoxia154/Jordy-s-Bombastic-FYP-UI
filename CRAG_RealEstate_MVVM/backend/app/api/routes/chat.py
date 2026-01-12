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