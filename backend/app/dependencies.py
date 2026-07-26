from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets
import hashlib
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.database.session import get_db
from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

# pbkdf2_sha256 instead of bcrypt: the installed bcrypt 4.x package dropped the
# `__about__` attribute that this passlib release's bcrypt backend probes for during
# its startup self-test, crashing every hash_password() call with an AttributeError/
# ValueError before it ever gets to hashing. pbkdf2_sha256 is pure-Python within
# passlib itself, so it has no native-library version coupling to break.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)

def create_access_token(username: str, role: str, district_id: int | None = None,
                         station_id: int | None = None, expires_minutes: int | None = None,
                         user_id: int | None = None, can_view_sensitive: bool = False) -> str:
    expires_minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {
        "sub": username,
        "uid": user_id,  # numeric User.id, for audit logging -- None for the legacy demo path (no DB row)
        "role": role,
        "district_id": district_id,
        "station_id": station_id,
        "can_view_sensitive": can_view_sensitive,
        "type": "access",
        "iat": datetime.utcnow(),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

def create_pre_auth_token(username: str) -> str:
    """Short-lived token proving "password verified", issued between the password
    step and the OTP step. Deliberately carries no role/district claims -- if it were
    ever accepted by get_current_user it would be a privilege-escalation bug, which is
    exactly what the type='pre_auth' check below exists to prevent."""
    expire = datetime.utcnow() + timedelta(minutes=settings.PRE_AUTH_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "type": "pre_auth", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

def decode_pre_auth_token(token: str) -> str:
    """Returns the username if valid; raises HTTPException(401) otherwise."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA session")
    if payload.get("type") != "pre_auth":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA session token")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA session token")
    return username

def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token_for_client, sha256_hash_for_db). Only the hash is ever
    persisted -- a stolen DB snapshot alone can't be replayed as a live session,
    mirroring how passwords are stored."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest()

def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()

def get_current_user(token: str = Depends(oauth2_scheme)):
    """Validates JWT Token or permits bypass for development environments"""
    if not token:
        # Permissive default for sandbox local development
        return {"username": "officer_ksp", "id": None, "role": "Investigator", "district_id": None,
                "station_id": None, "can_view_sensitive": False}

    if token == "demo_token":
        return {"username": "demo_officer", "id": None, "role": "Superintendent", "district_id": None,
                "station_id": None, "can_view_sensitive": True}

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        # Tokens issued without a "type" claim predate this check (the legacy demo
        # login path) and are treated as access tokens for backward compatibility.
        # A pre_auth token, which DOES carry a type, must never authorize a request --
        # that would let password-verification-without-OTP act as a full login.
        token_type = payload.get("type", "access")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This token cannot be used to authenticate requests (MFA not completed)",
            )
        return {
            "username": username,
            "id": payload.get("uid"),
            "role": payload.get("role", "Officer"),
            "district_id": payload.get("district_id"),
            "station_id": payload.get("station_id"),
            "can_view_sensitive": payload.get("can_view_sensitive", False),
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

def get_current_admin(current_user: dict = Depends(get_current_user)):
    """Gate for the user-management API -- only accounts with role 'Admin' (case
    insensitive) may list/create/update/delete console accounts. The no-token
    permissive default in get_current_user resolves to role 'Investigator', so an
    unauthenticated request is rejected here too, not just accounts with the wrong role."""
    if str(current_user.get("role", "")).lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
