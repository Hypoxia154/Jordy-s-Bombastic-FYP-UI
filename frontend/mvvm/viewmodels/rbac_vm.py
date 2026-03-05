from typing import Dict, Any
from mvvm.services.api_client import ApiClient

class RBACViewModel:
    def __init__(self, api: ApiClient):
        self.api = api

    def get_rbac_metrics(self) -> Dict[str, Any]:
        """Fetch the aggregated RBAC access logs for the master dashboard."""
        try:
            return self.api.get("/admin/rbac/metrics")
        except Exception as e:
            # Propagate error up for Streamlit to handle
            raise Exception(f"Failed to fetch RBAC metrics: {str(e)}")

    def simulate_rbac(self, role: str, endpoint: str, method: str) -> Dict[str, Any]:
        """Runs a 'What-If' test against the backend Casbin enforcer."""
        try:
            payload = {
                "simulate_role": role,
                "simulate_endpoint": endpoint,
                "simulate_method": method
            }
            return self.api.post("/admin/rbac/simulate", payload)
        except Exception as e:
            raise Exception(f"Simulation failed: {str(e)}")
