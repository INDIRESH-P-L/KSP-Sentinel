"""Feature 4 — chain-of-custody service for digital evidence.

Every read, transfer or modification of an evidence item goes through
`log_evidence_action()`. Keeping that in one function is the point: a route that
forgets to log is a broken chain of custody, and a broken chain is the kind of defect
that surfaces in court rather than in a test run.

    Integrity checking with an opaque file reference.
    `file_reference` is an opaque pointer -- this service never holds the bytes, so it
    physically cannot recompute a SHA-256. The hash therefore travels *inbound*: the
    system that does hold the bytes reports an `observed_hash`, which is compared
    against the stored baseline.

      observed matches baseline  -> "verified"
      observed differs           -> "integrity_mismatch": the item is flagged and the
                                    baseline is deliberately LEFT INTACT, so the
                                    original fingerprint stays on record instead of
                                    being silently overwritten
      no observed hash supplied  -> "not_verified", recorded as such

    That last case matters: a log row must never imply an integrity check that never
    happened. "not_verified" is an honest record; silently writing the old hash into
    hash_after would be a lie about what was checked.
"""
import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sqlalchemy.orm import Session
from app.database.models import EvidenceItem, EvidenceAccessLog
from app.core.timeutil import utc_now

# Chain-of-custody actions. 'added' is the genesis row for an item.
VALID_ACTIONS = ("added", "viewed", "modified", "transferred", "exported")

VERIFIED = "verified"
MISMATCH = "integrity_mismatch"
NOT_VERIFIED = "not_verified"
BASELINE_RECORDED = "baseline_recorded"


def log_evidence_action(
    db: Session,
    item: EvidenceItem,
    accessed_by: str,
    action: str,
    observed_hash: str | None = None,
    detail: str | None = None,
    commit: bool = True,
    rebaseline: bool = False,
    custodian_before: str | None = None,
    custodian_after: str | None = None,
) -> EvidenceAccessLog:
    """Appends one chain-of-custody row and applies any integrity consequence.

    `rebaseline=True` is for the one case where a *different* hash is legitimate: the
    file_reference itself was corrected, so the record now points at a different object
    which naturally has a different fingerprint. Comparing it to the old baseline would
    report tampering that did not happen. It records the old and new hashes side by side
    and moves the baseline forward -- but it deliberately does NOT clear an existing
    integrity flag, so a pointer swap cannot be used to launder an item that was already
    flagged.

    Returns the created log row. Raises ValueError on an unknown action rather than
    silently recording an unrecognised one -- an unparseable custody trail is worse
    than a rejected request.
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"Unknown evidence action {action!r}; expected one of {VALID_ACTIONS}")

    baseline = item.content_hash
    observed = (observed_hash or "").strip().lower() or None

    if action == "added":
        # Genesis row: there is no prior state to compare against.
        verification = BASELINE_RECORDED if observed else NOT_VERIFIED
        hash_before, hash_after = None, observed
    elif rebaseline and observed is not None:
        # The pointer changed, so a differing hash is expected, not suspicious.
        # Both values are kept on the row; any existing flag is left standing.
        verification = BASELINE_RECORDED
        hash_before, hash_after = baseline, observed
        item.content_hash = observed
    elif observed is None:
        verification = NOT_VERIFIED
        hash_before, hash_after = baseline, None
    elif baseline is None:
        # First hash ever reported for this item — record it as the baseline.
        verification = BASELINE_RECORDED
        hash_before, hash_after = None, observed
        item.content_hash = observed
    elif observed == baseline:
        verification = VERIFIED
        hash_before, hash_after = baseline, observed
    else:
        # Mismatch. Flag the item; do NOT overwrite the baseline.
        verification = MISMATCH
        hash_before, hash_after = baseline, observed
        item.integrity_flagged = True
        item.integrity_flagged_at = utc_now()

    row = EvidenceAccessLog(
        evidence_id=item.id,
        accessed_by=accessed_by,
        action=action,
        timestamp=utc_now(),
        hash_before=hash_before,
        hash_after=hash_after,
        verification=verification,
        custodian_before=custodian_before,
        custodian_after=custodian_after,
        detail=(detail or "")[:300] or None,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def serialize_item(item: EvidenceItem) -> dict:
    return {
        "id": item.id,
        "fir_id": item.fir_id,
        "item_type": item.item_type,
        "file_reference": item.file_reference,
        "description": item.description,
        "added_by": item.added_by,
        "added_at": item.added_at,
        "current_custodian": item.current_custodian,
        "content_hash": item.content_hash,
        "integrity_flagged": bool(item.integrity_flagged),
        "integrity_flagged_at": item.integrity_flagged_at,
    }


def serialize_log(row: EvidenceAccessLog) -> dict:
    return {
        "id": row.id,
        "evidence_id": row.evidence_id,
        "accessed_by": row.accessed_by,
        "action": row.action,
        "timestamp": row.timestamp,
        "hash_before": row.hash_before,
        "hash_after": row.hash_after,
        "verification": row.verification,
        # Structured custody transition. Without these the history endpoint could not
        # answer "who held this item on date X" once a caller supplied a note, because
        # the note replaced the only place the from/to pair was recorded.
        "custodian_before": row.custodian_before,
        "custodian_after": row.custodian_after,
        "detail": row.detail,
    }
