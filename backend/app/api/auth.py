from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from backend.app.config import settings
from backend.app.database.session import get_db
from backend.app.database.models import User
from backend.app.dependencies import verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])

def _issue_token(username: str, role: str):
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + access_token_expires

    payload = {"sub": username, "role": role, "exp": expire}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"username": username, "role": role}
    }

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Validates police credentials and issues JWT security token"""
    username = form_data.username
    password = form_data.password

    # Real accounts created through the admin console take priority over the demo
    # fallback below -- this is also the only path that can ever grant role "Admin".
    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        if not db_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated. Contact your administrator.",
            )
        if not verify_password(password, db_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return _issue_token(db_user.username, db_user.role)

    # Legacy demo fallback for local command-center testing: any username not
    # registered as a real account, with password 'password', 'ksp123', or 'admin'.
    if password not in ["password", "ksp123", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = "Superintendent" if username in ["sp_admin", "keshav"] else "Investigator"
    return _issue_token(username, role)
