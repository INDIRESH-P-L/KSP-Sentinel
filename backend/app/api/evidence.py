"""Chain-of-custody API for digital evidence (additive — see NEW_FEATURES.md, Feature 4).

Every route here funnels its logging through app.services.evidence.log_evidence_action()
rather than writing EvidenceAccessLog rows itself, so the custody rule is enforced in one
place and cannot drift between endpoints.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.session import get_db
from app.database.models import FIR, EvidenceItem, EvidenceAccessLog
from app.core.security import deny_admin_from_crime_data, require_role
from app.services.evidence import (
    log_evidence_action, serialize_item, serialize_log, VALID_ACTIONS, MISMATCH,
    BASELINE_RECORDED,
)

router = APIRouter(prefix="/evidence", tags=["Evidence Chain of Custody"])

ITEM_TYPES = ("photo", "video", "audio", "document", "device_image", "cdr", "other")


def _actor(current_user: dict) -> str:
    return str(current_user.get("username") or "unknown")


def _get_item(db: Session, item_id: int) -> EvidenceItem:
    item = db.query(EvidenceItem).filter(EvidenceItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Evidence item not found")
    return item


class AddEvidenceRequest(BaseModel):
    item_type: str = Field(..., max_length=50, description=f"One of {ITEM_TYPES}")
    file_reference: str = Field(..., min_length=1, max_length=300,
                                description="Opaque pointer to the stored object; bytes are never read by this service")
    description: str | None = Field(None, max_length=2000)
    current_custodian: str | None = Field(None, max_length=100,
                                          description="Defaults to the officer adding the item")
    content_hash: str | None = Field(None, min_length=64, max_length=64,
                                     description="SHA-256 baseline reported by the system holding the bytes")


class EditEvidenceRequest(BaseModel):
    """Metadata corrections only. Every field here is a *description* of the evidence,
    never its custody state or its integrity state -- see the route docstring for what
    is deliberately not editable and why.

    extra="forbid" so an attempt to set a protected field (current_custodian,
    content_hash, integrity_flagged, added_by, fir_id) is rejected outright. Pydantic
    would otherwise drop it silently, leaving the caller believing a custody or
    integrity value had been changed when it had not -- a dangerous thing to be wrong
    about in an evidence system.
    """
    model_config = {"extra": "forbid"}

    description: str | None = Field(None, max_length=2000)
    item_type: str | None = Field(None, max_length=50)
    file_reference: str | None = Field(None, min_length=1, max_length=300)
    observed_hash: str | None = Field(None, min_length=64, max_length=64,
                                      description="Required when changing file_reference")
    reason: str = Field(..., min_length=5, max_length=300,
                        description="Why this correction is being made -- recorded in the custody trail")


class TransferRequest(BaseModel):
    new_custodian: str = Field(..., min_length=1, max_length=100)
    observed_hash: str | None = Field(None, min_length=64, max_length=64,
                                      description="SHA-256 observed at handover; omit if unavailable")
    note: str | None = Field(None, max_length=300)


@router.post("/{fir_id}/items")
def add_evidence_item(
    fir_id: int,
    payload: AddEvidenceRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("investigator")),
):
    """Registers a new evidence item against a case and writes its genesis 'added' row.

    Investigator clearance or above: adding evidence starts a custody chain that a court
    may later rely on, so it is not an Analyst-level action.
    """
    if payload.item_type not in ITEM_TYPES:
        raise HTTPException(status_code=422, detail=f"item_type must be one of {list(ITEM_TYPES)}")
    if not db.query(FIR).filter(FIR.id == fir_id).first():
        raise HTTPException(status_code=404, detail="FIR not found")

    actor = _actor(current_user)
    item = EvidenceItem(
        fir_id=fir_id,
        item_type=payload.item_type,
        file_reference=payload.file_reference,
        description=payload.description,
        added_by=actor,
        current_custodian=payload.current_custodian or actor,
        content_hash=(payload.content_hash or "").strip().lower() or None,
    )
    db.add(item)
    db.flush()   # need item.id for the log row, but keep both in one transaction

    log = log_evidence_action(db, item, accessed_by=actor, action="added",
                              observed_hash=payload.content_hash,
                              detail=f"Evidence registered against FIR {fir_id}", commit=False)
    db.commit()
    db.refresh(item)
    db.refresh(log)
    return {"message": "Evidence item added", "item": serialize_item(item), "log_entry": serialize_log(log)}


@router.get("/{fir_id}/items")
def list_evidence_items(
    fir_id: int,
    log_access: bool = Query(True, description="Write a 'viewed' custody row for each item returned"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
):
    """Lists evidence for a case.

    Listing IS an access, so by default each item returned gets a 'viewed' custody row —
    a court asking "who looked at this?" needs that answer. `log_access=false` exists for
    internal/UI polling that would otherwise flood the trail; it is a deliberate, visible
    choice by the caller rather than a silent omission.
    """
    if not db.query(FIR).filter(FIR.id == fir_id).first():
        raise HTTPException(status_code=404, detail="FIR not found")

    items = (db.query(EvidenceItem)
               .filter(EvidenceItem.fir_id == fir_id)
               .order_by(EvidenceItem.added_at.asc(), EvidenceItem.id.asc()).all())

    if log_access and items:
        actor = _actor(current_user)
        for it in items:
            # No bytes to hash on a read -> recorded as 'not_verified', never as verified.
            log_evidence_action(db, it, accessed_by=actor, action="viewed",
                                detail=f"Listed via /evidence/{fir_id}/items", commit=False)
        db.commit()

    return {
        "fir_id": fir_id,
        "count": len(items),
        "access_logged": bool(log_access and items),
        "items": [serialize_item(i) for i in items],
    }


@router.get("/item/{item_id}/history")
def evidence_history(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
):
    """Full custody trail for one item, oldest first.

    Reading the trail is deliberately NOT itself logged: the history endpoint reads the
    log, not the evidence, and self-logging would make the trail grow every time anyone
    audited it.

    Any integrity mismatch is surfaced at the top level (`integrity`), not buried among
    the rows — a flagged item must be impossible to miss.
    """
    item = _get_item(db, item_id)
    rows = (db.query(EvidenceAccessLog)
              .filter(EvidenceAccessLog.evidence_id == item_id)
              .order_by(EvidenceAccessLog.timestamp.asc(), EvidenceAccessLog.id.asc()).all())

    mismatches = [r for r in rows if r.verification == MISMATCH]
    unverified = sum(1 for r in rows if r.verification == "not_verified")

    integrity = {
        "integrity_flagged": bool(item.integrity_flagged),
        "integrity_flagged_at": item.integrity_flagged_at,
        "baseline_hash": item.content_hash,
        "mismatch_count": len(mismatches),
        "unverified_access_count": unverified,
        "status": "COMPROMISED — hash mismatch recorded" if item.integrity_flagged else "intact",
        "note": ("A reported hash did not match the recorded baseline. The baseline has NOT been "
                 "overwritten; both values are preserved in the log rows below."
                 if item.integrity_flagged else
                 "No hash mismatch has been reported for this item."),
    }
    if mismatches:
        first = mismatches[0]
        integrity["first_mismatch"] = {
            "at": first.timestamp, "by": first.accessed_by,
            "expected": first.hash_before, "observed": first.hash_after,
        }

    return {
        "item": serialize_item(item),
        "integrity": integrity,
        "custody_chain": [serialize_log(r) for r in rows],
        "entry_count": len(rows),
    }


@router.patch("/item/{item_id}/transfer")
def transfer_custody(
    item_id: int,
    payload: TransferRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("investigator")),
):
    """Hands custody to another officer, logging 'transferred' with hash re-verification.

    Investigator clearance or above — a custody handover is the step most likely to be
    challenged in court, so it is not an Analyst-level action.

    A reported hash that disagrees with the baseline does NOT block the transfer: the
    handover is a fact that still needs recording. The item is flagged instead, and the
    response says so plainly.
    """
    item = _get_item(db, item_id)
    actor = _actor(current_user)
    previous = item.current_custodian

    if payload.new_custodian.strip() == (previous or "").strip():
        raise HTTPException(
            status_code=409,
            detail="The item is already in that custodian's possession; nothing to transfer.",
        )

    log = log_evidence_action(
        db, item, accessed_by=actor, action="transferred",
        observed_hash=payload.observed_hash,
        # The from/to pair goes in its own columns so it survives regardless of what
        # the caller writes in `note`; the note is now additive, not a replacement.
        custodian_before=previous,
        custodian_after=payload.new_custodian,
        detail=(payload.note
                or f"Custody transferred from {previous} to {payload.new_custodian}"),
        commit=False,
    )
    item.current_custodian = payload.new_custodian
    db.commit()
    db.refresh(item)
    db.refresh(log)

    resp = {
        "message": "Custody transferred",
        "previous_custodian": previous,
        "current_custodian": item.current_custodian,
        "verification": log.verification,
        "item": serialize_item(item),
        "log_entry": serialize_log(log),
    }
    if log.verification == MISMATCH:
        resp["warning"] = (
            "INTEGRITY MISMATCH: the hash reported at handover does not match the recorded "
            "baseline. The item is now flagged and the baseline was left unchanged. The transfer "
            "was still recorded — verify the file against the original source before relying on it."
        )
    elif log.verification == "not_verified":
        resp["warning"] = (
            "No hash was supplied, so integrity could not be checked at this handover. "
            "The transfer is recorded as unverified."
        )
    return resp


@router.get("/actions")
def list_actions():
    """The custody action vocabulary, so a client doesn't have to hardcode it."""
    return {"actions": list(VALID_ACTIONS), "item_types": list(ITEM_TYPES)}


@router.patch("/item/{item_id}")
def edit_evidence_item(
    item_id: int,
    payload: EditEvidenceRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("investigator")),
):
    """Corrects an evidence item's metadata, logging 'modified' with a field-level diff.

    Investigator clearance or above -- the same bar as adding and transferring.

    A `reason` is mandatory. In a custody context an unexplained edit is nearly as bad
    as an unlogged one: the trail needs to answer *why* a record changed, not just that
    it did. The log detail records each field as `old -> new`.

    Deliberately NOT editable here:

      * `current_custodian` -- that is a handover, and routing it through this endpoint
        would bypass the 'transferred' action and its hash re-verification. Use
        PATCH /item/{id}/transfer.
      * `content_hash`, `integrity_flagged` -- letting a flagged item be "corrected"
        back to clean would defeat the entire tamper-detection mechanism. A raised flag
        is never cleared by an edit, including when the file_reference changes.
      * `added_by`, `added_at`, `fir_id` -- historical facts about how the item entered
        the system, not descriptions of it.

    Changing `file_reference` repoints the record at a different object, so a different
    hash is expected rather than suspicious. `observed_hash` is required in that case and
    is recorded as a re-baseline (old and new hashes both kept on the row), never as a
    mismatch. An already-flagged item stays flagged.
    """
    item = _get_item(db, item_id)
    actor = _actor(current_user)

    if payload.item_type is not None and payload.item_type not in ITEM_TYPES:
        raise HTTPException(status_code=422, detail=f"item_type must be one of {list(ITEM_TYPES)}")

    pointer_changed = (payload.file_reference is not None
                       and payload.file_reference != item.file_reference)
    if pointer_changed and not payload.observed_hash:
        raise HTTPException(
            status_code=422,
            detail="observed_hash is required when changing file_reference: the record will point "
                   "at a different object, and the custody trail must carry that object's fingerprint.",
        )

    # Build the diff before mutating, so the log describes the actual transition.
    changes = []
    for field in ("description", "item_type", "file_reference"):
        new_value = getattr(payload, field)
        if new_value is None:
            continue
        old_value = getattr(item, field)
        if new_value != old_value:
            changes.append((field, old_value, new_value))

    if not changes:
        raise HTTPException(status_code=400, detail="No changes supplied; nothing to record.")

    for field, _old, new_value in changes:
        setattr(item, field, new_value)

    def _short(v):
        text = "(empty)" if v in (None, "") else str(v)
        return text if len(text) <= 60 else text[:57] + "..."

    diff = "; ".join(f"{f}: {_short(o)} -> {_short(n)}" for f, o, n in changes)
    log = log_evidence_action(
        db, item, accessed_by=actor, action="modified",
        observed_hash=payload.observed_hash,   # always forwarded; `rebaseline` below is
                                       # what distinguishes a legitimate re-point
                                       # from a genuine integrity mismatch,
        rebaseline=pointer_changed,
        detail=f"{payload.reason.strip()} | {diff}",
        commit=False,
    )
    db.commit()
    db.refresh(item)
    db.refresh(log)

    resp = {
        "message": "Evidence item updated",
        "fields_changed": [f for f, _o, _n in changes],
        "reason": payload.reason.strip(),
        "item": serialize_item(item),
        "log_entry": serialize_log(log),
    }
    if pointer_changed:
        resp["note"] = (
            "file_reference changed, so the supplied hash was recorded as a new baseline "
            "(both the previous and new fingerprints are preserved on the log entry). "
            "This is not treated as tampering."
        )
        if item.integrity_flagged:
            resp["warning"] = (
                "This item remains INTEGRITY FLAGGED. Re-pointing the file reference does not "
                "clear a previously recorded mismatch."
            )
    return resp
