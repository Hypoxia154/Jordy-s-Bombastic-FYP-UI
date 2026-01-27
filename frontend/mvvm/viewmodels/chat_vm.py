from typing import List, Optional
from mvvm.services.api_client import ApiClient
from mvvm.models import ChatSession, ChatMessage, ChatqueryResponse

class ChatViewModel:
    def __init__(self, api: ApiClient):
        self.api = api

    def list_sessions(self) -> List[ChatSession]:
        """Fetch all chat sessions for the current user."""
        data = self.api.get("/chat/sessions/")
        # specific validation or transformation logic
        return [ChatSession(**item) for item in data]

    def get_messages(self, session_id: int) -> List[ChatMessage]:
        """Fetch message history for a specific session."""
        data = self.api.get(f"/chat/sessions/{session_id}/messages")
        return [ChatMessage(**item) for item in data]

    def clear_sessions(self) -> bool:
        """Clear all sessions for the user."""
        self.api.delete("/chat/sessions")
        return True

    def query(self, question: str, session_id: Optional[int]) -> ChatqueryResponse:
        """Send a question to the CRAG engine."""
        payload = {"question": question, "session_id": session_id}
        data = self.api.post("/crag/query", payload)
        return ChatqueryResponse(**data)

    def ingest_document(self, file_obj) -> str:
        """Upload a file for ingestion."""
        # files dict for requests: {'field_name': (filename, fileobj, content_type)}
        files = {"file": (file_obj.name, file_obj, file_obj.type)}
        data = self.api.post_file("/crag/ingest", files)
        return data.get("message", "Ingested successfully.")

