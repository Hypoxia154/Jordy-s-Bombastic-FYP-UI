from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.deps import check_permission, get_current_user, require_role
from app.core.security_casbin import enforcer
from app.db.repositories.rbac import RBACRepository

router = APIRouter()

class SimulationRequest(BaseModel):
    simulate_role: str
    simulate_endpoint: str
    simulate_method: str

@router.get("/metrics", dependencies=[Depends(check_permission)])
def get_rbac_metrics():
    """
    Returns aggregated RBAC access logs for the master dashboard.
    Protected by Casbin (only master/admin should have access).
    """
    repo = RBACRepository()
    return repo.get_metrics()

@router.post("/simulate")
def simulate_rbac(payload: SimulationRequest, current_user: dict = Depends(get_current_user)):
    """
    Simulates a Casbin check without making the actual request.
    Records the simulation in the rbac_access_logs to demonstrate the dashboard working.
    """
    # Only allow managers to run simulations
    require_role(current_user, {"master", "admin"})
    
    is_allowed = enforcer.enforce(payload.simulate_role, payload.simulate_endpoint, payload.simulate_method)
    
    # Log it as a real attempt to populate the metrics dashboard
    repo = RBACRepository()
    action_str = "ALLOWED" if is_allowed else "DENIED"
    username = f"SIMULATION ({current_user.get('username', 'unknown')})"
    
    # Force synchronous logging here so the dashboard updates immediately
    repo.log_access(
        username=username,
        role=payload.simulate_role,
        endpoint=payload.simulate_endpoint,
        method=payload.simulate_method,
        action=action_str
    )
    
    return {
        "allowed": is_allowed,
        "detail": f"Casbin evaluated {payload.simulate_role} -> {payload.simulate_method} {payload.simulate_endpoint} as {action_str}"
    }
