"""Seed a realistic travelling burglary series, for the serial-series detector.

Why a fixture is needed
-----------------------
Series detection reads the MO match graph, which is built from the structured
`modus_operandi` table. The demo corpus in seed_demo_intelligence_data.py contains
matched *pairs*, which is exactly what a pair-matcher produces and exactly what a series
detector cannot use -- a component of two is not a run.

This seeds a genuine run: eight house burglaries sharing one signature, moving northwest
along the NH-48 corridor out of Bengaluru at a roughly nine-day cadence. That shape is
deliberate, because it exercises every part of the analysis:

  * eight cases      -> clears MIN_SERIES_SIZE with sample confidence to spare
  * ~9 day intervals -> a measurable cadence with a realistic amount of jitter
  * a real corridor  -> a significant spatial drift rather than a stationary cluster
  * six districts    -> the cross-district condition MO matching requires

Nothing here is inserted twice: every row is guarded by its natural key, so this is safe
to re-run and safe against an already-populated database.

    cd backend
    python scripts/seed_crime_series.py            # seed
    python scripts/seed_crime_series.py --rebuild  # seed, then run MO matching

The dates are anchored relative to *today* so the forecast window always lands in a
useful place for a demo rather than drifting years into the past.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

from app.core.timeutil import utc_now  # noqa: E402
from app.database.models import (  # noqa: E402
    Base, CrimeCategory, CrimeSubcategory, District, FIR, ModusOperandi, PoliceStation,
)
from app.database.session import SessionLocal, engine  # noqa: E402

# Districts along the NH-48 corridor, Bengaluru outward to the northwest.
CORRIDOR = [
    # (district, population, station, lat, lng)
    ("Bengaluru Urban", 13600000, "Yeshwanthpur PS", 13.0230, 77.5500),
    ("Bengaluru Rural", 1000000,  "Nelamangala PS",  13.0996, 77.3940),
    ("Tumakuru",        2680000,  "Tumakuru Town PS", 13.3392, 77.1010),
    ("Chitradurga",     1660000,  "Chitradurga Town PS", 14.2251, 76.3980),
    ("Davanagere",      1950000,  "Davanagere South PS", 14.4644, 75.9218),
    ("Haveri",          1600000,  "Haveri Town PS",  14.7935, 75.4044),
    ("Dharwad",         1850000,  "Hubballi Town PS", 15.3647, 75.1240),
]

# The shared signature. Identical across every member -- that is what makes it a series
# rather than seven unrelated burglaries.
SIGNATURE = ("forced_entry", "iron rod", "night", "residence")

# (days_before_today, district index, fir suffix, description)
# Gaps: 9, 8, 10, 9, 11, 8, 9 -> a median near 9 with believable jitter, so the
# irregularity measure has something real to compute.
SERIES = [
    (64, 0, "0311", "Rear door forced open with an iron rod between 1 AM and 3 AM while the "
                    "family was away; gold ornaments and cash taken from an almirah. No CCTV "
                    "on the lane."),
    (55, 1, "0327", "Rear grille prised open with a rod at night; almirah broken and jewellery "
                    "removed. Neighbours reported a white van parked near the service road."),
    (47, 2, "0402", "House on the outskirts entered through the back door, forced with a rod, "
                    "around 2 AM. Cash and gold taken; the rest of the house left undisturbed."),
    (37, 3, "0418", "Locked house broken into at night through the rear entrance using an iron "
                    "rod. Only the bedroom almirah was targeted."),
    (28, 4, "0433", "Rear door lock levered off with a rod between midnight and 3 AM. Gold "
                    "chains and cash missing; electronics untouched."),
    (17, 5, "0447", "Night-time forced entry at the back of the house with an iron rod; almirah "
                    "opened and jewellery taken. A white van was seen on the highway service road."),
    (9,  6, "0461", "Rear door forced with a rod around 2 AM while the occupants were at a "
                    "wedding. Cash and gold ornaments removed from the bedroom."),
    (1,  6, "0470", "Second burglary in the same town within a fortnight: rear entry forced with "
                    "an iron rod at night, only jewellery and cash taken."),
]


def _get_or_create(db, model, defaults=None, **kw):
    row = db.query(model).filter_by(**kw).first()
    if row:
        return row, False
    row = model(**{**kw, **(defaults or {})})
    db.add(row)
    db.flush()
    return row, True


def run(rebuild: bool = False) -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    made = {"districts": 0, "stations": 0, "firs": 0, "mo": 0}
    try:
        category, new = _get_or_create(db, CrimeCategory, name="Theft & Burglary")
        subcat, _ = _get_or_create(db, CrimeSubcategory, name="House Burglary",
                                   defaults={"category_id": category.id})

        stations = []
        for dname, pop, sname, lat, lng in CORRIDOR:
            d, created = _get_or_create(db, District, name=dname,
                                        defaults={"population": pop})
            made["districts"] += int(created)
            s, created = _get_or_create(db, PoliceStation, name=sname,
                                        defaults={"district_id": d.id,
                                                  "latitude": lat, "longitude": lng})
            made["stations"] += int(created)
            stations.append((s, lat, lng))

        today = utc_now().replace(hour=2, minute=30, second=0, microsecond=0)

        for days_ago, idx, suffix, desc in SERIES:
            station, lat, lng = stations[idx]
            number = f"SER/2026/{suffix}"
            occurred = today - timedelta(days=days_ago)

            fir = db.query(FIR).filter(FIR.fir_number == number).first()
            if not fir:
                # Nudge each offence slightly off its station so the series has real
                # spatial spread rather than a stack of identical points.
                jitter = (idx * 0.004) - 0.012
                fir = FIR(
                    fir_number=number,
                    police_station_id=station.id,
                    subcategory_id=subcat.id,
                    description=desc,
                    latitude=round(lat + jitter, 6),
                    longitude=round(lng - jitter * 0.6, 6),
                    date_occurred=occurred,
                    date_reported=occurred + timedelta(hours=7),
                    status="INVESTIGATING",
                )
                db.add(fir)
                db.flush()
                made["firs"] += 1

            if not db.query(ModusOperandi).filter(ModusOperandi.fir_id == fir.id).first():
                db.add(ModusOperandi(
                    fir_id=fir.id, entry_method=SIGNATURE[0], weapon_used=SIGNATURE[1],
                    time_of_day_pattern=SIGNATURE[2], target_type=SIGNATURE[3]))
                made["mo"] += 1

        db.commit()
        print("Seeded travelling burglary series (existing rows untouched):")
        for k, v in made.items():
            print(f"  {k:12s} +{v}")

        if rebuild:
            from app.services.mo_matching import run_mo_matching
            print("\nRebuilding MO matches...")
            result = run_mo_matching(db)
            for k, v in result.items():
                if not isinstance(v, (dict, list)):
                    print(f"  {k:24s} {v}")
        else:
            print("\nRun MO matching to link them into a detectable series:")
            print("  python scripts/seed_crime_series.py --rebuild")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"Seed failed: {type(exc).__name__}: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed a travelling burglary series.")
    ap.add_argument("--rebuild", action="store_true",
                    help="Run MO matching afterwards so the series is immediately detectable.")
    raise SystemExit(run(ap.parse_args().rebuild))
