"""
Non-destructive migration for the Person/Location/ModusOperandi/Vehicle intelligence
layer (KSP Sentinel gap-analysis roadmap, section 2). Unlike load_data.py this does
NOT drop existing tables — it only creates the new ones and backfills them from the
existing Accused/Victim/FIR records already in the database. Safe to re-run: every
insert is guarded by an existence check first.
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from backend.app.database.models import (
    Base, FIR, Accused, Victim,
    Person, Location, PersonIncidentLink, ModusOperandi,
)
from backend.app.database.session import engine, SessionLocal
from sqlalchemy import text, inspect

WEAPON_KEYWORDS = ["knife", "gun", "firearm", "revolver", "pistol", "rod", "blade", "chain", "sword", "axe", "acid"]

TARGET_TYPE_BY_CATEGORY = {
    "BURGLARY": "residence",
    "THEFT": "individual",
    "CYBER CRIME": "digital",
    "MURDER": "individual",
    "ASSAULT": "individual",
    "KIDNAPPING": "individual",
    "RIOTS": "public_order",
    "FRAUD": "individual",
}


def ensure_columns():
    """Adds columns to pre-existing tables that create_all() can't retrofit."""
    inspector = inspect(engine)
    with engine.connect() as conn:
        station_cols = {c["name"] for c in inspector.get_columns("police_stations")}
        if "taluk_id" not in station_cols:
            print("Adding police_stations.taluk_id ...")
            conn.execute(text("ALTER TABLE police_stations ADD COLUMN taluk_id INTEGER"))
            conn.commit()

        fir_cols = {c["name"] for c in inspector.get_columns("fir_cases")}
        if "location_id" not in fir_cols:
            print("Adding fir_cases.location_id ...")
            conn.execute(text("ALTER TABLE fir_cases ADD COLUMN location_id INTEGER"))
            conn.commit()


def derive_entry_method(subcategory_name: str):
    if not subcategory_name:
        return None
    name = subcategory_name.lower()
    if "by day" in name:
        return "day_entry"
    if "by night" in name:
        return "night_entry"
    if any(k in name for k in ["cyber", "phishing", "online", "identity theft", "social media"]):
        return "online"
    if "pickpocket" in name:
        return "stealth"
    return "unknown"


def derive_weapon(description: str):
    if not description:
        return None
    text_lower = description.lower()
    for kw in WEAPON_KEYWORDS:
        if kw in text_lower:
            return kw
    return None


def derive_time_of_day(date_occurred):
    if not date_occurred:
        return None
    h = date_occurred.hour
    if h >= 22 or h < 4:
        return "night"
    if 4 <= h < 12:
        return "morning"
    if 12 <= h < 18:
        return "afternoon"
    return "evening"


def derive_target_type(category_major_head: str, subcategory_name: str):
    if subcategory_name and any(k in subcategory_name.lower() for k in ["vehicle", "bicycle"]):
        return "vehicle"
    return TARGET_TYPE_BY_CATEGORY.get(category_major_head, "individual")


SENSITIVE_OFFENSE_KEYWORDS = ["women", "child", "pocso", "rape", "sexual", "molest", "dowry"]


def is_sensitive_victim(victim):
    """Section 228A IPC / equivalent BNS provision: identity suppression applies to victims
    of specific offences (sexual assault, POCSO, etc.), not to every female/child victim."""
    if victim.category not in ("WOMAN", "CHILD"):
        return False
    fir = victim.fir
    sub_name = (fir.subcategory.name if fir and fir.subcategory else "") or ""
    return any(k in sub_name.lower() for k in SENSITIVE_OFFENSE_KEYWORDS)


def backfill_locations(session):
    print("Backfilling Location records from FIR coordinates...")
    existing = {(round(l.latitude, 4), round(l.longitude, 4)): l.id for l in session.query(Location).all()}
    firs = session.query(FIR).filter(FIR.location_id.is_(None), FIR.latitude.isnot(None), FIR.longitude.isnot(None)).all()

    new_locations = 0
    for f in firs:
        key = (round(f.latitude, 4), round(f.longitude, 4))
        loc_id = existing.get(key)
        if loc_id is None:
            loc = Location(
                address_text=f.description,
                latitude=f.latitude,
                longitude=f.longitude,
                location_type="crime_scene",
            )
            session.add(loc)
            session.flush()
            existing[key] = loc.id
            loc_id = loc.id
            new_locations += 1
        f.location_id = loc_id

    session.commit()
    print(f"  Created {new_locations} new Location records; linked {len(firs)} FIRs.")


def backfill_persons_and_links(session):
    print("Backfilling Person records and PersonIncidentLink edges...")
    already_accused = {p.source_accused_id for p in session.query(Person).filter(Person.source_accused_id.isnot(None)).all()}
    already_victim = {p.source_victim_id for p in session.query(Person).filter(Person.source_victim_id.isnot(None)).all()}

    accused_rows = session.query(Accused).filter(~Accused.id.in_(already_accused)).all() if already_accused else session.query(Accused).all()
    new_persons = 0
    for a in accused_rows:
        p = Person(full_name=a.name, age=a.age, gender=a.gender, source_accused_id=a.id)
        session.add(p)
        session.flush()
        new_persons += 1
        for fir in a.firs:
            session.add(PersonIncidentLink(person_id=p.id, fir_id=fir.id, role="accused"))

    victim_rows = session.query(Victim).filter(~Victim.id.in_(already_victim)).all() if already_victim else session.query(Victim).all()
    for v in victim_rows:
        sensitive = is_sensitive_victim(v)
        p = Person(full_name=v.name, age=v.age, gender=v.gender, source_victim_id=v.id, sensitive=sensitive)
        session.add(p)
        session.flush()
        new_persons += 1
        session.add(PersonIncidentLink(person_id=p.id, fir_id=v.fir_id, role="victim"))

    session.commit()
    print(f"  Created {new_persons} new Person records ({len(accused_rows)} accused, {len(victim_rows)} victims).")


def backfill_modus_operandi(session):
    print("Backfilling structured ModusOperandi tags...")
    already = {m.fir_id for m in session.query(ModusOperandi.fir_id).all()}
    firs = session.query(FIR).filter(~FIR.id.in_(already)).all() if already else session.query(FIR).all()

    count = 0
    for f in firs:
        sub = f.subcategory
        sub_name = sub.name if sub else None
        cat_major = sub.category.major_head if (sub and sub.category) else None

        mo = ModusOperandi(
            fir_id=f.id,
            entry_method=derive_entry_method(sub_name),
            weapon_used=derive_weapon(f.description),
            time_of_day_pattern=derive_time_of_day(f.date_occurred),
            target_type=derive_target_type(cat_major, sub_name),
        )
        session.add(mo)
        count += 1

    session.commit()
    print(f"  Created {count} ModusOperandi records.")


def run():
    print("Ensuring intelligence-layer tables exist (non-destructive, only adds missing tables)...")
    Base.metadata.create_all(bind=engine)
    ensure_columns()

    session = SessionLocal()
    try:
        backfill_locations(session)
        backfill_persons_and_links(session)
        backfill_modus_operandi(session)
        print("Intelligence layer migration complete. Vehicle/VehicleIncidentLink tables were "
              "created but left empty — no vehicle data exists in the current source dataset yet.")
    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run()
