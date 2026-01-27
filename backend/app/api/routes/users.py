from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, require_role
from app.models.schemas import UserCreateRequest, UserPublic, UserUpdateRequest, RoleUpdateRequest
from app.db.repositories.users import UsersRepository

router = APIRouter()

@router.get("", response_model=list[UserPublic])
def list_users(current=Depends(get_current_user)) -> list[UserPublic]:
    require_role(current, allowed={"admin", "master"})
    return UsersRepository().list_users()

@router.post("", response_model=UserPublic)
def create_user(payload: UserCreateRequest, current=Depends(get_current_user)) -> UserPublic:
    require_role(current, allowed={"admin", "master"})
    if current["role"] == "admin" and payload.role != "staff":
        raise HTTPException(status_code=403, detail="Admins can only create staff users.")
    return UsersRepository().create_user(payload)

@router.put("/{username}", response_model=UserPublic)
def update_user(username: str, payload: UserUpdateRequest, current=Depends(get_current_user)) -> UserPublic:
    repo = UsersRepository()
    target = repo.get_user(username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if current["role"] == "master":
        pass
    elif current["role"] == "admin":
        if target["role"] != "staff":
            raise HTTPException(status_code=403, detail="Admins can only update staff users.")
    else:
        if current["username"] != username:
            raise HTTPException(status_code=403, detail="Not allowed.")

    return repo.update_user(username, payload)

@router.put("/{username}/role", response_model=UserPublic)
def update_role(username: str, payload: RoleUpdateRequest, current=Depends(get_current_user)) -> UserPublic:
    require_role(current, allowed={"master"})
    if username == current["username"] and payload.role != "master":
        raise HTTPException(status_code=400, detail="Master cannot demote themselves.")
    return UsersRepository().update_role(username, payload.role)

@router.delete("/{username}")
def delete_user(username: str, current=Depends(get_current_user)) -> dict:
    require_role(current, allowed={"master"})
    if username == current["username"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    ok = UsersRepository().delete_user(username)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"status": "ok", "message": f"Deleted user {username}."}
