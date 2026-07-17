from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from backend.app.database.session import get_db
from backend.app.config import settings

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

def get_current_user(token: str = Depends(oauth2_scheme)):
    """Validates JWT Token or permits bypass for development environments"""
    if not token:
        # Permissive default for sandbox local development
        return {"username": "officer_ksp", "role": "Investigator"}
        
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        return {"username": username, "role": payload.get("role", "Officer")}
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
