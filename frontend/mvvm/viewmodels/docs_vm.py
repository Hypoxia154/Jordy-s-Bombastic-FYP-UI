from typing import List
from mvvm.services.api_client import ApiClient

class DocsViewModel:
    def __init__(self, api: ApiClient):
        self.api = api

    def list_documents(self) -> List[str]:
        """Fetch all ingested documents."""
        data = self.api.get("/crag/documents")
        return data.get("files", [])

    def delete_document(self, filename: str) -> bool:
        """Delete a document by filename."""
        self.api.delete(f"/crag/documents/{filename}")
        return True
