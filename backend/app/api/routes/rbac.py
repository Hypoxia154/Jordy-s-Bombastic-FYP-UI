from fastapi import APIRouter, Depends
from app.core.deps import check_permission
from app.db.repositories.rbac import RBACRepository

router = APIRouter()

@router.get("/metrics", dependencies=[Depends(check_permission)])
def get_rbac_metrics():
    """
    Returns aggregated RBAC access logs for the master dashboard.
    Protected by Casbin (only master/admin should have access).
    """
    repo = RBACRepository()
    return repo.get_metrics()
