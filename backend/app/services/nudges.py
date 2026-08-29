"""Feature 3 — case timeline nudges.

A daily scan that raises supervisor-facing prompts on cases drifting past a
threshold. Three kinds:

  staleness            no investigation activity for NUDGE_STALENESS_DAYS
  chargesheet_deadline the statutory filing window is closing and none is filed
  court_date           a court date falls inside NUDGE_DEADLINE_WINDOW_DAYS

    Two derivations the schema forces, both configurable.

    `chargesheets` records when a chargesheet WAS filed, never when one is DUE, so the
    deadline is derived as date_reported + NUDGE_CHARGESHEET_DEADLINE_DAYS (60 by
    default, mirroring CrPC 167(2)(a)(ii) / BNSS 187 for offences punishable with under
    ten years).

    There is no hearing-date column anywhere either. `convictions.conviction_date` is
    the only court-linked date, so a value in the FUTURE is treated as a scheduled
    court date. If a dedicated hearing table is added later, point _court_date_nudges()
    at it -- nothing else needs to change.

Re-running is safe: one *open* nudge per (fir_id, nudge_type), and open nudges whose
condition has since cleared are auto-resolved rather than left to pile up. A prompt that
never goes away stops being read.
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sqlalchemy.orm import Session
from app.database.models import (
    FIR, Investigation, ChargeSheet, Conviction, PoliceStation, CaseNudge,
)
from app.core.timeutil import utc_now
from app.config import settings

STALENESS = "staleness"
COURT_DATE = "court_date"
CHARGESHEET_DEADLINE = "chargesheet_deadline"
NUDGE_TYPES = (STALENESS, COURT_DATE, CHARGESHEET_DEADLINE)

PENDING, ACKNOWLEDGED, RESOLVED = "pending", "acknowledged", "resolved"
OPEN_STATUSES = (PENDING, ACKNOWLEDGED)

# A closed case needs no prompting; everything else is still live work.
CLOSED_STATUSES = {"CLOSED", "DISPOSED"}


def _supervisor_for(fir: FIR, investigations_by_fir: dict) -> str | None:
    """Best available responsible officer.

    The schema has no supervisor hierarchy -- `officers.rank` exists but nothing maps a
    case to a supervising officer -- so this is the assigned investigating officer,
    which is who a prompt should reach in practice. Swap this one function if a real
    reporting line is added.
    """
    inv = investigations_by_fir.get(fir.id)
    return inv.assigned_officer if inv else None


def _open_key(db: Session):
    """(fir_id, nudge_type) pairs that already have an open nudge."""
    rows = db.query(CaseNudge.fir_id, CaseNudge.nudge_type).filter(
        CaseNudge.status.in_(OPEN_STATUSES)
    ).all()
    return {(r[0], r[1]) for r in rows}


def run_nudge_scan(db: Session, staleness_days: int | None = None,
                   window_days: int | None = None, now: datetime | None = None,
                   auto_resolve: bool = True) -> dict:
    """Scans open cases and raises/clears nudges. Returns a summary.

    `auto_resolve=False` makes the run report-only. An exploratory scan with
    non-default thresholds MUST use it: the reconcile pass below closes any open
    nudge this run did not re-raise, and a run with different thresholds legitimately
    produces a different set -- so letting it reconcile silently closes real nudges
    the configured daily scan had raised.
    """
    staleness_days = settings.NUDGE_STALENESS_DAYS if staleness_days is None else staleness_days
    window_days = settings.NUDGE_DEADLINE_WINDOW_DAYS if window_days is None else window_days
    now = now or utc_now()
    started = now

    firs = (db.query(FIR)
              .filter(~FIR.status.in_(CLOSED_STATUSES))
              .order_by(FIR.id)
              .limit(settings.NUDGE_MAX_CASES).all())
    fir_ids = [f.id for f in firs]
    if not fir_ids:
        return {"cases_scanned": 0, "created": 0, "auto_resolved": 0, "created_by_type": {},
                "staleness_days": staleness_days, "window_days": window_days,
                "duration_seconds": 0.0}

    investigations = {}
    for inv in db.query(Investigation).filter(Investigation.fir_id.in_(fir_ids)).all():
        # Keep the most recently touched investigation per case.
        prev = investigations.get(inv.fir_id)
        if prev is None or (inv.last_updated or datetime.min) > (prev.last_updated or datetime.min):
            investigations[inv.fir_id] = inv

    chargesheet_fir_ids = {c.fir_id for c in
                           db.query(ChargeSheet.fir_id).filter(ChargeSheet.fir_id.in_(fir_ids)).all()}

    convictions = {}
    for cv in db.query(Conviction).filter(Conviction.fir_id.in_(fir_ids)).all():
        if cv.conviction_date and cv.conviction_date > now:
            prev = convictions.get(cv.fir_id)
            if prev is None or cv.conviction_date < prev.conviction_date:
                convictions[cv.fir_id] = cv       # soonest upcoming date wins

    already_open = _open_key(db)
    created_by_type = {}
    still_valid = set()

    def raise_nudge(fir, ntype, due, reason):
        still_valid.add((fir.id, ntype))
        if (fir.id, ntype) in already_open:
            return
        db.add(CaseNudge(
            fir_id=fir.id, nudge_type=ntype, due_date=due, status=PENDING,
            assigned_supervisor=_supervisor_for(fir, investigations),
            reason=reason, created_at=now,
        ))
        created_by_type[ntype] = created_by_type.get(ntype, 0) + 1

    stale_cutoff = now - timedelta(days=staleness_days)
    deadline_horizon = now + timedelta(days=window_days)

    for fir in firs:
        # --- staleness -------------------------------------------------------
        inv = investigations.get(fir.id)
        if inv is not None:
            last_touch = inv.last_updated
            source = f"investigation last updated {last_touch:%Y-%m-%d}" if last_touch else "investigation has no last_updated"
        else:
            last_touch = fir.date_reported
            source = f"no investigation record; FIR registered {last_touch:%Y-%m-%d}" if last_touch else "no investigation record"

        if last_touch is not None and last_touch < stale_cutoff:
            idle_days = (now - last_touch).days
            raise_nudge(fir, STALENESS, last_touch + timedelta(days=staleness_days),
                        f"No case activity for {idle_days} days ({source}); "
                        f"threshold is {staleness_days} days.")

        # --- chargesheet deadline -------------------------------------------
        if fir.id not in chargesheet_fir_ids and fir.date_reported:
            deadline = fir.date_reported + timedelta(days=settings.NUDGE_CHARGESHEET_DEADLINE_DAYS)
            if deadline <= deadline_horizon:
                overdue = deadline < now
                raise_nudge(fir, CHARGESHEET_DEADLINE, deadline,
                            ("Chargesheet deadline PASSED on "
                             if overdue else "Chargesheet due by ")
                            + f"{deadline:%Y-%m-%d} "
                              f"({settings.NUDGE_CHARGESHEET_DEADLINE_DAYS} days from registration) "
                              f"and none is on record.")

        # --- court date ------------------------------------------------------
        cv = convictions.get(fir.id)
        if cv is not None and cv.conviction_date <= deadline_horizon:
            days_out = (cv.conviction_date - now).days
            court = f" at {cv.court}" if cv.court else ""
            raise_nudge(fir, COURT_DATE, cv.conviction_date,
                        f"Court date in {days_out} day(s) on {cv.conviction_date:%Y-%m-%d}{court}.")

    # --- auto-resolve nudges whose condition has cleared ---------------------
    auto_resolved = 0
    if auto_resolve:
        # Restricted to the FIRs this run actually walked. `firs` is capped at
        # NUDGE_MAX_CASES, so a database with more open cases than the cap leaves the
        # remainder unscanned -- and closing their nudges for "condition no longer
        # met" would be asserting something this run never checked.
        scanned_ids = set(fir_ids)
        open_nudges = (db.query(CaseNudge)
                         .filter(CaseNudge.status.in_(OPEN_STATUSES))
                         .filter(CaseNudge.fir_id.in_(scanned_ids))
                         .all())
        for nudge in open_nudges:
            if (nudge.fir_id, nudge.nudge_type) in still_valid:
                continue
            nudge.status = RESOLVED
            nudge.updated_at = now
            nudge.resolved_by = "system:nudge-scan"
            nudge.resolution_note = "Condition no longer met at the next scan; closed automatically."
            auto_resolved += 1

    db.commit()
    return {
        "cases_scanned": len(firs),
        "created": sum(created_by_type.values()),
        "created_by_type": created_by_type,
        "auto_resolved": auto_resolved,
        "staleness_days": staleness_days,
        "window_days": window_days,
        "chargesheet_deadline_days": settings.NUDGE_CHARGESHEET_DEADLINE_DAYS,
        "duration_seconds": round((datetime.utcnow() - started).total_seconds(), 3),
    }


def serialize_nudge(n: CaseNudge, fir: FIR | None = None, station: PoliceStation | None = None) -> dict:
    out = {
        "id": n.id,
        "fir_id": n.fir_id,
        "nudge_type": n.nudge_type,
        "due_date": n.due_date,
        "status": n.status,
        "assigned_supervisor": n.assigned_supervisor,
        "reason": n.reason,
        "created_at": n.created_at,
        "updated_at": n.updated_at,
        "resolved_by": n.resolved_by,
        "resolution_note": n.resolution_note,
    }
    if n.due_date:
        out["days_until_due"] = (n.due_date - datetime.utcnow()).days
        out["overdue"] = n.due_date < datetime.utcnow()
    if fir is not None:
        out["fir_number"] = fir.fir_number
        out["fir_status"] = fir.status
        out["station"] = station.name if station else None
        out["station_id"] = station.id if station else None
        out["district_id"] = station.district_id if station else None
    return out
