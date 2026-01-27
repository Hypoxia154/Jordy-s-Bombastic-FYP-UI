from __future__ import annotations
from typing import Optional, List, Any
from pydantic import BaseModel, Field

class ChatSession(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: Optional[str] = None

class ChatMessage(BaseModel):
    id: Optional[int] = None
    role: str
    content: str
    sources: Optional[List[str]] = None
    confidence: Optional[float] = None
    session_id: Optional[int] = None

class ChatqueryResponse(BaseModel):
    session_id: int
    answer: str
    sources: Optional[List[str]] = None
    confidence: Optional[float] = None
