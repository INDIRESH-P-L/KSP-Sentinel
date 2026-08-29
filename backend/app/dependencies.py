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

def _credentials_error(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Resolves the caller's identity from a Bearer JWT. 401s if there isn't one.

    This function previously returned a fabricated "officer_ksp"/Investigator identity
    when NO token was presented ("permissive default for sandbox local development"),
    and mapped the literal string "demo_token" to a Superintendent with
    can_view_sensitive=True. Both were unconditional and shipped to production, which
    made every endpoint in the platform -- FIR records, victim data, the criminal
    network, patrol plans -- readable by any anonymous caller who could reach the
    port. They are gone. Authentication is mandatory; routes that are genuinely
    public depend on `get_optional_user` instead (see app/api/public.py).
    """
    if not token:
        raise _credentials_error("Authentication required")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise _credentials_error()

    username = payload.get("sub")
    if not username:
        raise _credentials_error()

    # A pre_auth token proves only "password verified" -- accepting one here would let
    # password-without-OTP act as a completed login. Tokens are now always minted with
    # an explicit type, so anything that is not "access" is refused (the old code
    # defaulted a missing type to "access" to keep legacy demo tokens working; that
    # path no longer exists).
    if payload.get("type") != "access":
        raise _credentials_error(
            "This token cannot be used to authenticate requests (MFA not completed)"
        )

    return {
        "username": username,
        "id": payload.get("uid"),
        "role": payload.get("role", "Officer"),
        "district_id": payload.get("district_id"),
        "station_id": payload.get("station_id"),
        "can_view_sensitive": payload.get("can_view_sensitive", False),
    }


def get_optional_user(token: str = Depends(oauth2_scheme)) -> dict | None:
    """Identity for genuinely public routes: returns the user when a valid token is
    present, None when it isn't. Never fabricates an identity, and never 401s.

    Used by the citizen-facing endpoints (public district safety, FIR status lookup)
    so they can log who acted when an officer happens to be signed in, without
    requiring it.
    """
    if not token:
        return None
    try:
        return get_current_user(token)
    except HTTPException:
        return None


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
