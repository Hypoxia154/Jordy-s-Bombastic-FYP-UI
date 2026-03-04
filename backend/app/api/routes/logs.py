from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from app.core.deps import get_current_user, check_permission
from app.db.repositories.logs import LogsRepository

router = APIRouter()

@router.get("", response_model=List[Dict[str, Any]])
def get_system_logs(current=Depends(get_current_user), _=Depends(check_permission)) -> List[Dict[str, Any]]:
    """Fetch the latest 500 error logs. Requires master privileges via Casbin."""
    return LogsRepository().get_logs(limit=200)

@router.delete("")
def clear_system_logs(current=Depends(get_current_user), _=Depends(check_permission)) -> dict:
    """Wipe all system logs."""
    LogsRepository().clear_logs()
    return {"status": "ok", "message": "Logs cleared."}
