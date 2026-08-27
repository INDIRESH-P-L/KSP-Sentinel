"""Seed a small demo corpus for the Investigation Intelligence features (NEW_FEATURES.md).

Purely additive and idempotent: creates tables that don't exist yet, then inserts
demo rows only when the same natural key is absent. It never drops or updates an
existing row, so it is safe to re-run and safe to point at a populated database
(load_data.py, by contrast, is destructive -- this is not that).

The fixture is shaped to exercise the new features end to end:
  * FIR #2 is a near-duplicate of #1 (same incident, same place, next day)  -> Feature 3
  * FIRs #1/#3 and #4/#5 share an MO signature ACROSS districts             -> Feature 1
  * Descriptions span snatching / burglary / phishing                       -> Feature 2
"""
import os
import sys
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.database.models import (
    Base, District, Taluk, PoliceStation, CrimeCategory, CrimeSubcategory, FIR, ModusOperandi,
)
from app.database.session import engine, SessionLocal

DISTRICTS = [("Bengaluru Urban", 13600000), ("Mysuru", 3000000), ("Mangaluru", 2100000)]
STATIONS = [
    ("Indiranagar PS", "Bengaluru Urban", 12.9719, 77.6412),
    ("Majestic Transit PS", "Bengaluru Urban", 12.9778, 77.5714),
    ("Devaraja PS", "Mysuru", 12.3052, 76.6551),
    ("Pandeshwar PS", "Mangaluru", 12.8596, 74.8436),
]
CATEGORIES = [("Theft & Burglary", "THEFT"), ("Cyber Crime", "CYBER CRIME")]
SUBCATEGORIES = [("Chain Snatching", "Theft & Burglary"), ("House Burglary", "Theft & Burglary"),
                 ("Phishing Fraud", "Cyber Crime")]

# (fir_number, station, subcategory, description, lat, lng, occurred, status, MO tuple)
# MO tuple = (entry_method, weapon_used, time_of_day_pattern, target_type)
FIRS = [
    ("BLR/2024/0101", "Indiranagar PS", "Chain Snatching",
     "Two men riding a black Pulsar motorcycle snatched a gold chain from a woman walking near 100 Feet Road "
     "at around 9 PM and sped away towards Domlur without stopping.",
     12.9719, 77.6412, datetime(2024, 5, 12, 21, 10), "INVESTIGATING",
     ("stealth", None, "night", "individual")),

    # Near-duplicate of the row above: same incident re-filed the next morning.
    ("BLR/2024/0102", "Indiranagar PS", "Chain Snatching",
     "Gold chain snatched by two men on a black Pulsar bike near 100 Feet Road at about 9 PM; "
     "the accused escaped towards Domlur without stopping.",
     12.9721, 77.6415, datetime(2024, 5, 13, 9, 30), "REGISTERED",
     ("stealth", None, "night", "individual")),

    # Same MO signature as 0101 but a DIFFERENT district -> cross-district match.
    ("MYS/2024/0044", "Devaraja PS", "Chain Snatching",
     "Gold chain snatched from an elderly woman by two riders on a motorcycle near Sayyaji Rao Road "
     "late in the evening; riders fled towards the market.",
     12.3052, 76.6551, datetime(2024, 5, 19, 22, 5), "REGISTERED",
     ("stealth", None, "night", "individual")),

    ("MNG/2024/0077", "Pandeshwar PS", "House Burglary",
     "Unknown persons broke open the rear door lock of a locked house at night and took away gold ornaments "
     "and cash while the family was away.",
     12.8596, 74.8436, datetime(2024, 6, 2, 2, 15), "INVESTIGATING",
     ("forced_entry", "rod", "night", "residence")),

    # Same MO signature as MNG/2024/0077 but a DIFFERENT district.
    ("BLR/2024/0110", "Majestic Transit PS", "House Burglary",
     "Culprits forced open the back door of a residence during the night using an iron rod and decamped "
     "with jewellery and cash.",
     12.9778, 77.5714, datetime(2024, 6, 8, 1, 40), "REGISTERED",
     ("forced_entry", "rod", "night", "residence")),

    ("BLR/2024/0120", "Majestic Transit PS", "Phishing Fraud",
     "Complainant received a call from a person posing as a bank official who obtained the OTP and "
     "fraudulently transferred money from the complainant's account.",
     12.9780, 77.5720, datetime(2024, 6, 15, 14, 20), "REGISTERED",
     ("online", None, "afternoon", "digital")),
]


def run():
    print("Ensuring tables exist (non-destructive)...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    created = {"districts": 0, "stations": 0, "categories": 0, "subcategories": 0, "firs": 0, "mo": 0}
    try:
        d_by_name = {}
        for name, pop in DISTRICTS:
            d = db.query(District).filter(District.name == name).first()
            if not d:
                d = District(name=name, population=pop, risk_score=55)
                db.add(d); db.flush(); created["districts"] += 1
            d_by_name[name] = d

        s_by_name = {}
        for name, dname, lat, lng in STATIONS:
            s = db.query(PoliceStation).filter(PoliceStation.name == name).first()
            if not s:
                s = PoliceStation(name=name, district_id=d_by_name[dname].id, latitude=lat, longitude=lng)
                db.add(s); db.flush(); created["stations"] += 1
            s_by_name[name] = s

        c_by_name = {}
        for name, major in CATEGORIES:
            c = db.query(CrimeCategory).filter(CrimeCategory.name == name).first()
            if not c:
                c = CrimeCategory(name=name, major_head=major)
                db.add(c); db.flush(); created["categories"] += 1
            c_by_name[name] = c

        sub_by_name = {}
        for name, cname in SUBCATEGORIES:
            sub = db.query(CrimeSubcategory).filter(CrimeSubcategory.name == name).first()
            if not sub:
                sub = CrimeSubcategory(name=name, category_id=c_by_name[cname].id)
                db.add(sub); db.flush(); created["subcategories"] += 1
            sub_by_name[name] = sub

        for num, stn, sub, desc, lat, lng, occurred, status, mo in FIRS:
            f = db.query(FIR).filter(FIR.fir_number == num).first()
            if not f:
                f = FIR(fir_number=num, police_station_id=s_by_name[stn].id,
                        subcategory_id=sub_by_name[sub].id, description=desc,
                        latitude=lat, longitude=lng, date_occurred=occurred,
                        date_reported=occurred, status=status)
                db.add(f); db.flush(); created["firs"] += 1
            if not db.query(ModusOperandi).filter(ModusOperandi.fir_id == f.id).first():
                db.add(ModusOperandi(fir_id=f.id, entry_method=mo[0], weapon_used=mo[1],
                                     time_of_day_pattern=mo[2], target_type=mo[3]))
                created["mo"] += 1

        db.commit()
        print("Seed complete (existing rows left untouched):")
        for k, v in created.items():
            print(f"  {k:15s} +{v}")
    except Exception as e:
        db.rollback(); print(f"Seed failed: {e}"); raise
    finally:
        db.close()


if __name__ == "__main__":
    run()


# ─────────────────────────────────────────────────────────────────────────────
# Feature 3 fixture: investigations / chargesheets / convictions
#
# Shaped so one scan produces every nudge type at once:
#   BLR/2024/0101  investigation untouched for ~40 days      -> staleness
#   BLR/2024/0102  investigation touched yesterday           -> (no staleness)
#   MYS/2024/0044  no investigation row at all, old FIR      -> staleness
#   MNG/2024/0077  chargesheet already filed                 -> (no deadline nudge)
#   BLR/2024/0110  court date 3 days out                     -> court_date
# Chargesheet-deadline nudges arise naturally for any case with no chargesheet
# whose registration + NUDGE_CHARGESHEET_DEADLINE_DAYS falls inside the window.
# ─────────────────────────────────────────────────────────────────────────────
def seed_case_timeline(reference: datetime | None = None):
    from datetime import timedelta
    from app.database.models import Investigation, ChargeSheet, Conviction, Accused

    now = reference or datetime.utcnow()
    db = SessionLocal()
    created = {"investigations": 0, "chargesheets": 0, "convictions": 0}
    try:
        plan = [
            ("BLR/2024/0101", "PSI Rao",    now - timedelta(days=40)),
            ("BLR/2024/0102", "PSI Rao",    now - timedelta(days=1)),
            ("MNG/2024/0077", "PSI Gowda",  now - timedelta(days=30)),
            ("BLR/2024/0110", "PSI Kumar",  now - timedelta(days=2)),
            ("BLR/2024/0120", "PSI Kumar",  now - timedelta(days=25)),
        ]
        for fir_number, officer, touched in plan:
            fir = db.query(FIR).filter(FIR.fir_number == fir_number).first()
            if not fir:
                continue
            if not db.query(Investigation).filter(Investigation.fir_id == fir.id).first():
                db.add(Investigation(fir_id=fir.id, assigned_officer=officer,
                                     status="ONGOING", last_updated=touched))
                created["investigations"] += 1

        # One case already has its chargesheet -> must NOT get a deadline nudge.
        fir = db.query(FIR).filter(FIR.fir_number == "MNG/2024/0077").first()
        if fir and not db.query(ChargeSheet).filter(ChargeSheet.fir_id == fir.id).first():
            db.add(ChargeSheet(fir_id=fir.id, filed_date=now - timedelta(days=5),
                               sections="BNS 331(4)", status="FILED"))
            created["chargesheets"] += 1

        # A FUTURE conviction_date stands in for a scheduled hearing (see the note in
        # app/services/nudges.py -- the schema has no hearing-date column).
        fir = db.query(FIR).filter(FIR.fir_number == "BLR/2024/0110").first()
        if fir and not db.query(Conviction).filter(Conviction.fir_id == fir.id).first():
            accused = db.query(Accused).first()
            if accused is None:
                accused = Accused(name="Demo Accused", age=32, gender="M")
                db.add(accused); db.flush()
            db.add(Conviction(fir_id=fir.id, accused_id=accused.id,
                              conviction_date=now + timedelta(days=3),
                              status="PENDING_TRIAL", court="Sessions Court, Bengaluru"))
            created["convictions"] += 1

        db.commit()
        print("Case-timeline fixture (existing rows left untouched):")
        for k, v in created.items():
            print(f"  {k:16s} +{v}")
    except Exception as e:
        db.rollback(); print(f"Case-timeline seed failed: {e}"); raise
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Feature 1 fixture: officers, on-duty shifts, forecast hotspots.
#
# Shaped to exercise the interesting cases in one run:
#   * more hotspots than officers -> the lowest-priority ones stay UNCOVERED
#   * one officer at a station with NO coordinates -> excluded, not defaulted
#   * one off_duty and one on_leave officer -> must not be assigned
#   * hotspots deliberately closer to the "wrong" station, so greedy and the
#     Hungarian optimum diverge and the comparison endpoint has something to show
# ─────────────────────────────────────────────────────────────────────────────
def seed_patrol(reference: datetime | None = None):
    from datetime import timedelta
    from app.database.models import Officer, OfficerShift, CrimeHotspot, PoliceStation

    now = reference or datetime.utcnow()
    db = SessionLocal()
    created = {"officers": 0, "shifts": 0, "hotspots": 0, "stations": 0}
    try:
        # A station with no coordinates, to prove located-station filtering.
        if not db.query(PoliceStation).filter(PoliceStation.name == "Unlocated Outpost").first():
            d = db.query(District).filter(District.name == "Bengaluru Urban").first()
            db.add(PoliceStation(name="Unlocated Outpost", district_id=d.id if d else None))
            created["stations"] += 1
            db.flush()

        stations = {s.name: s for s in db.query(PoliceStation).all()}
        roster = [
            # (name, badge, rank, station, shift status)
            ("H. Raju",     "KSP-1001", "Head Constable", "Indiranagar PS",      "on_duty"),
            ("S. Meena",    "KSP-1002", "Constable",      "Indiranagar PS",      "on_duty"),
            ("V. Prakash",  "KSP-1003", "PSI",            "Majestic Transit PS", "on_duty"),
            ("A. Fernandes","KSP-1004", "Constable",      "Majestic Transit PS", "off_duty"),
            ("R. Devi",     "KSP-1005", "Constable",      "Indiranagar PS",      "on_leave"),
            ("N. Shetty",   "KSP-1006", "Constable",      "Unlocated Outpost",   "on_duty"),
        ]
        for name, badge, rank, station_name, status in roster:
            officer = db.query(Officer).filter(Officer.badge_number == badge).first()
            station = stations.get(station_name)
            if not officer:
                officer = Officer(name=name, badge_number=badge, rank=rank,
                                  station_id=station.id if station else None, status="ACTIVE")
                db.add(officer); db.flush(); created["officers"] += 1
            if not db.query(OfficerShift).filter(OfficerShift.officer_id == officer.id).first():
                db.add(OfficerShift(
                    officer_id=officer.id, station_id=station.id if station else None,
                    shift_start=now - timedelta(hours=2), shift_end=now + timedelta(hours=6),
                    status=status))
                created["shifts"] += 1

        # Five hotspots for three assignable officers -> ranks 4 and 5 stay uncovered.
        hotspots = [
            ("Indiranagar PS",      12.9740, 77.6430, 9.4),
            ("Majestic Transit PS", 12.9790, 77.5730, 8.1),
            ("Indiranagar PS",      12.9705, 77.6395, 6.7),
            ("Majestic Transit PS", 12.9760, 77.5700, 4.2),
            ("Indiranagar PS",      12.9800, 77.6500, 2.8),
        ]
        for station_name, lat, lng, intensity in hotspots:
            station = stations.get(station_name)
            if not station:
                continue
            exists = (db.query(CrimeHotspot)
                        .filter(CrimeHotspot.police_station_id == station.id,
                                CrimeHotspot.latitude == lat,
                                CrimeHotspot.longitude == lng).first())
            if not exists:
                db.add(CrimeHotspot(police_station_id=station.id, latitude=lat, longitude=lng,
                                    intensity=intensity, prediction_date=now.date()))
                created["hotspots"] += 1

        db.commit()
        print("Patrol fixture (existing rows left untouched):")
        for k, v in created.items():
            print(f"  {k:12s} +{v}")
    except Exception as e:
        db.rollback(); print(f"Patrol seed failed: {e}"); raise
    finally:
        db.close()
