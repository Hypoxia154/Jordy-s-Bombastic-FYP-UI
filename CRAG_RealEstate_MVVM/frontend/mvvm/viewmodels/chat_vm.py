from mvvm.services.api_client import ApiClient


class ChatViewModel:
    def __init__(self, api: ApiClient):
        self.api = api

    def list_sessions(self) -> list[dict]:
        return self.api.get("/chat/sessions")

    def get_messages(self, session_id: int) -> list[dict]:
        return self.api.get(f"/chat/sessions/{session_id}/messages")

    def clear_sessions(self) -> dict:
        return self.api.delete("/chat/sessions")

    def query(self, question: str, session_id: int | None) -> dict:
        return self.api.post("/crag/query", {"question": question, "session_id": session_id})
