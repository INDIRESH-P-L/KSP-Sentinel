"""Append-only audit logging (backend.app.database.models.AuditLog).

log_action is synchronous and commits its own row immediately -- called from inside
request handlers that already have a live `db: Session`, not as background/deferred
work, so a security-relevant action (login, RBAC denial, evidence access) is never
lost if the request crashes right after.

Rule: never pass PII (names, phone numbers, addresses, Aadhaar) into `detail` or
`resource`. Log identifiers (fir_id, user_id, district_id), not the personal data
itself -- the audit log must not become a second place PII can leak from.
"""
import sys
import os
from sqlalchemy.orm import Session

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.models import AuditLog


def log_action(db: Session, user_id: int | None, action: str, resource: str | None = None,
                ip_address: str | None = None, user_agent: str | None = None,
                success: bool = True, detail: str | None = None, username: str | None = None) -> None:
    try:
        db.add(AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource=resource,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:500] or None,
            success=success,
            detail=(detail or "")[:500] or None,
        ))
        db.commit()
    except Exception:
        # Audit logging must never take down the request it's observing. If the
        # insert itself fails (e.g. DB hiccup), roll back so it doesn't poison the
        # caller's transaction and swallow the error -- this is best-effort telemetry,
        # not the system of record for the action itself.
        db.rollback()
