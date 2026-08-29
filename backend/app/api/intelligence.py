"""Investigation Intelligence API (additive — see NEW_FEATURES.md).

Everything in this router is *advisory*: it surfaces candidates for a human to
judge and never mutates or blocks the existing FIR intake path. In particular
/check-duplicate is deliberately NOT called from /api/crimes/register — keeping
intake and duplicate-detection decoupled means a change here can never break
registration.

Reuses the existing embedding pipeline (embeddings.sentence_transformer /
embeddings.faiss_index via embeddings.similarity_search) rather than standing up
a second vector stack.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
from math import radians, sin, cos, asin, sqrt
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.session import get_db
from app.database.models import FIR, PoliceStation, District, ModusOperandi, MOPatternMatch, SectionSuggestion
from app.core.security import deny_admin_from_crime_data, require_role, scope_to_user_district
from app.services.mo_matching import run_mo_matching
from app.services import section_suggestion as section_svc
from app.services import crime_series
from app.core.security import ROLE_RANK
from app.config import settings
from app.logging import logger
from embeddings.similarity_search import search_similar_firs
from embeddings.sentence_transformer import HAS_TRANSFORMERS
from embeddings.faiss_index import HAS_FAISS

router = APIRouter(prefix="/intelligence", tags=["Investigation Intelligence"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km, or None if either point is missing."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return round(2 * r * asin(sqrt(a)), 3)


def _embedding_backend() -> str:
    """Which vector stack is actually live. Reported on every response because the
    score scale -- and therefore the meaningful threshold -- differs between them."""
    enc = "sentence-transformers" if HAS_TRANSFORMERS else "tfidf-fallback"
    idx = "faiss" if HAS_FAISS else "numpy-cosine-fallback"
    return f"{enc}+{idx}"


def _default_threshold() -> float:
    return (settings.DUPLICATE_SIMILARITY_THRESHOLD if HAS_TRANSFORMERS
            else settings.DUPLICATE_SIMILARITY_THRESHOLD_TFIDF)


def _district_of(fir: FIR):
    """(district_id, district_name) for a FIR via its station, or (None, None)."""
    station = fir.station
    if station is None or station.district is None:
        return None, None
    return station.district.id, station.district.name


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid ISO datetime: {value!r}")


# ── Feature 3: duplicate / near-duplicate FIR check at intake ────────────────

class DuplicateCheckRequest(BaseModel):
    """Draft FIR fields. Only `description` is required — location and date are
    corroborating signals, so the check still works from text alone."""
    description: str = Field(..., min_length=10, max_length=5000)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    date_occurred: str | None = Field(None, max_length=40, description="ISO 8601")
    # Floor is 0.3, not 0.0. At 0.0 the `score < threshold` filter rejects nothing,
    # so any caller could set threshold=0&top_k=100 and receive a hundred full FIR
    # records -- descriptions, stations, dates -- turning a duplicate check into a
    # bulk export primitive.
    threshold: float | None = Field(None, ge=0.3, le=1.0, description="Overrides the configured default")
    top_k: int | None = Field(None, ge=1, le=100)


@router.post("/check-duplicate")
def check_duplicate(
    payload: DuplicateCheckRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
):
    """Flags existing FIRs that look like the draft being typed.

    Advisory only: a hit is returned as `possible_duplicate`, never auto-rejected —
    two genuinely distinct incidents can read almost identically (two chain
    snatchings on the same street), so the officer decides, not the model.

    Location and date are reported as corroborating context (distance_km,
    days_apart) rather than used as filters, so a duplicate filed against the
    wrong station or with a mistyped date still surfaces.
    """
    threshold = payload.threshold if payload.threshold is not None else _default_threshold()
    top_k = payload.top_k or settings.DUPLICATE_SEARCH_TOP_K
    draft_dt = _parse_dt(payload.date_occurred)

    # Same encoder + index the semantic case search uses.
    try:
        candidates = search_similar_firs(payload.description, top_k, db)
    except Exception as exc:  # index not built / corpus empty
        # The raw exception used to be interpolated into the response, which leaked
        # internal numpy shapes and file paths to any caller. Logged, not returned.
        logger.exception("Similarity search failed for duplicate check")
        raise HTTPException(
            status_code=503,
            detail="The similarity index is not available yet. Try again shortly; if this "
                   "persists, rebuild the index.",
        )

    matches = []
    for c in candidates:
        score = float(c["score"])
        if score < threshold:
            continue
        fir: FIR = c["fir"]
        district_id, district_name = _district_of(fir)

        distance_km = _haversine_km(payload.latitude, payload.longitude, fir.latitude, fir.longitude)
        days_apart = None
        if draft_dt and fir.date_occurred:
            days_apart = abs((draft_dt - fir.date_occurred).days)

        reasons = [f"text similarity {score:.2f} >= {threshold:.2f}"]
        if distance_km is not None and distance_km <= settings.DUPLICATE_NEARBY_KM:
            reasons.append(f"within {distance_km} km")
        if days_apart is not None and days_apart <= settings.DUPLICATE_NEARBY_DAYS:
            reasons.append(f"{days_apart} day(s) apart")

        matches.append({
            "fir_id": fir.id,
            "fir_number": fir.fir_number,
            "similarity_score": round(score, 4),
            "station": fir.station.name if fir.station else None,
            "district_id": district_id,
            "district": district_name,
            "date_reported": fir.date_reported,
            "date_occurred": fir.date_occurred,
            "status": fir.status,
            "description": fir.description,
            "distance_km": distance_km,
            "days_apart": days_apart,
            "flag": "possible_duplicate",
            "reasons": reasons,
        })

    matches.sort(key=lambda m: m["similarity_score"], reverse=True)
    return {
        "possible_duplicate": len(matches) > 0,
        "threshold": threshold,
        "embedding_backend": _embedding_backend(),
        "candidates_examined": len(candidates),
        "match_count": len(matches),
        "advisory": "Possible duplicates are surfaced for human review only. "
                    "Registration is not blocked and no record has been modified.",
        "matches": matches,
    }


# ── Feature 1: cross-district modus-operandi pattern matching ────────────────

def _mo_dict(mo: ModusOperandi | None):
    if mo is None:
        return None
    return {
        "entry_method": mo.entry_method,
        "weapon_used": mo.weapon_used,
        "time_of_day_pattern": mo.time_of_day_pattern,
        "target_type": mo.target_type,
    }


def _fir_brief(fir: FIR | None, district_name: str | None):
    if fir is None:
        return None
    return {
        "fir_id": fir.id,
        "fir_number": fir.fir_number,
        "station": fir.station.name if fir.station else None,
        "district": district_name,
        "date_occurred": fir.date_occurred,
        "date_reported": fir.date_reported,
        "status": fir.status,
        "description": fir.description,
        "modus_operandi": _mo_dict(fir.modus_operandi),
    }


def _serialize_match(m: MOPatternMatch, firs: dict, districts: dict):
    d1 = districts.get(m.district_id_1)
    d2 = districts.get(m.district_id_2)
    return {
        "id": m.id,
        "match_type": m.match_type,
        "similarity_score": m.similarity_score,
        "detected_at": m.detected_at,
        "district_1": {"id": m.district_id_1, "name": d1},
        "district_2": {"id": m.district_id_2, "name": d2},
        "case_1": _fir_brief(firs.get(m.fir_id_1), d1),
        "case_2": _fir_brief(firs.get(m.fir_id_2), d2),
    }


def _hydrate(db: Session, matches: list):
    """Bulk-loads the FIRs and districts referenced by `matches` (avoids N+1)."""
    fir_ids = {m.fir_id_1 for m in matches} | {m.fir_id_2 for m in matches}
    dist_ids = {m.district_id_1 for m in matches} | {m.district_id_2 for m in matches}
    fir_ids.discard(None); dist_ids.discard(None)
    firs = {f.id: f for f in db.query(FIR).filter(FIR.id.in_(fir_ids)).all()} if fir_ids else {}
    districts = {d.id: d.name for d in db.query(District).filter(District.id.in_(dist_ids)).all()} if dist_ids else {}
    return firs, districts


@router.post("/mo-matches/run")
def run_mo_match_job(
    threshold: float | None = Query(None, ge=0.0, le=1.0, description="Overrides MO_MATCH_THRESHOLD"),
    replace: bool = Query(True, description="Clear previous detections first (idempotent re-run)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("investigator")),
):
    """Runs the cross-district MO matching job on demand.

    Writes detections, so it needs Investigator clearance or above -- an Analyst can
    read the results but not regenerate them. Admin is deliberately excluded
    (require_role sits on the operational ladder, which Admin is not on).
    """
    return run_mo_matching(db, threshold=threshold, replace=replace)


@router.get("/mo-matches")
def list_mo_matches(
    district_id: int | None = Query(None, gt=0, description="Matches touching this district (either side)"),
    match_type: str | None = Query(None, max_length=30, description="entry_method | weapon | time_pattern | combined"),
    from_date: str | None = Query(None, max_length=40, description="detected_at >= this ISO datetime"),
    to_date: str | None = Query(None, max_length=40, description="detected_at <= this ISO datetime"),
    min_score: float | None = Query(None, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int | None = Depends(scope_to_user_district),
):
    """Lists detected cross-district MO matches.

    An Analyst/Investigator with a district assigned only sees matches involving that
    district, mirroring how /api/crimes/ scopes case listings.
    """
    q = db.query(MOPatternMatch)

    # A user's own district scope wins over the query param -- same precedence as list_firs.
    effective_district = scoped_district_id if scoped_district_id is not None else district_id
    if effective_district is not None:
        q = q.filter((MOPatternMatch.district_id_1 == effective_district) |
                     (MOPatternMatch.district_id_2 == effective_district))
    if match_type:
        q = q.filter(MOPatternMatch.match_type == match_type)
    if min_score is not None:
        q = q.filter(MOPatternMatch.similarity_score >= min_score)
    dt_from, dt_to = _parse_dt(from_date), _parse_dt(to_date)
    if dt_from:
        q = q.filter(MOPatternMatch.detected_at >= dt_from)
    if dt_to:
        q = q.filter(MOPatternMatch.detected_at <= dt_to)

    total = q.count()
    matches = (q.order_by(MOPatternMatch.similarity_score.desc(), MOPatternMatch.id.desc())
                 .offset(offset).limit(limit).all())
    firs, districts = _hydrate(db, matches)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "district_id": effective_district,
            "district_scope_enforced": scoped_district_id is not None,
            "match_type": match_type,
            "from_date": from_date,
            "to_date": to_date,
            "min_score": min_score,
        },
        "matches": [_serialize_match(m, firs, districts) for m in matches],
    }


@router.get("/mo-matches/{fir_id}")
def mo_matches_for_case(
    fir_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int | None = Depends(scope_to_user_district),
):
    """Cross-district MO matches involving one specific case (for a case detail view)."""
    fir = db.query(FIR).filter(FIR.id == fir_id).first()
    if not fir:
        raise HTTPException(status_code=404, detail="FIR not found")

    # Same district scoping the sibling list route applies. Without it, an
    # Analyst/Investigator restricted to one district could read any case's matches --
    # including the full description of the OTHER case in each pair -- simply by
    # walking fir_id, which is exactly what list_mo_matches exists to prevent.
    if scoped_district_id is not None:
        fir_district, _ = _district_of(fir)
        if fir_district is not None and fir_district != scoped_district_id:
            raise HTTPException(
                status_code=403,
                detail="This case is outside your assigned district.",
            )

    matches = (db.query(MOPatternMatch)
                 .filter((MOPatternMatch.fir_id_1 == fir_id) | (MOPatternMatch.fir_id_2 == fir_id))
                 .order_by(MOPatternMatch.similarity_score.desc()).all())
    firs, districts = _hydrate(db, matches)

    district_id, district_name = _district_of(fir)
    return {
        "fir_id": fir.id,
        "fir_number": fir.fir_number,
        "district": district_name,
        "modus_operandi": _mo_dict(fir.modus_operandi),
        "match_count": len(matches),
        "matches": [_serialize_match(m, firs, districts) for m in matches],
    }


# ── Feature 2: IPC/BNS section suggestion ───────────────────────────────────

class SuggestSectionsRequest(BaseModel):
    """Free-text complaint. `fir_id` is optional — supply it only to attach the
    suggestions to an existing case (which is what triggers a write)."""
    description: str = Field(..., min_length=10, max_length=5000)
    top_k: int | None = Field(None, ge=1, le=10)
    min_confidence: float | None = Field(None, ge=0.0, le=1.0)
    fir_id: int | None = Field(None, gt=0, description="Attach + persist the suggestions to this case")
    persist: bool = Field(True, description="Only has effect when fir_id is supplied")


@router.post("/suggest-sections")
def suggest_sections(
    payload: SuggestSectionsRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
):
    """Ranked IPC/BNS section candidates for a complaint description.

    Retrieval, not classification: the complaint is matched by cosine similarity
    against a curated reference corpus of section descriptions
    (backend/data/ipc_bns_sections.json). There is no labelled complaint→section
    training data in this repo, so a trained classifier would be a black box with no
    ground truth behind it.

    Callable standalone while a complaint is being drafted. It is deliberately NOT
    invoked by /api/crimes/register — registration behaviour is unchanged, and the
    frontend may call this alongside it if it chooses.

    Writing suggestions against a case (`fir_id`) needs Investigator clearance;
    reading suggestions does not.
    """
    results = section_svc.suggest_sections(
        payload.description, top_k=payload.top_k, min_confidence=payload.min_confidence
    )

    persisted = 0
    if payload.fir_id is not None and payload.persist:
        rank = ROLE_RANK.get(str(current_user.get("role", "")).lower())
        if rank is None or rank < ROLE_RANK["investigator"]:
            raise HTTPException(
                status_code=403,
                detail="Attaching section suggestions to a case requires Investigator clearance or higher. "
                       "Omit fir_id (or set persist=false) to get advisory suggestions without storing them.",
            )
        if not db.query(FIR).filter(FIR.id == payload.fir_id).first():
            raise HTTPException(status_code=404, detail="FIR not found")

        # Replace this case's previous suggestions rather than appending to them.
        # Every call used to add a fresh row per result with no dedup, no uniqueness
        # constraint on (fir_id, suggested_section) and no delete endpoint -- so an
        # officer re-running the suggestion while drafting silently accumulated
        # duplicate charges against the case, with no way to remove them.
        db.query(SectionSuggestion).filter(SectionSuggestion.fir_id == payload.fir_id).delete(
            synchronize_session=False)

        for r in results:
            db.add(SectionSuggestion(
                fir_id=payload.fir_id,
                suggested_section=r["suggested_section"],
                confidence=r["confidence"],
                reference_description=r["reference_description"],
            ))
            persisted += 1
        db.commit()

    _sections, _idx, _enc, meta = section_svc.get_index()
    return {
        "method": "retrieval",
        "embedding_backend": section_svc.embedding_backend(),
        "reference_version": meta.get("version"),
        "reference_entries": len(_sections),
        "fir_id": payload.fir_id,
        "persisted": persisted,
        "advisory": meta.get("disclaimer"),
        "suggestions": results,
    }


@router.get("/section-suggestions/{fir_id}")
def stored_section_suggestions(
    fir_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
):
    """Section suggestions previously stored against a case, newest first."""
    fir = db.query(FIR).filter(FIR.id == fir_id).first()
    if not fir:
        raise HTTPException(status_code=404, detail="FIR not found")

    rows = (db.query(SectionSuggestion)
              .filter(SectionSuggestion.fir_id == fir_id)
              .order_by(SectionSuggestion.created_at.desc(), SectionSuggestion.confidence.desc())
              .all())
    return {
        "fir_id": fir.id,
        "fir_number": fir.fir_number,
        "count": len(rows),
        "suggestions": [{
            "id": r.id,
            "suggested_section": r.suggested_section,
            "confidence": r.confidence,
            "reference_description": r.reference_description,
            "created_at": r.created_at,
        } for r in rows],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Serial crime series — assembling pairwise MO matches into runs, and forecasting
# where and when a run may continue. See app/services/crime_series.py.
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/series")
def list_crime_series(
    min_edge_score: float = Query(crime_series.MIN_EDGE_SCORE, ge=0.5, le=1.0,
                                  description="Minimum MO similarity for two cases to be linked"),
    min_series_size: int = Query(crime_series.MIN_SERIES_SIZE, ge=3, le=50,
                                 description="Smallest run reported; below 3 is a pair, not a series"),
    forecast_only: bool = Query(False, description="Return only series that produced a forecast"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int | None = Depends(scope_to_user_district),
):
    """Detected serial runs, most urgent first.

    A "series" is a connected component of the cross-district MO match graph with at
    least `min_series_size` cases. Each is profiled for cadence, spatial drift and
    confidence, and — only where the evidence supports it — carries a forecast window
    and search area.

    District scoping matches the rest of this router: an Analyst/Investigator with an
    assigned district sees only series that touch it. The series is still reported
    whole, because a run that crosses a boundary is precisely the thing a
    district-scoped officer would otherwise never see; scoping decides whether they see
    the series at all, not whether they see all of it.
    """
    analysis = crime_series.analyse_series(
        db, min_score=min_edge_score, min_size=min_series_size)

    series = analysis["series"]
    if scoped_district_id is not None:
        series = [s for s in series
                  if any(m["district_id"] == scoped_district_id for m in s["members"])]
    if forecast_only:
        series = [s for s in series if s.get("forecast")]

    return {
        **analysis,
        "series": series,
        "series_count": len(series),
        "district_scope_enforced": scoped_district_id is not None,
    }


@router.get("/series/{fir_id}")
def series_for_fir(
    fir_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int | None = Depends(scope_to_user_district),
):
    """The serial run containing one case, for a case-detail panel."""
    fir = db.query(FIR).filter(FIR.id == fir_id).first()
    if not fir:
        raise HTTPException(status_code=404, detail="FIR not found")

    if scoped_district_id is not None:
        fir_district, _ = _district_of(fir)
        if fir_district is not None and fir_district != scoped_district_id:
            raise HTTPException(status_code=403,
                                detail="This case is outside your assigned district.")

    found = crime_series.series_for_case(db, fir_id)
    if not found:
        return {
            "fir_id": fir_id,
            "in_series": False,
            "detail": "This case is not part of a detected serial run.",
        }
    return {"fir_id": fir_id, "in_series": True, "series": found}
