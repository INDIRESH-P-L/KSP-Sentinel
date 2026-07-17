from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from backend.app.config import settings
from backend.app.database.session import get_db
from backend.app.database.models import User, RefreshToken
from backend.app.dependencies import (
    verify_password, create_access_token, create_pre_auth_token, decode_pre_auth_token,
    generate_refresh_token, hash_refresh_token,
)
from backend.app.core import mfa
from backend.app.core.audit import log_action
from backend.app.core.brute_force import record_failed_login, clear_failed_logins
from backend.app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])


class VerifyOtpRequest(BaseModel):
    pre_auth_token: str
    code: str

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: str


def _client_ip(request: Request) -> str:
    # Trusts X-Forwarded-For only if you actually run behind a reverse proxy that
    # sets it; falls back to the direct peer address otherwise.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _issue_full_session(db: Session, username: str, role: str, district_id=None, station_id=None,
                         expires_minutes: int | None = None, user_id: int | None = None,
                         can_view_sensitive: bool = False):
    access_token = create_access_token(username, role, district_id, station_id, expires_minutes,
                                        user_id, can_view_sensitive)
    raw_refresh, refresh_hash = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user_id,  # None for the legacy demo path, which has no real User row
        token_hash=refresh_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "user": {"username": username, "role": role, "district_id": district_id, "station_id": station_id},
    }


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Step 1 of login: verify password. Returns either a full session (accounts
    without MFA enabled, and the legacy demo fallback) or an mfa_required response
    carrying a pre_auth_token for /api/auth/verify-otp."""
    username = form_data.username
    password = form_data.password
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "unknown")[:500]

    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        if not db_user.is_active:
            log_action(db, None, "login_blocked_inactive", "auth", ip, ua, success=False, username=username)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account has been deactivated. Contact your administrator.",
            )
        if not verify_password(password, db_user.password_hash):
            record_failed_login(ip)
            log_action(db, db_user.id, "login_failed_password", "auth", ip, ua, success=False, username=username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if db_user.mfa_enabled and db_user.totp_secret:
            # Not a failure, but not a completed login either -- counters are only
            # cleared once verify-otp actually succeeds, below.
            log_action(db, db_user.id, "login_password_ok_awaiting_mfa", "auth", ip, ua, success=True, username=username)
            return {"mfa_required": True, "pre_auth_token": create_pre_auth_token(username)}

        # Real account without MFA configured -- issue a full session directly.
        clear_failed_logins(ip)
        session = _issue_full_session(db, db_user.username, db_user.role, db_user.district_id,
                                       db_user.station_id, user_id=db_user.id,
                                       can_view_sensitive=db_user.can_view_sensitive)
        log_action(db, db_user.id, "login_success", "auth", ip, ua, success=True, username=username)
        return session

    # Legacy demo fallback for local command-center testing: any username not
    # registered as a real account, with password 'password', 'ksp123', or 'admin'.
    # This path can never reach MFA and can never be assigned role Admin.
    if password not in ["password", "ksp123", "admin"]:
        record_failed_login(ip)
        log_action(db, None, "login_failed_password", "auth", ip, ua, success=False, username=username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clear_failed_logins(ip)
    role = "Superintendent" if username in ["sp_admin", "keshav"] else "Investigator"
    session = _issue_full_session(db, username, role)
    log_action(db, None, "login_success_legacy", "auth", ip, ua, success=True, username=username)
    return session


@router.post("/verify-otp")
@limiter.limit("5/minute")
def verify_otp(payload: VerifyOtpRequest, request: Request, db: Session = Depends(get_db)):
    """Step 2 of login: exchanges a pre_auth_token + valid TOTP code for a real session."""
    username = decode_pre_auth_token(payload.pre_auth_token)
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "unknown")[:500]

    db_user = db.query(User).filter(User.username == username).first()
    if not db_user or not db_user.is_active or not db_user.totp_secret:
        log_action(db, db_user.id if db_user else None, "mfa_failed", "auth", ip, ua, success=False, username=username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA verification failed")

    plaintext_secret = mfa.decrypt_secret(db_user.totp_secret)
    matched_step = mfa.verify_totp_code(plaintext_secret, payload.code, last_used_step=db_user.last_totp_step)
    if matched_step is None:
        record_failed_login(ip)
        log_action(db, db_user.id, "mfa_failed", "auth", ip, ua, success=False, username=username,
                   detail="wrong code or replayed code")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication code")

    clear_failed_logins(ip)
    # Persisted before issuing tokens so this exact code can never be replayed again,
    # even by a second request that races in before the first one commits.
    db_user.last_totp_step = matched_step
    db.commit()

    session = _issue_full_session(
        db, db_user.username, db_user.role, db_user.district_id, db_user.station_id,
        expires_minutes=15,  # short-lived once MFA is in play; refreshed via /api/auth/refresh
        user_id=db_user.id, can_view_sensitive=db_user.can_view_sensitive,
    )
    log_action(db, db_user.id, "login_success_mfa", "auth", ip, ua, success=True, username=username)
    return session


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Rotates a refresh token: the old one is revoked and a new access+refresh pair
    is issued. Single-use rotation means a stolen-and-replayed old refresh token is
    immediately detectable (it'll already be marked revoked)."""
    token_hash = hash_refresh_token(payload.refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not row or row.revoked or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid or expired")

    user = db.query(User).filter(User.id == row.user_id).first() if row.user_id else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is no longer active")

    session = _issue_full_session(
        db, user.username, user.role, user.district_id, user.station_id,
        expires_minutes=15 if user.mfa_enabled else None,
        user_id=user.id, can_view_sensitive=user.can_view_sensitive,
    )
    new_hash = hash_refresh_token(session["refresh_token"])
    new_row = db.query(RefreshToken).filter(RefreshToken.token_hash == new_hash).first()

    row.revoked = True
    if new_row:
        row.replaced_by_id = new_row.id
    db.commit()
    return session


@router.post("/logout")
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    """Revokes a refresh token server-side so it can't be used again even if it leaks
    after the client discards it."""
    token_hash = hash_refresh_token(payload.refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if row:
        row.revoked = True
        db.commit()
    return {"status": "logged_out"}
