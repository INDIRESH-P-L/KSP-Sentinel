from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from backend.app.database.session import get_db
from backend.app.database.models import User
from backend.app.dependencies import get_current_admin, hash_password
from backend.app.core import mfa
from backend.app.core.audit import log_action

router = APIRouter(prefix="/users", tags=["User Management"])

# Access levels an admin can assign. "Admin" grants the same user-management
# console access being used to create/edit accounts here.
ALLOWED_ROLES = ["Admin", "Superintendent", "Investigator", "Analyst"]

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "Investigator"
    district_id: Optional[int] = None
    station_id: Optional[int] = None

class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    district_id: Optional[int] = None
    station_id: Optional[int] = None
    clear_district: bool = False  # explicit unset, since district_id=None is ambiguous with "don't change"
    clear_station: bool = False
    can_view_sensitive: Optional[bool] = None

def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _serialize(u: User):
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "mfa_enabled": u.mfa_enabled,
        "district_id": u.district_id,
        "station_id": u.station_id,
        "can_view_sensitive": u.can_view_sensitive,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "created_by": u.created_by,
    }

@router.get("/")
def list_users(db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Lists every console account. Admin only."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_serialize(u) for u in users]

@router.post("/", status_code=201)
def create_user(payload: CreateUserRequest, request: Request, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Creates a new police console account with MFA enrolled by default. Admin only.

    The plaintext TOTP secret and its otpauth:// provisioning URI are returned ONCE,
    in this response only -- give them to the officer to scan into an authenticator
    app immediately. After this call the secret exists only encrypted at rest; it
    cannot be retrieved again (use POST /{user_id}/reset-mfa if it's lost)."""
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

    plaintext_secret = mfa.generate_totp_secret()
    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        created_by=admin["username"],
        totp_secret=mfa.encrypt_secret(plaintext_secret),
        mfa_enabled=True,
        district_id=payload.district_id,
        station_id=payload.station_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_action(db, admin.get("id"), "user_created", f"user:{user.id}",
               _client_ip(request), request.headers.get("user-agent"),
               success=True, username=admin["username"], detail=f"created={username},role={payload.role}")

    return {
        **_serialize(user),
        "totp_secret": plaintext_secret,
        "otpauth_uri": mfa.provisioning_uri(plaintext_secret, username),
    }

@router.post("/{user_id}/reset-mfa")
def reset_mfa(user_id: int, request: Request, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Issues a brand new TOTP secret for a user who lost their authenticator device,
    invalidating the old one. Returned once, same as account creation. Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plaintext_secret = mfa.generate_totp_secret()
    user.totp_secret = mfa.encrypt_secret(plaintext_secret)
    user.mfa_enabled = True
    db.commit()

    log_action(db, admin.get("id"), "user_mfa_reset", f"user:{user.id}",
               _client_ip(request), request.headers.get("user-agent"),
               success=True, username=admin["username"])

    return {
        "id": user.id,
        "username": user.username,
        "totp_secret": plaintext_secret,
        "otpauth_uri": mfa.provisioning_uri(plaintext_secret, user.username),
    }

@router.patch("/{user_id}")
def update_user(user_id: int, payload: UpdateUserRequest, request: Request, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Updates a user's access level, active status, district/station scope, and/or
    password. Admin only."""
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

    if payload.clear_district:
        user.district_id = None
    elif payload.district_id is not None:
        user.district_id = payload.district_id

    if payload.clear_station:
        user.station_id = None
    elif payload.station_id is not None:
        user.station_id = payload.station_id

    if payload.can_view_sensitive is not None:
        user.can_view_sensitive = payload.can_view_sensitive

    db.commit()
    db.refresh(user)

    log_action(db, admin.get("id"), "user_updated", f"user:{user.id}",
               _client_ip(request), request.headers.get("user-agent"),
               success=True, username=admin["username"])

    return _serialize(user)

@router.delete("/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    """Permanently removes a console account. Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == admin["username"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    db.delete(user)
    db.commit()

    log_action(db, admin.get("id"), "user_deleted", f"user:{user_id}",
               _client_ip(request), request.headers.get("user-agent"),
               success=True, username=admin["username"], detail=f"deleted={user.username}")

    return {"status": "deleted", "id": user_id}
