"""Field-level PII masking, applied server-side to response payloads.

The frontend is never trusted to hide anything -- every field here is masked (or
redacted entirely) before it leaves the API, based on the caller's role and the
per-record `sensitive` flag (IPC 228A / BNS equivalent identity-protection).

Rules (see mask_person below):
  - `sensitive` record: identity fields (name, address, id_reference) are masked for
    EVERYONE, regardless of role, unless the caller has the `can_view_sensitive`
    break-glass grant (backend/app/database/models.py::User.can_view_sensitive).
  - Non-sensitive record, role Superintendent: no masking.
  - Non-sensitive record, role Investigator: name visible, address hidden,
    id_reference (Aadhaar-equivalent) shown only as a fixed masked pattern.
  - Non-sensitive record, role Analyst (or any other/unknown role): every personal
    field redacted.
"""

REDACTED = "[REDACTED]"
SENSITIVE_REDACTED = "[REDACTED - Sensitive]"
MASKED_ID = "****-****-****"


def mask_field(value, show_chars: int = 0) -> str:
    """Generic partial mask: keeps the last `show_chars` characters, replaces the
    rest with a fixed-width block of asterisks so the masked value doesn't itself
    leak the original length."""
    if not value:
        return ""
    value = str(value)
    if show_chars <= 0 or show_chars >= len(value):
        return "*" * 8
    return "*" * 8 + value[-show_chars:]


def mask_person(person: dict, role: str, can_view_sensitive: bool = False, is_sensitive: bool = False) -> dict:
    """Applies masking to a dict with (a subset of) the keys: name, address,
    id_reference, age, gender. Only keys present in the input are touched, so
    callers can pass whatever subset they actually have."""
    masked = dict(person)
    role_l = (role or "").lower()

    if is_sensitive and not can_view_sensitive:
        # Identity suppressed for every role -- this is the IPC 228A case, not an
        # access-level distinction.
        if "name" in masked:
            masked["name"] = SENSITIVE_REDACTED
        if "address" in masked:
            masked["address"] = SENSITIVE_REDACTED
        if "id_reference" in masked:
            masked["id_reference"] = SENSITIVE_REDACTED
        return masked

    if role_l == "superintendent":
        return masked  # full visibility

    if role_l == "investigator":
        if "address" in masked:
            masked["address"] = REDACTED
        if "id_reference" in masked and masked.get("id_reference"):
            masked["id_reference"] = MASKED_ID
        # name/age/gender remain visible for an Investigator working the case
        return masked

    # Analyst, or any unrecognized role: full redaction of personal fields.
    for key in ("name", "address", "id_reference", "gender", "age"):
        if key in masked:
            masked[key] = REDACTED
    return masked
