"""Public, unauthenticated API (additive — see NEW_FEATURES.md, Feature 4).

Everything on this router is world-readable, so it carries NO auth dependency by
design. That makes the sanitisation boundary the only thing standing between this and
the operational data, which is why the payload is assembled by an explicit allow-list in
app/services/public_safety.py rather than by serialising rows.

Nothing here touches persons, accused, victims, officers, police stations, FIR details,
evidence, nudges or patrol.
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.core.rate_limit import limiter
from app.config import settings
from app.database.session import get_db
from app.services.public_safety import get_public_safety
from app.services.fir_status import check_status
from integrations.messaging_bot import get_sender, build_status_message, CHANNELS, CHANNEL_SMS

router = APIRouter(prefix="/public", tags=["Public"])


@router.get("/district-safety")
@limiter.limit("30/minute")
def district_safety(request: Request):
    """District-level safety guidance for the public page. No authentication.

    Rate-limited on top of the global per-IP cap: this is the one route anyone on the
    internet can reach, and the payload is cached, so a tighter limit costs legitimate
    users nothing.
    """
    payload = get_public_safety()
    if not payload.get("available"):
        raise HTTPException(status_code=503,
                            detail=payload.get("reason", "Public safety data is unavailable."))
    return payload


# ── Feature 5: public FIR status check ──────────────────────────────────────

class FIRStatusRequest(BaseModel):
    """FIR number plus the phone on file. Nothing else is accepted."""
    model_config = {"extra": "forbid"}

    fir_number: str = Field(..., min_length=3, max_length=50)
    phone: str = Field(..., min_length=10, max_length=20,
                       description="Complainant phone on file; any common Indian format")
    notify: bool = Field(False, description="Also send the status as a message")
    channel: str = Field(CHANNEL_SMS, description=f"One of {CHANNELS}")


@router.post("/fir-status")
@limiter.limit(settings.FIR_STATUS_RATE_LIMIT)
def fir_status(request: Request, payload: FIRStatusRequest, db: Session = Depends(get_db)):
    """Current status of one FIR, for the complainant. No authentication.

    Returns ONLY a status label -- never the station, officer, dates, sections, accused
    or victim. Someone holding an FIR number and a phone gets progress, not a case file.

    An unknown FIR number and a wrong phone produce the SAME response, so the endpoint
    cannot be walked to discover which FIR numbers exist. It is rate-limited more
    tightly than the rest of this router because it takes user input.

    `notify` currently routes through the STUB sender: the message is logged, never
    delivered, and every result carries simulated=true. No messaging provider is
    configured -- see integrations/messaging_bot.py.
    """
    result = check_status(db, payload.fir_number, payload.phone)

    if not result["verified"]:
        # 200, not 404: a 404 would itself confirm the FIR number does not exist.
        return {
            "verified": False,
            "status": None,
            "message": result["message"],
            "notified": False,
        }

    notified = None
    if payload.notify:
        channel = payload.channel if payload.channel in CHANNELS else CHANNEL_SMS
        sender = get_sender()
        send_result = sender.send(
            payload.phone,
            build_status_message(result["fir_number"], result["status"]),
            channel=channel,
        )
        notified = send_result.as_dict()

    return {
        "verified": True,
        "fir_number": result["fir_number"],
        "status": result["status"],
        "message": result["message"],
        "notified": notified,
    }

