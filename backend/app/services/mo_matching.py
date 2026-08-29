"""Feature 1 — cross-district modus-operandi pattern matching.

`modus_operandi` stores four *categorical* tags (entry_method, weapon_used,
time_of_day_pattern, target_type), not free text and not a vector — so similarity
here is a weighted agreement score over those fields rather than a cosine over an
embedding. Embedding the tags into a sentence just to cosine them would be a lossy
detour around data that is already structured.

Scoring
    score = Σ(weight of agreeing comparable fields) / Σ(weight of comparable fields)

A field is *comparable* only when BOTH records populate it. Two NULLs are absence of
evidence, not agreement — counting them as a match would make sparsely-tagged cases
look identical to each other. Because that shrinks the denominator, a pair must also
clear MO_MATCH_MIN_COMPARABLE_FIELDS before its score is trusted: otherwise two cases
whose only shared populated field is time_of_day="night" would score a perfect 1.0 on
a single coincidence.

Only pairs from DIFFERENT districts are considered.
"""
import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sqlalchemy.orm import Session
from app.database.models import FIR, ModusOperandi, PoliceStation, MOPatternMatch
from app.config import settings

# (model attribute, weight setting, match_type label for a lone agreement)
MO_FIELDS = (
    ("entry_method", "MO_WEIGHT_ENTRY_METHOD", "entry_method"),
    ("weapon_used", "MO_WEIGHT_WEAPON", "weapon"),
    ("target_type", "MO_WEIGHT_TARGET_TYPE", "combined"),   # not a spec match_type on its own
    ("time_of_day_pattern", "MO_WEIGHT_TIME_PATTERN", "time_pattern"),
)


def _norm(value):
    """Normalise a tag for comparison. 'unknown'/'none' are placeholders the backfill
    writes when it couldn't derive a value — treat them as missing, not as a value two
    cases can agree on."""
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in ("", "unknown", "none", "n/a", "na", "null"):
        return None
    return v


def score_pair(mo_a: ModusOperandi, mo_b: ModusOperandi):
    """Returns (score, match_type, agreeing_fields, comparable_fields).

    score is None when the pair has too few mutually-populated fields to judge.
    """
    agreeing, comparable = [], []
    agree_weight = total_weight = 0.0

    for attr, weight_key, label in MO_FIELDS:
        a, b = _norm(getattr(mo_a, attr, None)), _norm(getattr(mo_b, attr, None))
        if a is None or b is None:
            continue                      # not comparable — excluded from both sums
        weight = float(getattr(settings, weight_key))
        comparable.append(attr)
        total_weight += weight
        if a == b:
            agreeing.append(attr)
            agree_weight += weight

    if len(comparable) < settings.MO_MATCH_MIN_COMPARABLE_FIELDS or total_weight <= 0:
        return None, None, agreeing, comparable

    score = agree_weight / total_weight

    # match_type: a single agreeing field names itself (where the spec has a label for
    # it); anything broader is "combined".
    if len(agreeing) == 1:
        label = next(lbl for attr, _, lbl in MO_FIELDS if attr == agreeing[0])
        match_type = label
    else:
        match_type = "combined"

    return score, match_type, agreeing, comparable


def _district_id(fir: FIR):
    st = fir.station
    return st.district_id if st is not None else None


def run_mo_matching(db: Session, threshold: float | None = None, replace: bool = True) -> dict:
    """Scans every cross-district FIR pair that has MO tags on both sides and records
    those scoring at/above `threshold` into mo_pattern_matches.

    replace=True clears previous detections first so a re-run is idempotent rather
    than accumulating duplicate rows on every invocation.
    """
    threshold = settings.MO_MATCH_THRESHOLD if threshold is None else threshold
    started = datetime.utcnow()

    rows = (
        db.query(FIR, ModusOperandi)
        .join(ModusOperandi, ModusOperandi.fir_id == FIR.id)
        .join(PoliceStation, FIR.police_station_id == PoliceStation.id)
        .filter(PoliceStation.district_id.isnot(None))
        # Deterministic slice. Without an ORDER BY, which FIRs fall inside
        # MO_MATCH_MAX_FIRS is whatever the database happens to return, so two runs
        # over unchanged data could scan different sets and produce different
        # detections -- and, combined with the scoped delete above, silently churn
        # findings on every run.
        .order_by(FIR.id)
        .limit(settings.MO_MATCH_MAX_FIRS)
        .all()
    )

    records = [(fir, mo, _district_id(fir)) for fir, mo in rows]
    records = [r for r in records if r[2] is not None]

    if replace:
        # Scoped to the FIRs this run actually re-examines. An unqualified
        # `.delete()` cleared every MO detection in the state, so a district-limited
        # or capped run destroyed findings it was never going to regenerate.
        scanned_ids = [fir.id for fir, _, _ in records]
        if scanned_ids:
            db.query(MOPatternMatch).filter(
                MOPatternMatch.fir_id_1.in_(scanned_ids) | MOPatternMatch.fir_id_2.in_(scanned_ids)
            ).delete(synchronize_session=False)
            db.flush()

    detected = 0
    pairs_examined = 0
    skipped_same_district = 0
    by_type: dict[str, int] = {}

    for i in range(len(records)):
        fir_a, mo_a, dist_a = records[i]
        for j in range(i + 1, len(records)):
            fir_b, mo_b, dist_b = records[j]
            if dist_a == dist_b:
                skipped_same_district += 1
                continue          # same-district MO overlap is routine, not intelligence
            pairs_examined += 1

            score, match_type, _agree, _comp = score_pair(mo_a, mo_b)
            if score is None or score < threshold:
                continue

            # Canonical ordering so each pair is stored once.
            if fir_a.id <= fir_b.id:
                id1, id2, d1, d2 = fir_a.id, fir_b.id, dist_a, dist_b
            else:
                id1, id2, d1, d2 = fir_b.id, fir_a.id, dist_b, dist_a

            db.add(MOPatternMatch(
                fir_id_1=id1, fir_id_2=id2, match_type=match_type,
                similarity_score=round(float(score), 4),
                district_id_1=d1, district_id_2=d2, detected_at=datetime.utcnow(),
            ))
            detected += 1
            by_type[match_type] = by_type.get(match_type, 0) + 1

    db.commit()
    return {
        "threshold": threshold,
        "firs_with_mo": len(records),
        "cross_district_pairs_examined": pairs_examined,
        "same_district_pairs_skipped": skipped_same_district,
        "matches_detected": detected,
        "matches_by_type": by_type,
        "replaced_previous": replace,
        "duration_seconds": round((datetime.utcnow() - started).total_seconds(), 3),
    }
