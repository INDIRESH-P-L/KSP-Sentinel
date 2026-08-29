"""Time helpers anchored to the deployment's operational timezone.

Why this exists
---------------
This is a Karnataka State Police system: the duty day, the patrol roster and every
"today" an officer sees begin at 00:00 **IST**. Several modules computed day
boundaries with `datetime.utcnow().date()` instead, which places the boundary at
00:00 UTC = 05:30 IST. The consequences were not cosmetic:

  * `services/patrol.persist()` deleted "today's" assignments using that boundary,
    so a roster committed at 02:00 IST landed in the *previous* operational day and
    a re-run at 06:00 IST silently wiped it.
  * `GET /patrol/assignments/current` hid every assignment made between midnight and
    05:30 IST — the night shift could not see its own orders.

Timestamps are still *stored* naive-UTC (the existing columns are naive and the
whole schema assumes it). These helpers only convert at the boundary, where the
question "which operational day is this?" is asked.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None  # type: ignore

# Overridable so a deployment outside IST is a config change, not a code change.
OPERATIONAL_TIMEZONE = os.getenv("OPERATIONAL_TIMEZONE", "Asia/Kolkata")

# Fallback used when tzdata is unavailable (a bare container image, most often).
# IST is a fixed +05:30 with no DST, so a static offset is exact rather than an
# approximation.
_IST_FALLBACK = timezone(timedelta(hours=5, minutes=30))


def _tz() -> timezone:
    if ZoneInfo is not None:
        try:
            return ZoneInfo(OPERATIONAL_TIMEZONE)  # type: ignore[return-value]
        except Exception:
            pass
    return _IST_FALLBACK


def utc_now() -> datetime:
    """Current UTC time as a naive datetime, matching how the columns are stored.

    Prefer this over `datetime.utcnow()`, which is deprecated in Python 3.12+.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_now() -> datetime:
    """Current wall-clock time in the operational timezone (tz-aware)."""
    return datetime.now(_tz())


def local_day_start_utc() -> datetime:
    """Naive-UTC instant at which the current operational day began.

    For IST this is 18:30 UTC on the previous calendar date. Compare stored
    (naive-UTC) timestamps against this to mean "since midnight local".
    """
    start_local = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc).replace(tzinfo=None)


def to_naive_utc(value: datetime) -> datetime:
    """Normalises any datetime to naive UTC.

    A tz-aware value parsed from user input (e.g. `2026-01-01T00:00:00+05:30`) would
    otherwise be compared against naive stored values, which raises TypeError, or be
    silently truncated by the DB driver — dropping the offset and shifting the
    instant by hours.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
