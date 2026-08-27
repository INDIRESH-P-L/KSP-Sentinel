"""Complainant contact registration (additive — see NEW_FEATURES.md, Feature 5).

Kept off the public router on purpose: everything under /api/public is documented as
unauthenticated, and attaching a complainant's phone to a case is emphatically not.

The number is never stored in the clear. Only an HMAC-SHA256 digest is kept, which means
this endpoint can register a number and the public checker can verify one, but nothing in
the system can read a number back out or message someone who has not supplied theirs.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.session import get_db
from app.database.models import FIR, FIRComplainantContact
from app.core.security import require_role, deny_admin_from_crime_data
from app.services.fir_status import phone_hmac, normalise_phone
from integrations.messaging_bot import CHANNELS, mask_phone

router = APIRouter(prefix="/complainant", tags=["Complainant Contact"])


class RegisterContactRequest(BaseModel):
    model_config = {"extra": "forbid"}

    phone: str = Field(..., min_length=10, max_length=20)
    preferred_channel: str | None = Field(None, max_length=20, description=f"One of {CHANNELS}")


@router.post("/{fir_id}/contact")
def register_contact(
    fir_id: int,
    payload: RegisterContactRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("investigator")),
):
    """Registers the phone a complainant may later use to check their case status.

    Investigator clearance: this attaches personal contact data to a case.

    Only the keyed digest is written. The response echoes a MASKED number so the officer
    can confirm what was captured without the full value entering logs or a screenshot.
    """
    if not db.query(FIR).filter(FIR.id == fir_id).first():
        raise HTTPException(status_code=404, detail="FIR not found")
    if payload.preferred_channel and payload.preferred_channel not in CHANNELS:
        raise HTTPException(status_code=422, detail=f"preferred_channel must be one of {list(CHANNELS)}")
    if len(normalise_phone(payload.phone)) < 10:
        raise HTTPException(status_code=422, detail="A valid 10-digit phone number is required.")

    digest = phone_hmac(payload.phone)
    existing = (db.query(FIRComplainantContact)
                  .filter(FIRComplainantContact.fir_id == fir_id,
                          FIRComplainantContact.phone_hmac == digest).first())
    if existing:
        return {"message": "Contact already registered for this case",
                "fir_id": fir_id, "phone": mask_phone(payload.phone), "created": False}

    db.add(FIRComplainantContact(
        fir_id=fir_id, phone_hmac=digest,
        preferred_channel=payload.preferred_channel,
        created_by=str(current_user.get("username") or "unknown"),
    ))
    db.commit()
    return {"message": "Contact registered", "fir_id": fir_id,
            "phone": mask_phone(payload.phone), "created": True}


@router.get("/{fir_id}/contacts")
def list_contacts(
    fir_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
):
    """How many contacts are registered against a case.

    Returns counts and channels only. There is no number to return -- by design the
    stored digest cannot be reversed, so this endpoint cannot leak one even if misused.
    """
    if not db.query(FIR).filter(FIR.id == fir_id).first():
        raise HTTPException(status_code=404, detail="FIR not found")
    rows = db.query(FIRComplainantContact).filter(FIRComplainantContact.fir_id == fir_id).all()
    return {
        "fir_id": fir_id,
        "count": len(rows),
        "contacts": [{"id": r.id, "preferred_channel": r.preferred_channel,
                      "created_at": r.created_at, "created_by": r.created_by,
                      "phone": "[stored as a keyed hash; not recoverable]"} for r in rows],
    }
