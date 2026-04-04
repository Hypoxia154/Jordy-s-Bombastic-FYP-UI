from typing import List
from mvvm.services.api_client import ApiClient

class DocsViewModel:
    def __init__(self, api: ApiClient):
        self.api = api

    def list_documents(self) -> List[str]:
        """Fetch all ingested documents (admin/master)."""
        data = self.api.get("/crag/documents")
        return data.get("files", [])

    def list_my_documents(self) -> List[str]:
        """Fetch only documents accessible to the current user."""
        data = self.api.get("/crag/documents/my")
        return data.get("files", [])

    def get_access(self, filename: str) -> List[str]:
        """Get list of usernames with access to a document."""
        data = self.api.get(f"/crag/documents/{filename}/access")
        return data.get("usernames", [])

    def set_access(self, filename: str, usernames: List[str]) -> None:
        """Set access list for a document."""
        self.api.put(f"/crag/documents/{filename}/access", {"usernames": usernames})

    def delete_document(self, filename: str) -> bool:
        """Delete a document by filename."""
        self.api.delete(f"/crag/documents/{filename}")
        return True
