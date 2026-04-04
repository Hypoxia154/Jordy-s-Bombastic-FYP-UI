from typing import List, Dict, Any
from mvvm.services.api_client import ApiClient

class LogsViewModel:
    def __init__(self, api: ApiClient):
        self.api = api

    def get_system_logs(self) -> List[Dict[str, Any]]:
        """Fetch the latest system errors/logs from the backend."""
        try:
            return self.api.get("/admin/logs")
        except Exception as e:
            # handle unauthorized or connection errors gracefully in the ui
            raise Exception(f"Failed to fetch logs: {str(e)}")

    def clear_system_logs(self) -> bool:
        """Clear all backend system logs."""
        try:
            self.api.delete("/admin/logs")
            return True
        except Exception:
            return False
