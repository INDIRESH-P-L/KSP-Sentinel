"""Feature 5 — public FIR status lookup.

Two rules govern everything here.

    1. MINIMUM DISCLOSURE. The response carries a status label and nothing else. No
       station, no officer, no dates, no sections, no accused, no victim. Someone
       holding an FIR number and a phone gets progress, not a case file.

    2. NO ENUMERATION ORACLE. An unknown FIR number and a wrong phone return the
       BYTE-IDENTICAL failure response. If they differed, anyone could walk the FIR
       number space and learn which cases exist -- which is itself disclosure, even
       without a status attached.

Phone verification compares HMAC-SHA256 digests keyed with SECRET_KEY; the number is
never stored in the clear (see FIRComplainantContact).
"""
import hashlib
import hmac
import os
import re
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sqlalchemy.orm import Session
from app.database.models import FIR, FIRComplainantContact
from app.config import settings

# FIR.status -> the four public labels. TRIAL folds into "Chargesheet Filed" because a
# trial necessarily follows one, and the public vocabulary is deliberately only four
# states wide; a fifth would leak procedural detail the brief did not ask to expose.
STATUS_LABELS = {
    "REGISTERED": "Registered",
    "INVESTIGATING": "Under Investigation",
    "UNDER_INVESTIGATION": "Under Investigation",
    "CHARGE_SHEETED": "Chargesheet Filed",
    "CHARGESHEETED": "Chargesheet Filed",
    "TRIAL": "Chargesheet Filed",
    "CLOSED": "Closed",
    "DISPOSED": "Closed",
}
DEFAULT_LABEL = "Registered"

# One message for both failure modes. Deliberately vague about which check failed.
GENERIC_FAILURE = (
    "We could not match that FIR number with the phone number provided. "
    "Please check both and try again, or contact the police station where the "
    "complaint was filed."
)


def normalise_phone(phone: str) -> str:
    """Reduce to digits and keep the last 10.

    Indian numbers arrive as 9845012345, +919845012345, 09845012345 and 91 9845012345.
    Normalising to the last 10 digits means the same person verifies whichever form they
    type, and the stored digest does not depend on formatting.
    """
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else digits


def phone_hmac(phone: str) -> str:
    """Keyed digest. The key is what stops a 10-digit keyspace being brute-forced."""
    normalised = normalise_phone(phone)
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        normalised.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def public_status_label(raw_status: str | None) -> str:
    return STATUS_LABELS.get((raw_status or "").strip().upper(), DEFAULT_LABEL)


def check_status(db: Session, fir_number: str, phone: str) -> dict:
    """Verify and return the public status, or an indistinguishable failure."""
    failure = {"verified": False, "status": None, "message": GENERIC_FAILURE}

    normalised = normalise_phone(phone)
    if len(normalised) < 10:
        # Too short to be a real number. Same shape as any other failure so a caller
        # cannot use validation strictness to infer anything either.
        return failure

    fir = db.query(FIR).filter(FIR.fir_number == fir_number.strip()).first()
    expected = phone_hmac(phone)

    # Always compute the comparison, even when the FIR is missing, so the work done is
    # not obviously different between the two failure paths.
    contacts = (db.query(FIRComplainantContact)
                  .filter(FIRComplainantContact.fir_id == (fir.id if fir else -1)).all())
    matched = any(hmac.compare_digest(c.phone_hmac, expected) for c in contacts)

    if fir is None or not matched:
        return failure

    return {
        "verified": True,
        "fir_number": fir.fir_number,
        "status": public_status_label(fir.status),
        "message": f"FIR {fir.fir_number} is currently '{public_status_label(fir.status)}'.",
    }
