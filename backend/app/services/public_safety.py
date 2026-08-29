"""Feature 4 — public district safety view.

Everything this module returns is served with **zero authentication**, so it is built as
an explicit allow-list: the output dict is assembled field by field from named values and
a source row is never spread into it. A field can only reach the public unless someone
adds it here deliberately.

    Approved sanitisation boundary (see NEW_FEATURES.md)

    EXPOSED : district name, district centroid lat/lng, Low|Medium|High band,
              rising|stable|falling trend, the period those cover, generic tips.
    EXCLUDED: raw risk_score, risk_factors, population, literacy/unemployment/poverty/
              urbanisation rates, any case count or rate, and everything from persons,
              accused, victims, officers, police_stations, evidence, nudges and patrol.

    Two things deliberately never published:

      * `risk_factors` reads "Risk based on urbanization 32.56% and unemp 57.64%".
        A government system attaching an unemployment figure to a place as its "risk
        factor" is editorialising about that place with official authority.
      * Counts and rates. The band is published, the number behind it is not, so
        volumes cannot be reconstructed from the page.

Banding is per-capita terciles over the trailing complete 12 months. The stored
`risk_score` is unusable for this: 40 of 43 districts hold the same value (95), which
would publish "40 of 43 districts are High risk" -- alarming and uninformative.

Terciles are RELATIVE: a third of districts sit in each band by construction, so "High"
means "in the worst third of Karnataka today", not "above an absolute danger threshold".
`methodology` says exactly that in the response, because a public reader will otherwise
supply their own meaning.
"""
import sys
import os
import threading
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app import filestore_crime_data
from app.core.timeutil import utc_now

# Functional units, not places anyone lives in. Their per-capita rates (1-2 per 100k)
# are meaningless, and "CID: Low risk" on a public map is nonsense.
NON_GEOGRAPHIC_UNITS = {
    "CID",
    "Coastal Security Police",
    "ISD Bengaluru",
    "Karnataka Railways",
}

LOW, MEDIUM, HIGH = "Low", "Medium", "High"
RISING, STABLE, FALLING = "rising", "stable", "falling"

# A half-year either side is steadier than month-over-month, which swings on seasonality.
TREND_HALF_WINDOW_MONTHS = 6
TREND_SENSITIVITY = 0.10          # +/-10% before it is called a direction rather than noise

GENERAL_TIPS = [
    "Save 112 for emergencies and 1930 for cyber-fraud reporting.",
    "Report suspicious activity to your local police station rather than acting on it yourself.",
    "Keep vehicle documents and valuables out of sight when parking.",
]

TIPS_BY_BAND = {
    LOW: [
        "Routine precautions are usually enough here.",
        "Lock vehicles and homes even for short absences.",
    ],
    MEDIUM: [
        "Prefer well-lit main roads after dark.",
        "Keep phones and chains out of sight near busy junctions and markets.",
        "Verify callers who ask for OTPs or bank details — banks never ask for them.",
    ],
    HIGH: [
        "Avoid isolated stretches after dark; use main roads where possible.",
        "Keep valuables concealed in crowded areas, transit hubs and markets.",
        "Secure homes before travelling and tell a neighbour you are away.",
        "Verify callers who ask for OTPs or bank details — banks never ask for them.",
    ],
}

DISCLAIMER = (
    "General guidance compiled from historical police records. This is not a live "
    "emergency service and does not describe current conditions — dial 112 in an emergency."
)

_lock = threading.Lock()
_cache = {"payload": None, "built_at": None}


def _month_label(period) -> str:
    return period.to_timestamp().strftime("%B %Y")


def _build() -> dict:
    """Computes the whole public payload once. Cached because this walks ~1.7M rows and
    the endpoint is unauthenticated -- recomputing per request would hand anyone a cheap
    way to load the box."""
    import pandas as pd  # local import: only needed on the build path

    ds = filestore_crime_data.get_dataset()
    if ds is None:
        return {"available": False, "reason": "Crime dataset unavailable."}
    df, districts_df = ds[0], ds[1]

    months = df["date_reported"].dt.to_period("M")
    # The most recent month in the extract is partial (a fraction of a normal month), so
    # including it would report a collapse that is really just an incomplete file.
    last_complete = months.max() - 1
    window_start = last_complete - 11
    prev_end = last_complete - TREND_HALF_WINDOW_MONTHS
    recent_start = prev_end + 1

    in_window = df[(months >= window_start) & (months <= last_complete)]
    counts = in_window.groupby("district_id").size()

    recent = df[(months >= recent_start) & (months <= last_complete)].groupby("district_id").size()
    previous = df[(months >= window_start) & (months <= prev_end)].groupby("district_id").size()

    pop = districts_df.set_index("id")["population"]
    names = districts_df.set_index("id")["name"]
    lats = districts_df.set_index("id")["latitude"]
    lngs = districts_df.set_index("id")["longitude"]

    eligible = []
    for did, name in names.items():
        if name in NON_GEOGRAPHIC_UNITS:
            continue
        population = pop.get(did)
        if not population or population <= 0:
            continue
        lat, lng = lats.get(did), lngs.get(did)
        if pd.isna(lat) or pd.isna(lng):
            continue                       # no centroid -> cannot place it on the map
        eligible.append((did, name, float(counts.get(did, 0)) / float(population) * 100_000, lat, lng))

    if not eligible:
        return {"available": False, "reason": "No eligible districts."}

    rates = sorted(r for _, _, r, _, _ in eligible)
    n = len(rates)
    t1 = rates[n // 3]
    t2 = rates[(2 * n) // 3]

    districts = []
    for did, name, rate, lat, lng in eligible:
        band = LOW if rate < t1 else (MEDIUM if rate < t2 else HIGH)

        r_now, r_prev = float(recent.get(did, 0)), float(previous.get(did, 0))
        if r_prev <= 0:
            trend = STABLE
        else:
            change = (r_now - r_prev) / r_prev
            trend = RISING if change > TREND_SENSITIVITY else (FALLING if change < -TREND_SENSITIVITY else STABLE)

        # Assembled field by field -- never a spread of the source row.
        districts.append({
            "district_name": str(name),
            "latitude": round(float(lat), 5),
            "longitude": round(float(lng), 5),
            "safety_category": band,
            "trend": trend,
            "safety_tips": TIPS_BY_BAND[band] + GENERAL_TIPS,
        })

    districts.sort(key=lambda d: d["district_name"])
    period = f"12 months to {_month_label(last_complete)}"

    return {
        "available": True,
        "data_period": period,
        "data_as_of": _month_label(last_complete),
        "generated_at": datetime.utcnow(),
        "district_count": len(districts),
        "methodology": (
            "Districts are grouped into three equal bands by recorded cases per 100,000 "
            "residents over the " + period + ". Bands are relative: \"High\" means the "
            "worst third of districts in this period, not an absolute danger threshold. "
            "Specialised units that are not geographic districts are excluded."
        ),
        "categories": [LOW, MEDIUM, HIGH],
        "disclaimer": DISCLAIMER,
        "districts": districts,
    }


def get_public_safety(force_rebuild: bool = False) -> dict:
    """Returns the cached public payload, building it on first use.

    Only a SUCCESSFUL build is cached. This previously stored whatever `_build()`
    returned, including its `{"available": False}` sentinel -- so a single request
    that arrived during the ~10 second startup window, before the background dataset
    preload finished, cached that failure permanently. The endpoint then answered 503
    for the entire life of the process even though the data had loaded seconds later,
    and nothing short of a restart cleared it (which merely re-ran the same race).

    A failed build now leaves the cache empty so the next request retries.
    """
    if force_rebuild or _cache["payload"] is None:
        with _lock:
            if force_rebuild or _cache["payload"] is None:
                payload = _build()
                if payload.get("available", True):
                    _cache["payload"] = payload
                    _cache["built_at"] = utc_now()
                else:
                    # Transient (dataset still loading). Return it to this caller, but
                    # do not poison the cache for every caller that follows.
                    return payload
    return _cache["payload"]
