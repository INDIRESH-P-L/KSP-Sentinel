"""Isolated data-loading module: serves API data straight from CSVs in the Catalyst
FileStore, bypassing the Datastore entirely.

Scope (deliberately narrow -- see the task this was built for):
  * ONLY reads. Never writes to, creates, or modifies any Datastore table or FileStore
    object. Download-only.
  * ONLY powers GET /api/reviews/ right now. The monthly crime-review CSVs
    (CRIME_REVIEW_FOR_THE_MONTH_OF_*.csv) live in the FileStore `ksp` folder as ~64
    small files (~60-85 KB each). They are parsed into the exact shape reviews.py
    already returns, then cached in memory on first use.

Why in-memory-cache-on-first-use rather than per-request: even though these particular
files are small, re-downloading + re-parsing 64 files on every request would add
seconds of latency per call for data that changes at most monthly. The cache is built
lazily on the first /reviews request (not at import time) so a FileStore/SDK outage
can't block server startup.

Auth/SDK: reuses the exact same zcatalyst_sdk.initialize() + file_store() pattern as
backend/app/core/storage.py, and the folder id from settings.CATALYST_FOLDER_ID (the
`ksp` FileStore folder). No new credentials or config are introduced.

Failure policy: every public function is total -- on ANY error (SDK init failure, folder
/ file download failure, malformed CSV) it logs a clear error and returns None. Callers
(the route handlers) treat None as "fall back to the existing Datastore/mock path" and
never crash.
"""
import io
import os
import re
import threading
from typing import Optional

from app.config import settings
from app.logging import logger

# Filename -> (month, year). Tolerant of the real-world names actually in the folder,
# which the stricter scripts/import_monthly_reviews.py regex would reject:
#   CRIME_REVIEW_FOR_THE_MONTH_OF_JANUARY_2025_0_5.csv   (trailing _0_5 export suffix)
#   CRIME_REVEIW_FOR_THE_MONTH_OF_JUNE_2024.csv          (REVEIW typo in source)
#   Crime_Review_for_the_month_of_August_2022.csv        (mixed case)
_MONTH_YEAR_RE = re.compile(r"MONTH[_ ]OF[_ ]([A-Z]+)[_ ](\d{4})", re.IGNORECASE)
_IS_REVIEW_FILE_RE = re.compile(r"CRIME[_ ]REV[EI]{2}W", re.IGNORECASE)  # matches REVIEW and the REVEIW typo

_MONTH_MAP = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
}

# Built lazily by _ensure_loaded(); a list of dicts already in /api/reviews/ item shape.
_reviews_cache: Optional[list] = None
_cache_lock = threading.Lock()

# Reuse a single SDK app instance across calls, same idea as storage.py's singleton.
_catalyst_app = None


def _parse_month_year(filename: str):
    """Returns (month:int, year:int) from a review filename, or None if it isn't one."""
    if not _IS_REVIEW_FILE_RE.search(filename):
        return None
    m = _MONTH_YEAR_RE.search(filename)
    if not m:
        return None
    month = _MONTH_MAP.get(m.group(1).upper())
    if not month:
        return None
    return month, int(m.group(2))


def _get_catalyst_app():
    """Lazily initialize (once) and return the Catalyst SDK app, or None on failure."""
    global _catalyst_app
    if _catalyst_app is not None:
        return _catalyst_app
    try:
        import zcatalyst_sdk
        _catalyst_app = zcatalyst_sdk.initialize()
        logger.info("filestore_data: Zoho Catalyst SDK initialized for FileStore reads.")
        return _catalyst_app
    except Exception as e:
        logger.error(f"filestore_data: could not initialize Catalyst SDK ({e}). "
                     f"/reviews will fall back to the Datastore path.")
        return None


def _download_folder_csvs():
    """Yields (filename, raw_bytes) for every file in the configured FileStore folder.

    Uses the same file_store().get_folder_instance(folder_id) entry point as
    core/storage.py. Individual file failures are logged and skipped rather than
    aborting the whole load.
    """
    app = _get_catalyst_app()
    if app is None:
        return

    if not settings.CATALYST_FOLDER_ID:
        logger.error("filestore_data: CATALYST_FOLDER_ID is not configured; cannot locate the review CSVs.")
        return

    try:
        folder_id = int(settings.CATALYST_FOLDER_ID)
        folder = app.file_store().get_folder_instance(folder_id)
        files = folder.get_paged_files()  # SDK: lists files in the folder
    except Exception as e:
        logger.error(f"filestore_data: failed to list files in FileStore folder "
                     f"{settings.CATALYST_FOLDER_ID} ({e}).")
        return

    # get_paged_files() may return a dict with a 'data' list depending on SDK version;
    # normalize both shapes defensively.
    if isinstance(files, dict):
        files = files.get("data", []) or []

    for f in files:
        try:
            file_name = f.get("file_name") if isinstance(f, dict) else getattr(f, "file_name", None)
            file_id = f.get("id") if isinstance(f, dict) else getattr(f, "id", None)
            if not file_name or file_id is None:
                continue
            if _parse_month_year(file_name) is None:
                continue  # not a monthly-review CSV -- skip (e.g. FIR dumps, xlsx)
            raw = folder.download_file(int(file_id))  # SDK: returns file bytes
            if isinstance(raw, str):
                raw = raw.encode("utf-8", errors="ignore")
            yield file_name, raw
        except Exception as e:
            logger.error(f"filestore_data: failed to download review file "
                         f"'{file_name if 'file_name' in dir() else '?'}' ({e}); skipping it.")
            continue


def _parse_review_csv(filename: str, raw: bytes, start_id: int) -> list:
    """Parses one monthly-review CSV into /api/reviews/ item dicts.

    Column resolution mirrors scripts/import_monthly_reviews.py (fuzzy header matching),
    since these are the same source files. month/year come from the filename, not a
    column. `id` is synthesized sequentially -- these files carry no stable row id, and
    the endpoint's id is only used for client-side keying.
    """
    import pandas as pd

    my = _parse_month_year(filename)
    if my is None:
        return []
    month, year = my

    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
    except Exception as e:
        logger.error(f"filestore_data: could not parse review CSV '{filename}' ({e}); skipping.")
        return []

    hdrs = [str(h).strip() for h in df.columns]

    def find_col(name_options):
        for opt in name_options:
            for h in hdrs:
                if opt.lower() in h.lower():
                    return h
        return None

    c_sl = find_col(["Sl.No", "Sl. No", "Sl No"])
    c_heads = find_col(["Heads of Crime", "Heads"])
    c_major = find_col(["Major Heads", "Major"])
    c_minor = find_col(["Minor Heads", "Minor"])
    c_upto = find_col(["upto the end of month", "During the current year upto"])
    c_prev_month = find_col(["previous month"])
    c_curr_month = find_col(["current month", "During the current month"])

    def to_int(v):
        if v is None:
            return None
        v = str(v).strip().replace(",", "")
        if not v:
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return None

    def cell(row, col):
        if not col:
            return None
        val = str(row.get(col, "")).strip()
        return val or None

    items = []
    next_id = start_id
    for _, row in df.iterrows():
        heads = cell(row, c_heads)
        major = cell(row, c_major)
        minor = cell(row, c_minor)
        # Skip subtotal / blank / repeated-header rows, same rule as the importer.
        if not heads and not major and not minor:
            continue
        items.append({
            "id": next_id,
            "source_file": filename,
            "month": month,
            "year": year,
            "sl_no": to_int(cell(row, c_sl)),
            "heads_of_crime": heads,
            "major_head": major,
            "minor_head": minor,
            "upto_end_of_month": to_int(cell(row, c_upto)),
            "previous_month": to_int(cell(row, c_prev_month)),
            "current_month": to_int(cell(row, c_curr_month)),
            # No category-mapping layer exists for FileStore-sourced rows (that lives in
            # the Datastore's MonthlyReviewCategoryMap). Kept null so the response shape
            # stays identical to reviews.py.
            "mapped_category": None,
            "mapped_subcategory": None,
            "mapping_confidence": None,
            "mapping_method": None,
        })
        next_id += 1
    return items


def _ensure_loaded() -> bool:
    """Builds the in-memory review cache on first use. Returns True if data is available.
    Thread-safe and idempotent; a failed/empty load leaves the cache as None so the next
    request can retry rather than being stuck with an empty result forever."""
    global _reviews_cache
    if _reviews_cache is not None:
        return True
    with _cache_lock:
        if _reviews_cache is not None:  # re-check after acquiring the lock
            return True
        all_items = []
        next_id = 1
        file_count = 0
        for filename, raw in _download_folder_csvs():
            parsed = _parse_review_csv(filename, raw, next_id)
            if parsed:
                all_items.extend(parsed)
                next_id += len(parsed)
                file_count += 1
        if not all_items:
            logger.error("filestore_data: no review rows loaded from FileStore; "
                         "leaving cache empty so /reviews falls back to the Datastore.")
            return False
        _reviews_cache = all_items
        logger.info(f"filestore_data: cached {len(all_items)} review rows from "
                    f"{file_count} FileStore CSV(s).")
        return True


def get_reviews(month: Optional[int] = None, year: Optional[int] = None,
                limit: int = 200, offset: int = 0) -> Optional[dict]:
    """Returns the /api/reviews/ payload from FileStore-sourced data, or None to signal
    the caller to fall back to the Datastore. Shape matches reviews.py exactly:
        {"total": int, "limit": int, "offset": int, "items": [...]}.
    """
    try:
        if not _ensure_loaded():
            return None
        rows = _reviews_cache
        if month is not None:
            rows = [r for r in rows if r["month"] == month]
        if year is not None:
            rows = [r for r in rows if r["year"] == year]
        total = len(rows)
        page = rows[offset: offset + limit]
        return {"total": total, "limit": limit, "offset": offset, "items": page}
    except Exception as e:
        logger.error(f"filestore_data.get_reviews failed ({e}); falling back to Datastore.")
        return None


if __name__ == "__main__":
    # Manual self-test for a Catalyst-connected environment (this cannot be exercised in
    # a sandbox without SDK credentials). Run from the backend dir:  python -m app.filestore_data
    payload = get_reviews(limit=3)
    if payload is None:
        print("No FileStore data available (SDK/config/download failed). See logs above.")
    else:
        print(f"total rows: {payload['total']}")
        import json
        print(json.dumps(payload["items"][:3], indent=2, default=str))
