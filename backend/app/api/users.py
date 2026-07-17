from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from backend.app.database.session import get_db
from backend.app.database.models import User
from backend.app.dependencies import get_current_admin, hash_password

router = APIRouter(prefix="/users", tags=["User Management"])

# Access levels an admin can assign. "Admin" grants the same user-management
# console access being used to create/edit accounts here.
ALLOWED_ROLES = ["Admin", "Superintendent", "Investigator", "Analyst"]

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "Investigator"

class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

def _serialize(u: User):
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "created_by": u.created_by,
    }

@router.get("/")
def list_users(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Lists every console account. Admin only."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_serialize(u) for u in users]

@router.post("/", status_code=201)
def create_user(payload: CreateUserRequest, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Creates a new police console account. Admin only."""
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if payload.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ALLOWED_ROLES}")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        created_by=admin["username"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _serialize(user)

@router.patch("/{user_id}")
def update_user(user_id: int, payload: UpdateUserRequest, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Updates a user's access level, active status, and/or password. Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.role is not None:
        if payload.role not in ALLOWED_ROLES:
            raise HTTPException(status_code=400, detail=f"Role must be one of {ALLOWED_ROLES}")
        user.role = payload.role

    if payload.is_active is not None:
        if user.username == admin["username"] and not payload.is_active:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        user.is_active = payload.is_active

    if payload.password:
        if len(payload.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        user.password_hash = hash_password(payload.password)

    db.commit()
    db.refresh(user)
    return _serialize(user)

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Permanently removes a console account. Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == admin["username"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    db.delete(user)
    db.commit()
    return {"status": "deleted", "id": user_id}
