"""Case Readiness — one verdict per FIR, assembled from every other intelligence signal.

Why this exists
---------------
The platform already answers five separate questions about a case: is it a duplicate,
does its MO match another district, which sections apply, is the evidence intact, is it
going stale. Each lives behind its own endpoint and its own screen. An investigating
officer preparing a chargesheet therefore has to visit five places and hold the answers
in their head, and a supervisor reviewing forty cases cannot do that at all.

This module asks the question those five are really components of: **can this case go to
court, and if not, what is missing?**

Scoring
-------
Weighted checks over the evidentiary requirements of a chargesheet: an identified
accused, evidence whose custody is intact, applicable sections, and a live investigation.
Weights sum to 1.0 and are declared in CHECK_WEIGHTS so an operator can see and re-tune
what the score rewards.

The statutory clock (CrPC 167(2) / BNSS 187, mirrored in NUDGE_CHARGESHEET_DEADLINE_DAYS)
deliberately sits OUTSIDE the score. Time remaining is not evidentiary quality: a case can
be fully prepared with two days left, or empty with fifty. Mixing them would produce a
number that hides both. It gates the *band* instead, so an expired clock is surfaced as a
blocker regardless of how complete the file is.

What this is not
----------------
Not a decision. It never recommends filing or closing, and it does not score people. It
reports which documentary preconditions are met, with the underlying record for each, so
the officer can see why -- an unexplained number would be worse than no number.
"""
from __future__ import annotations

import sys
import os
from datetime import timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sqlalchemy.orm import Session

from app.config import settings
from app.core.timeutil import utc_now
from app.database.models import (
    FIR, Arrest, ChargeSheet, EvidenceItem, EvidenceAccessLog, Investigation,
    MOPatternMatch, SectionSuggestion, CaseNudge,
)

PASS, WARN, FAIL = "pass", "warn", "fail"

# Relative importance of each precondition. Sums to 1.0.
CHECK_WEIGHTS = {
    "accused_identified": 0.18,
    "arrest_recorded": 0.12,
    "evidence_present": 0.15,
    "evidence_integrity": 0.15,
    "custody_traceable": 0.10,
    "sections_attached": 0.12,
    "investigation_active": 0.10,
    "linkage_reviewed": 0.08,
}

# A WARN earns partial credit -- the precondition is addressed but incomplete, which is
# genuinely different from absent and should not score the same as either.
WARN_CREDIT = 0.5

BANDS = [
    (85, "ready", "Every documentary precondition is met."),
    (65, "nearly_ready", "Substantially prepared; a small number of gaps remain."),
    (40, "gaps", "Significant gaps -- not filing-ready."),
    (0, "blocked", "Core preconditions are unmet."),
]

# Cases untouched for this long are treated as dormant by the activity check. Shares the
# nudge threshold so the two features cannot disagree about what "stale" means.
STALE_DAYS = settings.NUDGE_STALENESS_DAYS


def _check(key: str, label: str, status: str, detail: str, action: str | None = None,
           evidence: dict | None = None) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status,
        "weight": CHECK_WEIGHTS[key],
        "detail": detail,
        "action": action,
        "evidence": evidence or {},
    }


def _accused_check(fir: FIR) -> dict:
    accused = list(fir.accused_list or [])
    if accused:
        names = [a.name for a in accused if getattr(a, "name", None)]
        return _check("accused_identified", "Accused identified", PASS,
                      f"{len(accused)} accused linked to this case.",
                      evidence={"count": len(accused), "names": names[:5]})
    return _check("accused_identified", "Accused identified", FAIL,
                  "No accused person is linked to this FIR.",
                  action="Link the identified accused, or record the case as undetected.")


def _arrest_check(db: Session, fir: FIR) -> dict:
    arrests = db.query(Arrest).filter(Arrest.fir_id == fir.id).all()
    accused_count = len(fir.accused_list or [])
    if arrests:
        return _check("arrest_recorded", "Arrest recorded", PASS,
                      f"{len(arrests)} arrest(s) on record.",
                      evidence={"count": len(arrests)})
    if accused_count:
        # Identified but not arrested is a real, legitimate state (absconding, bailed
        # before arrest). It is a gap in the file, not a failure of investigation.
        return _check("arrest_recorded", "Arrest recorded", WARN,
                      "Accused identified but no arrest is recorded.",
                      action="Record the arrest, or note why no arrest was effected.")
    return _check("arrest_recorded", "Arrest recorded", FAIL,
                  "No arrest recorded and no accused identified.",
                  action="Identify the accused before an arrest can be recorded.")


def _evidence_checks(db: Session, fir: FIR) -> tuple[dict, dict, dict]:
    items = db.query(EvidenceItem).filter(EvidenceItem.fir_id == fir.id).all()

    if not items:
        present = _check("evidence_present", "Evidence attached", FAIL,
                         "No evidence items are attached to this case.",
                         action="Attach the seized material and its custody record.")
        integrity = _check("evidence_integrity", "Evidence integrity", FAIL,
                           "No evidence to verify.",
                           action="Attach evidence first.")
        custody = _check("custody_traceable", "Custody traceable", FAIL,
                         "No custody trail exists.",
                         action="Attach evidence first.")
        return present, integrity, custody

    present = _check("evidence_present", "Evidence attached", PASS,
                     f"{len(items)} evidence item(s) attached.",
                     evidence={"count": len(items),
                               "types": sorted({i.item_type for i in items})})

    flagged = [i for i in items if i.integrity_flagged]
    if flagged:
        integrity = _check(
            "evidence_integrity", "Evidence integrity", FAIL,
            f"{len(flagged)} item(s) flagged: a reported hash did not match the baseline.",
            action="Resolve the integrity flag before relying on these items in court.",
            evidence={"flagged_item_ids": [i.id for i in flagged]})
    else:
        unhashed = [i for i in items if not i.content_hash]
        if unhashed:
            # No baseline means nothing can ever be verified against it later. That is a
            # weaker position than a verified item, but not the same as a mismatch.
            integrity = _check(
                "evidence_integrity", "Evidence integrity", WARN,
                f"{len(unhashed)} item(s) have no hash baseline recorded.",
                action="Record a SHA-256 baseline for each item so tampering stays detectable.",
                evidence={"unhashed_item_ids": [i.id for i in unhashed]})
        else:
            integrity = _check("evidence_integrity", "Evidence integrity", PASS,
                               "All items carry a baseline hash and none is flagged.")

    # Custody is traceable when every item's trail records who held it across each
    # handover. Transfers written before the custodian columns existed cannot answer
    # "who held this on date X", which is the question the trail exists for.
    item_ids = [i.id for i in items]
    transfers = (db.query(EvidenceAccessLog)
                   .filter(EvidenceAccessLog.evidence_id.in_(item_ids))
                   .filter(EvidenceAccessLog.action == "transferred")
                   .all())
    untraceable = [t.id for t in transfers if not t.custodian_after]
    if untraceable:
        custody = _check(
            "custody_traceable", "Custody traceable", FAIL,
            f"{len(untraceable)} custody transfer(s) do not record who received the item.",
            action="These predate structured custody logging and must be reconstructed manually.",
            evidence={"incomplete_log_ids": untraceable})
    else:
        custody = _check("custody_traceable", "Custody traceable", PASS,
                         f"{len(transfers)} handover(s) fully recorded."
                         if transfers else "Item has not changed hands; original custody intact.")
    return present, integrity, custody


def _sections_check(db: Session, fir: FIR) -> dict:
    filed = db.query(ChargeSheet).filter(ChargeSheet.fir_id == fir.id).first()
    if filed and filed.sections:
        return _check("sections_attached", "Sections determined", PASS,
                      f"Chargesheet filed under {filed.sections}.",
                      evidence={"sections": filed.sections, "filed_date": filed.filed_date})

    suggestions = (db.query(SectionSuggestion)
                     .filter(SectionSuggestion.fir_id == fir.id)
                     .order_by(SectionSuggestion.confidence.desc()).all())
    if suggestions:
        # Suggestions are advisory retrieval output, never a determination. A case whose
        # only legal basis is an unreviewed machine suggestion is not filing-ready.
        return _check(
            "sections_attached", "Sections determined", WARN,
            f"{len(suggestions)} suggested section(s) awaiting an officer's confirmation.",
            action="Confirm or replace the suggested sections.",
            evidence={"suggested": [s.suggested_section for s in suggestions[:5]]})

    return _check("sections_attached", "Sections determined", FAIL,
                  "No sections determined or suggested for this case.",
                  action="Run section suggestion, or enter the sections directly.")


def _investigation_check(db: Session, fir: FIR, now) -> dict:
    inv = (db.query(Investigation)
             .filter(Investigation.fir_id == fir.id)
             .order_by(Investigation.last_updated.desc()).first())
    if not inv:
        return _check("investigation_active", "Investigation active", FAIL,
                      "No investigation record exists for this case.",
                      action="Assign an investigating officer.")
    if not inv.assigned_officer:
        return _check("investigation_active", "Investigation active", FAIL,
                      "Investigation exists but no officer is assigned.",
                      action="Assign an investigating officer.")

    last = inv.last_updated
    idle_days = (now - last).days if last else None
    if idle_days is not None and idle_days > STALE_DAYS:
        return _check("investigation_active", "Investigation active", WARN,
                      f"No recorded activity for {idle_days} days "
                      f"(threshold {STALE_DAYS}).",
                      action="Record the current investigation status.",
                      evidence={"assigned_officer": inv.assigned_officer,
                                "idle_days": idle_days, "status": inv.status})
    return _check("investigation_active", "Investigation active", PASS,
                  f"Assigned to {inv.assigned_officer}; status {inv.status}.",
                  evidence={"assigned_officer": inv.assigned_officer,
                            "idle_days": idle_days, "status": inv.status})


def _linkage_check(db: Session, fir: FIR) -> dict:
    """Whether this case's cross-district MO links have been looked at.

    A pending link is not a defect in the case file -- it is intelligence the officer may
    not have seen. Surfacing it here is the point: it is the one check that can ADD to an
    investigation rather than just audit it.
    """
    matches = (db.query(MOPatternMatch)
                 .filter((MOPatternMatch.fir_id_1 == fir.id) | (MOPatternMatch.fir_id_2 == fir.id))
                 .order_by(MOPatternMatch.similarity_score.desc()).all())
    if not matches:
        return _check("linkage_reviewed", "Cross-district linkage", PASS,
                      "No cross-district MO matches flagged for this case.")

    top = matches[0]
    linked_ids = sorted({m.fir_id_1 for m in matches} | {m.fir_id_2 for m in matches} - {fir.id})
    return _check(
        "linkage_reviewed", "Cross-district linkage", WARN,
        f"{len(matches)} MO match(es) in other districts, strongest {top.similarity_score:.2f}.",
        action="Review the linked cases -- they may carry evidence or an accused this file lacks.",
        evidence={"match_count": len(matches),
                  "top_score": round(float(top.similarity_score), 3),
                  "linked_fir_ids": [i for i in linked_ids if i != fir.id][:8]})


def _statutory_clock(fir: FIR, db: Session, now) -> dict:
    """Days remaining to the derived chargesheet deadline.

    The schema records when a chargesheet WAS filed, never when it is due, so the
    deadline is derived as date_reported + NUDGE_CHARGESHEET_DEADLINE_DAYS -- the same
    derivation the nudge scan uses, so the two cannot disagree.
    """
    filed = db.query(ChargeSheet).filter(ChargeSheet.fir_id == fir.id).first()
    reported = fir.date_reported
    if not reported:
        return {"applicable": False, "reason": "No date_reported on this FIR."}

    deadline = reported + timedelta(days=settings.NUDGE_CHARGESHEET_DEADLINE_DAYS)
    days_remaining = (deadline - now).days

    if filed:
        return {
            "applicable": True, "satisfied": True,
            "deadline": deadline, "days_remaining": days_remaining,
            "status": "filed",
            "note": f"Chargesheet filed on {filed.filed_date:%Y-%m-%d}.",
        }

    status = "expired" if days_remaining < 0 else (
        "critical" if days_remaining <= 7 else
        "approaching" if days_remaining <= 21 else "comfortable")
    return {
        "applicable": True, "satisfied": False,
        "deadline": deadline, "days_remaining": days_remaining, "status": status,
        "basis": f"date_reported + {settings.NUDGE_CHARGESHEET_DEADLINE_DAYS} days "
                 f"(CrPC 167(2)(a)(ii) / BNSS 187 for offences under ten years)",
    }


def assess_case(db: Session, fir: FIR, now=None) -> dict:
    """Full readiness assessment for one FIR."""
    now = now or utc_now()

    ev_present, ev_integrity, ev_custody = _evidence_checks(db, fir)
    checks = [
        _accused_check(fir),
        _arrest_check(db, fir),
        ev_present,
        ev_integrity,
        ev_custody,
        _sections_check(db, fir),
        _investigation_check(db, fir, now),
        _linkage_check(db, fir),
    ]

    earned = sum(
        c["weight"] * (1.0 if c["status"] == PASS else WARN_CREDIT if c["status"] == WARN else 0.0)
        for c in checks
    )
    score = round(earned * 100, 1)

    statutory = _statutory_clock(fir, db, now)

    band, band_note = "blocked", ""
    for floor, name, note in BANDS:
        if score >= floor:
            band, band_note = name, note
            break

    # An expired statutory window overrides the band regardless of file quality: a
    # complete file filed out of time is not "ready", it is a different problem.
    if statutory.get("applicable") and not statutory.get("satisfied") \
            and statutory.get("status") == "expired":
        band = "blocked"
        band_note = ("The statutory chargesheet window has passed. "
                     "Escalate rather than treating this as a normal filing.")

    # Ordered worklist: hard failures first, then partials, heaviest weight first within
    # each. This ordering IS the recommendation -- it is what to do next, in order.
    blockers = [
        {"label": c["label"], "detail": c["detail"], "action": c["action"],
         "severity": "blocker" if c["status"] == FAIL else "gap"}
        for c in sorted(checks,
                        key=lambda c: (c["status"] != FAIL, -c["weight"]))
        if c["status"] in (FAIL, WARN) and c["action"]
    ]

    open_nudges = (db.query(CaseNudge)
                     .filter(CaseNudge.fir_id == fir.id)
                     .filter(CaseNudge.status.in_(("pending", "acknowledged")))
                     .count())

    return {
        "fir_id": fir.id,
        "fir_number": fir.fir_number,
        "status": fir.status,
        "assessed_at": now,
        "readiness_score": score,
        "band": band,
        "band_note": band_note,
        "checks": checks,
        "statutory_clock": statutory,
        "next_actions": blockers,
        "open_nudges": open_nudges,
        "scoring": {
            "weights": CHECK_WEIGHTS,
            "warn_credit": WARN_CREDIT,
            "note": "Weights sum to 1.0. A partially-met check earns half credit. The "
                    "statutory clock is reported separately and is not part of the score.",
        },
        "advisory": (
            "Documentary completeness only. This is not a recommendation to file, close "
            "or charge, and it does not assess the strength of the evidence -- only "
            "whether the record contains what a chargesheet requires."
        ),
    }
