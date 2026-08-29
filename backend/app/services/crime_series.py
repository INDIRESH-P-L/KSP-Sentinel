"""Serial crime series detection and next-occurrence forecasting.

What this does
--------------
Cross-district MO matching (services/mo_matching.py) tells an investigator that case A
resembles case B. That is a pairwise fact, and pairwise facts are where the existing
feature stops. But a serial offender does not commit two offences -- they commit a run of
them, and the run has properties no single pair can show: a cadence, a direction of
travel, and therefore a *next* one.

This module assembles those pairs into series and characterises each run:

  1. Union-find over the MO match graph gives connected components. A component of
     three or more linked cases is a candidate series (two is just a pair, and calling a
     pair a "series" would flood the view with noise).
  2. Temporal structure -- sorted offence dates, inter-arrival gaps, the median gap as
     the cadence, and the median absolute deviation as its irregularity.
  3. Spatial structure -- centroid, dispersion, and a least-squares fit of position
     against time, which detects a series that is *travelling* rather than circling one
     neighbourhood.
  4. A forecast: when the next offence in this series would fall if the observed cadence
     holds, and where, if the observed drift holds.

Why median and MAD rather than mean and standard deviation
----------------------------------------------------------
Both are robust to a single outlier. Real series have gaps -- the offender is in custody
for an unrelated matter, or travels, or one offence in the run was never reported. A mean
gap is dragged badly by one such interval; a median is not. The same reasoning applies to
the dispersion radius, which uses a percentile rather than a maximum so one outlying
offence does not inflate the search area beyond usefulness.

Honesty constraints, deliberately built in
------------------------------------------
A forecast that cannot be trusted is worse than none, so:

  * Confidence is computed from sample size, cadence regularity and spatial tightness,
    and a series below MIN_FORECAST_CONFIDENCE returns its analysis WITHOUT a prediction
    rather than a low-confidence guess dressed up as intelligence.
  * The predicted window is an interval derived from the observed irregularity, never a
    single date. A point estimate would imply precision the data does not contain.
  * Spatial drift is only applied when the linear fit actually explains the movement
    (R-squared above DRIFT_MIN_R2). Otherwise the series is treated as stationary and the
    forecast centres on the centroid -- extrapolating a trend from noise is how a
    forecast ends up pointing confidently at the wrong place.
  * Output describes CASES, never people. There are no names, no accused ids and no
    person links anywhere in this module. It answers "where might this pattern of
    offences recur" for patrol allocation -- not "who will offend", which this data
    cannot support and which is not a question a records system should be asked.
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sqlalchemy.orm import Session

from app.core.timeutil import utc_now
from app.database.models import District, FIR, ModusOperandi, MOPatternMatch, PoliceStation

EARTH_RADIUS_KM = 6371.0

# A component smaller than this is a pair or a singleton, not a run.
MIN_SERIES_SIZE = 3
# Only matches at least this strong contribute an edge. Weaker links chain unrelated
# cases into one enormous meaningless component (the classic transitive-closure failure).
MIN_EDGE_SCORE = 0.75
# Below this, the analysis is returned but no forecast is issued.
MIN_FORECAST_CONFIDENCE = 0.35
# Drift is only extrapolated when the linear fit explains this much of the movement.
DRIFT_MIN_R2 = 0.5
# The forecast window is never tighter than this, however regular the series looks --
# implying same-day precision from a handful of offences would be false confidence.
MIN_WINDOW_DAYS = 2
# Nor is the search radius ever smaller than this: a sub-kilometre ring reads as an
# address, which is not what this evidence supports.
MIN_RADIUS_KM = 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Geometry and statistics helpers
# ─────────────────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _mad(values: list[float], centre: float) -> float:
    """Median absolute deviation -- the robust analogue of standard deviation."""
    if not values:
        return 0.0
    return _median([abs(v - centre) for v in values])


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    idx = p * (len(s) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def _linfit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Least-squares fit of y = intercept + slope*x. Returns (intercept, slope, r2)."""
    n = len(xs)
    if n < 3:
        return (ys[0] if ys else 0.0), 0.0, 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return my, 0.0, 0.0
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((y - my) ** 2 for y in ys)
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0 else 0.0
    return intercept, slope, max(0.0, min(1.0, r2))


class _UnionFind:
    def __init__(self):
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path compression
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


# ─────────────────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────────────────

def _effective_date(fir: FIR):
    """When the offence happened. Falls back to the report date, which is the only thing
    available for a case where date_occurred was never captured."""
    return fir.date_occurred or fir.date_reported


def _components(db: Session, min_score: float) -> dict[int, list[int]]:
    """Connected components of the MO match graph, keyed by representative FIR id."""
    edges = (db.query(MOPatternMatch)
               .filter(MOPatternMatch.similarity_score >= min_score)
               .all())
    uf = _UnionFind()
    for e in edges:
        if e.fir_id_1 and e.fir_id_2:
            uf.union(e.fir_id_1, e.fir_id_2)

    groups: dict[int, list[int]] = {}
    for node in list(uf.parent):
        groups.setdefault(uf.find(node), []).append(node)
    return groups


def _temporal_profile(dates: list) -> dict:
    """Cadence and regularity from the sorted offence dates."""
    gaps = [(dates[i + 1] - dates[i]).total_seconds() / 86400.0
            for i in range(len(dates) - 1)]
    gaps = [g for g in gaps if g >= 0]
    if not gaps:
        return {"cadence_days": None, "irregularity_days": None, "regularity": 0.0,
                "gaps_days": [], "tempo": "unknown"}

    cadence = _median(gaps)
    mad = _mad(gaps, cadence)
    # 0 = erratic, 1 = metronomic. MAD equal to the cadence itself is thoroughly
    # irregular, so that is the point the score reaches zero.
    regularity = max(0.0, 1.0 - (mad / cadence)) if cadence > 0 else 0.0

    tempo = "steady"
    if len(gaps) >= 4:
        # Compare the recent half against the earlier half: a run that is speeding up is
        # operationally the most urgent thing this analysis can report.
        half = len(gaps) // 2
        early, late = _median(gaps[:half]), _median(gaps[half:])
        if early > 0:
            change = (late - early) / early
            tempo = "accelerating" if change < -0.25 else "slowing" if change > 0.25 else "steady"

    return {
        "cadence_days": round(cadence, 2),
        "irregularity_days": round(mad, 2),
        "regularity": round(regularity, 3),
        "gaps_days": [round(g, 2) for g in gaps],
        "tempo": tempo,
    }


def _spatial_profile(points: list[tuple[float, float]], dates: list) -> dict:
    """Centroid, dispersion and drift for the series."""
    if not points:
        return {"centroid": None, "radius_km": None, "drift": None}

    clat = sum(p[0] for p in points) / len(points)
    clng = sum(p[1] for p in points) / len(points)
    dists = [haversine_km(clat, clng, la, ln) for la, ln in points]
    # p75, not max: one outlying offence should not inflate the search area.
    radius = max(MIN_RADIUS_KM, _percentile(dists, 0.75))

    drift = None
    residual_radius = None
    if len(points) >= 3 and dates:
        t0 = dates[0]
        days = [(d - t0).total_seconds() / 86400.0 for d in dates]
        lat_int, lat_slope, lat_r2 = _linfit(days, [p[0] for p in points])
        lng_int, lng_slope, lng_r2 = _linfit(days, [p[1] for p in points])
        # Degrees per day -> km per day at this latitude.
        km_per_deg_lat = 111.32
        km_per_deg_lng = 111.32 * cos(radians(clat))
        speed = sqrt((lat_slope * km_per_deg_lat) ** 2 + (lng_slope * km_per_deg_lng) ** 2)
        combined_r2 = max(lat_r2, lng_r2)
        significant = bool(combined_r2 >= DRIFT_MIN_R2 and speed > 0.05)

        # Scatter about the fitted TRACK rather than about the centroid.
        #
        # This distinction decides whether a travelling series can be forecast at all.
        # A run moving 200 km along a highway has an enormous dispersion around its
        # centroid, yet each offence may sit within a few km of the line it is
        # travelling -- which makes it MORE predictable, not less. Measuring the
        # centroid spread here would penalise exactly the structure that carries the
        # signal, and the confidence score would then withhold a forecast precisely
        # when the pattern is clearest.
        if significant:
            resid = [
                haversine_km(la, ln,
                             lat_int + lat_slope * t,
                             lng_int + lng_slope * t)
                for (la, ln), t in zip(points, days)
            ]
            residual_radius = max(MIN_RADIUS_KM, _percentile(resid, 0.75))

        drift = {
            "lat_intercept": lat_int,
            "lng_intercept": lng_int,
            "lat_per_day": lat_slope,
            "lng_per_day": lng_slope,
            "speed_km_per_day": round(speed, 3),
            "fit_r2": round(combined_r2, 3),
            "significant": significant,
            "track_scatter_km": round(residual_radius, 2) if residual_radius else None,
        }

    # The operative radius: scatter about the track for a travelling series, about the
    # centroid for a stationary one. This is what the forecast searches and what
    # confidence is judged on.
    effective = residual_radius if residual_radius is not None else radius

    return {
        "centroid": {"lat": round(clat, 6), "lng": round(clng, 6)},
        "radius_km": round(effective, 2),
        "centroid_radius_km": round(radius, 2),
        "spread_km": round(max(dists) if dists else 0.0, 2),
        "drift": drift,
    }


def _confidence(n: int, regularity: float, radius_km: float) -> float:
    """How much this series supports a forecast at all.

    Three independent factors, multiplied so a failure in any one suppresses the whole
    thing -- a perfectly regular series of three cases scattered across the state should
    not forecast confidently, and neither should twenty tightly-clustered cases whose
    timing is random.
    """
    # Sample: 3 cases is the floor, 8+ is as much as count alone can buy.
    sample = min(1.0, (n - MIN_SERIES_SIZE + 1) / 6.0)
    # Tightness of the operative radius -- scatter about the fitted track for a
    # travelling series, about the centroid for a stationary one (see _spatial_profile).
    # 5 km or less is a beat; 50 km or more is a region and forecasts nothing useful.
    tightness = max(0.0, min(1.0, 1.0 - (radius_km - 5.0) / 45.0))
    score = sample * (0.35 + 0.65 * regularity) * (0.35 + 0.65 * tightness)
    return round(max(0.0, min(1.0, score)), 3)


def _forecast(dates: list, temporal: dict, spatial: dict, confidence: float, now) -> dict | None:
    """Next expected occurrence window and location, or None when unsupported."""
    cadence = temporal.get("cadence_days")
    if not cadence or confidence < MIN_FORECAST_CONFIDENCE:
        return None

    last = dates[-1]
    centre = last + timedelta(days=cadence)
    # Half-width from observed irregularity, floored so it never implies same-day
    # precision, and widened as confidence falls.
    half = max(MIN_WINDOW_DAYS, (temporal.get("irregularity_days") or 0) * 1.5)
    half = half * (1.0 + (1.0 - confidence))

    window_start = centre - timedelta(days=half)
    window_end = centre + timedelta(days=half)

    drift = (spatial.get("drift") or {})
    centroid = spatial.get("centroid") or {}
    if drift.get("significant"):
        # Project the observed movement forward one cadence from the LAST offence --
        # for a travelling series the most recent position is far more informative than
        # the centroid of everywhere it has been.
        last_lat = spatial["_last_point"][0]
        last_lng = spatial["_last_point"][1]
        pred_lat = last_lat + drift["lat_per_day"] * cadence
        pred_lng = last_lng + drift["lng_per_day"] * cadence
        basis = (f"projected along the series' observed track "
                 f"({drift['speed_km_per_day']} km/day, fit R²={drift['fit_r2']})")
    else:
        pred_lat, pred_lng = centroid.get("lat"), centroid.get("lng")
        basis = "centred on the series centroid; no significant directional drift detected"

    # An overdue series is the single most actionable state here, so it is named.
    overdue_days = (now - window_end).days if now > window_end else 0

    return {
        "window_start": window_start,
        "window_end": window_end,
        "window_centre": centre,
        "window_half_width_days": round(half, 1),
        "predicted_epicenter": (
            {"lat": round(pred_lat, 6), "lng": round(pred_lng, 6)}
            if pred_lat is not None and pred_lng is not None else None
        ),
        "search_radius_km": spatial.get("radius_km"),
        "basis": basis,
        "state": "overdue" if overdue_days > 0 else (
            "due_now" if window_start <= now <= window_end else "upcoming"),
        "overdue_days": overdue_days,
        "days_until_window": max(0, (window_start - now).days) if now < window_start else 0,
    }


def analyse_series(db: Session, min_score: float = MIN_EDGE_SCORE,
                   min_size: int = MIN_SERIES_SIZE, now=None) -> dict:
    """Detects every serial run in the MO match graph and profiles each one."""
    now = now or utc_now()
    groups = _components(db, min_score)

    candidates = {root: ids for root, ids in groups.items() if len(ids) >= min_size}
    all_ids = [i for ids in candidates.values() for i in ids]
    if not all_ids:
        return {
            "generated_at": now, "series_count": 0, "series": [],
            "parameters": {"min_edge_score": min_score, "min_series_size": min_size},
            "note": "No connected component of the MO match graph reached the minimum series size.",
        }

    firs = {f.id: f for f in db.query(FIR).filter(FIR.id.in_(all_ids)).all()}
    mos = {m.fir_id: m for m in db.query(ModusOperandi)
           .filter(ModusOperandi.fir_id.in_(all_ids)).all()}
    stations = {s.id: s for s in db.query(PoliceStation).all()}
    districts = {d.id: d for d in db.query(District).all()}

    def _district_of(fir: FIR):
        st = stations.get(fir.police_station_id)
        if not st or st.district_id is None:
            return None, None
        d = districts.get(st.district_id)
        return (d.id, d.name) if d else (st.district_id, None)

    out = []
    for root, ids in candidates.items():
        members = [firs[i] for i in ids if i in firs]
        dated = [f for f in members if _effective_date(f)]
        dated.sort(key=_effective_date)
        if len(dated) < min_size:
            continue

        dates = [_effective_date(f) for f in dated]
        located = [(f.latitude, f.longitude) for f in dated
                   if f.latitude is not None and f.longitude is not None]

        temporal = _temporal_profile(dates)
        spatial = _spatial_profile(located, dates[:len(located)])
        if located:
            spatial["_last_point"] = located[-1]

        confidence = _confidence(len(dated), temporal["regularity"],
                                 spatial.get("radius_km") or 999)
        forecast = _forecast(dates, temporal, spatial, confidence, now) if located else None
        spatial.pop("_last_point", None)

        # The shared signature -- what actually makes these one series.
        sig_fields = {}
        for key in ("entry_method", "weapon_used", "time_of_day_pattern", "target_type"):
            vals = {getattr(mos[f.id], key) for f in dated
                    if f.id in mos and getattr(mos[f.id], key)}
            if len(vals) == 1:
                sig_fields[key] = vals.pop()

        district_ids = set()
        member_rows = []
        for f in dated:
            did, dname = _district_of(f)
            if did:
                district_ids.add(did)
            member_rows.append({
                "fir_id": f.id, "fir_number": f.fir_number,
                "date": _effective_date(f), "status": f.status,
                "district_id": did, "district_name": dname,
                "station": stations.get(f.police_station_id).name
                           if stations.get(f.police_station_id) else None,
                "lat": f.latitude, "lng": f.longitude,
            })

        out.append({
            "series_id": f"S-{root}",
            "case_count": len(dated),
            "district_count": len(district_ids),
            "first_offence": dates[0],
            "latest_offence": dates[-1],
            "span_days": (dates[-1] - dates[0]).days,
            "signature": sig_fields,
            "temporal": temporal,
            "spatial": {k: v for k, v in spatial.items() if not k.startswith("_")},
            "confidence": confidence,
            "forecast": forecast,
            "forecast_withheld_reason": (
                None if forecast else
                ("Confidence below the reporting floor "
                 f"({confidence} < {MIN_FORECAST_CONFIDENCE}); the observed pattern does "
                 "not support a location or timing estimate."
                 if located else "No member case carries coordinates.")
            ),
            "members": member_rows,
        })

    # Most urgent first: an overdue or imminent series outranks a distant one, and
    # confidence breaks ties.
    def _urgency(s):
        f = s.get("forecast")
        if not f:
            return (3, 0.0)
        rank = {"overdue": 0, "due_now": 0, "upcoming": 1}.get(f["state"], 2)
        return (rank, -s["confidence"])

    out.sort(key=_urgency)

    return {
        "generated_at": now,
        "series_count": len(out),
        "series": out,
        "parameters": {
            "min_edge_score": min_score,
            "min_series_size": min_size,
            "min_forecast_confidence": MIN_FORECAST_CONFIDENCE,
            "drift_min_r2": DRIFT_MIN_R2,
        },
        "advisory": (
            "Forecasts describe where and when a LINKED PATTERN OF OFFENCES may recur, "
            "derived from the timing and location of cases already recorded. They are "
            "intended for patrol allocation and nothing else. They do not identify, "
            "predict or profile individuals, they are not grounds for a stop, and a "
            "window passing without an offence is an ordinary outcome, not a failure of "
            "the case."
        ),
    }


def series_for_case(db: Session, fir_id: int, **kwargs) -> dict | None:
    """The series containing one case, or None if it belongs to no run."""
    analysis = analyse_series(db, **kwargs)
    for s in analysis["series"]:
        if any(m["fir_id"] == fir_id for m in s["members"]):
            return {**s, "advisory": analysis["advisory"]}
    return None
