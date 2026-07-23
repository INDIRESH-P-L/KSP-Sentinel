"""One-time, admin-only trigger for seeding the FULL FileStore-sourced FIR dataset (see
scripts/load_data_from_filestore.py for the full rationale and size-budget math).

Why this lives as an API route instead of just running the script directly: the Catalyst
Python SDK (zcatalyst_sdk.initialize()) only receives auth headers inside a real Catalyst
runtime context -- a bare `python script.py` process has none, so the standalone script can
never reach FileStore outside `catalyst serve` / a deployed AppSail. This backend process
IS that context (it's how core/storage.py and filestore_data.py already talk to Catalyst
successfully), so running the same seeding logic from inside it is the only way to actually
exercise it in a place where the SDK can authenticate.

Runs in a background thread (not an async task) because it does long, blocking pandas/
SQLAlchemy work for ~1.67M rows -- an in-request call would hit the client/proxy timeout
long before finishing. Status is polled via GET, not pushed, to avoid needing websockets
for what is meant to be a run-it-once operation.

Remove this router once the one-time seed has been run successfully -- it is not meant to
be a permanent part of the API surface (re-running it means dropping and rebuilding every
crime-data table, not something to expose long-term even behind admin auth).
"""
import io
import os
import random
import sys
import threading
from datetime import datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))  # repo root, for scripts/

from app.database.session import engine, SessionLocal
from app.database.models import (
    Base, District, Taluk, PoliceStation, CrimeCategory, CrimeSubcategory,
    FIR, Victim, Accused, Arrest, Conviction, Investigation, ChargeSheet,
    Officer, YearlyCrimeReview, CrimeStatistic, CrimeRiskScore, CrimeForecast,
    fir_accused,
)
from app.dependencies import get_current_admin
from app.logging import logger

from scripts.load_data import DISTRICT_COORDS, CENSUS_DISTRICT_MAP, ACCUSED_NAMES, OFFICERS, load_real_census_data

router = APIRouter(prefix="/admin/seed", tags=["Admin: One-Time Data Seed"])

FILESTORE_FOLDER_ENV = "CATALYST_FOLDER_ID"
FIR_FILE_NAMES = [f"FIR{n}.csv" for n in range(1, 10)]  # FIR1.csv .. FIR9.csv
SAMPLE_CHILD_RECORDS_EVERY_N = 300

FIR_COLUMNS = [
    'District_Name', 'UnitName', 'FIR_YEAR', 'FIR_MONTH', 'FIR_Day',
    'FIR_Stage', 'CrimeGroup_Name', 'CrimeHead_Name', 'Latitude', 'Longitude',
    'ActSection', 'IOName', 'Place of Offence', 'Male', 'Female', 'Boy', 'Girl',
    'VICTIM COUNT', 'Accused Count', 'Arrested Count\tNo.',
    'Accused_ChargeSheeted Count', 'Conviction Count',
]
_COLUMN_ALIASES = {
    'Arrested Count\tNo.': ['Arrested Count\tNo.', 'Arrested Count No.', 'Arrested Count'],
    'Accused_ChargeSheeted Count': ['Accused_ChargeSheeted Count', 'Accused ChargeSheeted Count', 'ChargeSheeted Count'],
    'VICTIM COUNT': ['VICTIM COUNT', 'Victim Count', 'VictimCount'],
}

# Single in-process job record. A dict behind a lock is enough here: this endpoint is
# meant to be triggered once by one admin, not to support concurrent seed jobs.
_job_lock = threading.Lock()
_job_state = {"status": "idle", "detail": None, "started_at": None, "finished_at": None, "fir_count": None}


def _set_job(**kwargs):
    with _job_lock:
        _job_state.update(kwargs)


def _parse_fir_csv_bytes(raw_bytes, filename: str):
    if isinstance(raw_bytes, str):
        raw_bytes = raw_bytes.encode("utf-8", errors="ignore")
    try:
        header = pd.read_csv(io.BytesIO(raw_bytes), nrows=0).columns
        resolved = {}
        for wanted in FIR_COLUMNS:
            if wanted in header:
                resolved[wanted] = wanted
                continue
            for alias in _COLUMN_ALIASES.get(wanted, []):
                if alias in header:
                    resolved[wanted] = alias
                    break
        missing = [c for c in FIR_COLUMNS if c not in resolved]
        if missing:
            logger.error(f"admin_seed: '{filename}' missing columns {missing}; skipping.")
            return None
        df = pd.read_csv(io.BytesIO(raw_bytes), usecols=list(resolved.values()))
        df = df.rename(columns={v: k for k, v in resolved.items()})
        return df
    except Exception as e:
        logger.error(f"admin_seed: Failed parsing '{filename}': {e}")
        return None


def _download_fir_csvs() -> list[pd.DataFrame]:
    import zcatalyst_sdk
    app = zcatalyst_sdk.initialize()
    loaded_names = set()
    dataframes = []

    # 1. Try loading from Stratus bucket
    bucket_name = "sentinel-migration-bucket"
    try:
        bucket = app.stratus().bucket(bucket_name)
        for name in FIR_FILE_NAMES:
            for key_candidate in [f"archive/{name}", name]:
                try:
                    obj = bucket.get_object(key_candidate)
                    raw_bytes = obj.content if hasattr(obj, "content") else (obj.read() if hasattr(obj, "read") else obj)
                    if raw_bytes:
                        df = _parse_fir_csv_bytes(raw_bytes, name)
                        if df is not None:
                            dataframes.append(df)
                            loaded_names.add(name)
                            logger.info(f"admin_seed: loaded '{name}' from Stratus bucket '{bucket_name}/{key_candidate}': {len(df)} rows.")
                            break
                except Exception as e:
                    logger.debug(f"admin_seed: key '{key_candidate}' not fetched from Stratus: {e}")
    except Exception as e:
        logger.warning(f"admin_seed: Stratus bucket fetch warning: {e}")

    # 2. Fallback to FileStore folder
    missing_names = [n for n in FIR_FILE_NAMES if n not in loaded_names]
    folder_id = os.environ.get(FILESTORE_FOLDER_ENV)
    if missing_names and folder_id:
        try:
            folder = app.file_store().get_folder_instance(int(folder_id))
            listing = folder.get_paged_files()
            if isinstance(listing, dict):
                listing = listing.get("data", []) or []
            files_by_name = {}
            for f in listing:
                fname = f.get("file_name") if isinstance(f, dict) else getattr(f, "file_name", None)
                fid = f.get("id") if isinstance(f, dict) else getattr(f, "id", None)
                if fname in missing_names:
                    files_by_name[fname] = fid

            for name in missing_names:
                file_id = files_by_name.get(name)
                if file_id is None:
                    logger.warning(f"admin_seed: '{name}' not found in FileStore or Stratus; skipping.")
                    continue
                raw = folder.download_file(int(file_id))
                df = _parse_fir_csv_bytes(raw, name)
                if df is not None:
                    dataframes.append(df)
                    loaded_names.add(name)
                    logger.info(f"admin_seed: loaded '{name}' from FileStore folder: {len(df)} rows.")
        except Exception as e:
            logger.error(f"admin_seed: FileStore error: {e}")

    if not dataframes:
        raise RuntimeError("No FIR CSVs could be loaded from Stratus bucket or FileStore.")
    return dataframes


def _bulk_insert_chunked(session, model, rows, chunk_size=20_000, label=""):
    total = len(rows)
    for i in range(0, total, chunk_size):
        session.bulk_insert_mappings(model, rows[i:i + chunk_size])
        session.commit()
        if label:
            logger.info(f"admin_seed: {label}: {min(i + chunk_size, total)}/{total}")


def _run_seed_job():
    """The actual long-running seed. Same logic as scripts/load_data_from_filestore.py --
    kept in lockstep deliberately (see that file's docstring). Download-verify-before-drop
    ordering is preserved for the same reason: a failed FileStore call must never wipe the
    working database."""
    try:
        _set_job(status="downloading", detail="Downloading FIR CSVs from FileStore...")
        frames = _download_fir_csvs()
        df = pd.concat(frames, ignore_index=True)
        logger.info(f"admin_seed: combined dataset {len(df)} rows from {len(frames)} file(s).")

        census_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "datasets", "cleaned", "karnataka_census_2011.csv")
        demographics, taluks_data = load_real_census_data() if os.path.exists(census_path) else ({}, [])

        df['District_Name'] = df['District_Name'].astype(str).str.strip()
        df['UnitName'] = df['UnitName'].astype(str).str.strip()
        df['CrimeGroup_Name'] = df['CrimeGroup_Name'].astype(str).str.strip()
        df['CrimeHead_Name'] = df['CrimeHead_Name'].astype(str).str.strip()
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

        is_postgres = "postgresql" in engine.url.drivername
        if is_postgres:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()

        _set_job(status="seeding", detail=f"Download OK ({len(df)} rows) -- rebuilding tables...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        session = SessionLocal()
        try:
            def get_point_geom(lat, lng):
                return f"SRID=4326;POINT({lng} {lat})" if is_postgres else f"POINT({lng} {lat})"

            def get_multipolygon_geom(lat, lng):
                body = f"((({lng-0.1} {lat-0.1}, {lng+0.1} {lat-0.1}, {lng+0.1} {lat+0.1}, {lng-0.1} {lat+0.1}, {lng-0.1} {lat-0.1})))"
                return f"SRID=4326;MULTIPOLYGON{body}" if is_postgres else f"MULTIPOLYGON{body}"

            db_districts = {}
            for dist_name in df['District_Name'].unique():
                coords = DISTRICT_COORDS.get(dist_name, (12.9716, 77.5946))
                census_name = CENSUS_DISTRICT_MAP.get(dist_name)
                demo = demographics.get(census_name)
                if demo:
                    pop, urb_rate, lit_rate, unemp_rate, pov_rate = (
                        demo['population'], demo['urbanization_rate'], demo['literacy_rate'],
                        demo['unemployment_rate'], demo['poverty_rate'],
                    )
                    dist_code = demo['district_code']
                else:
                    pop, urb_rate, lit_rate, unemp_rate, pov_rate, dist_code = 1_000_000, 35.0, 75.0, 5.0, 15.0, None
                risk_score = min(95, max(20, int(urb_rate * 0.4 + unemp_rate * 4.0 + pov_rate * 1.5)))
                d_obj = District(
                    name=dist_name, population=pop, risk_score=risk_score,
                    risk_factors=f"Risk based on urbanization {urb_rate}% and unemp {unemp_rate}%.",
                    urbanization_rate=urb_rate, literacy_rate=lit_rate,
                    unemployment_rate=unemp_rate, poverty_rate=pov_rate,
                    geom=get_multipolygon_geom(coords[0], coords[1]),
                )
                session.add(d_obj)
                session.flush()
                db_districts[dist_name] = d_obj.id
                session.add(CrimeRiskScore(
                    district_id=d_obj.id, score=risk_score,
                    safety_index=round(100.0 - risk_score * 0.8, 1),
                    population_density=round(pop / 4500.0, 2),
                ))
                if dist_code:
                    for t_name in [t['name'] for t in taluks_data if t['district_code'] == dist_code][:4]:
                        session.add(Taluk(
                            district_id=d_obj.id, name=t_name,
                            geom=get_multipolygon_geom(coords[0] + random.uniform(-0.04, 0.04), coords[1] + random.uniform(-0.04, 0.04)),
                        ))
            session.commit()

            _set_job(detail="Seeding police stations...")
            db_stations = {}
            station_avg_coords = df.groupby(['District_Name', 'UnitName'])[['Latitude', 'Longitude']].mean().reset_index()
            for _, row in station_avg_coords.iterrows():
                d_name, s_name = row['District_Name'], row['UnitName']
                d_coords = DISTRICT_COORDS.get(d_name, (12.9716, 77.5946))
                lat = row['Latitude'] if not pd.isna(row['Latitude']) and row['Latitude'] > 0 else d_coords[0] + random.uniform(-0.02, 0.02)
                lng = row['Longitude'] if not pd.isna(row['Longitude']) and row['Longitude'] > 0 else d_coords[1] + random.uniform(-0.02, 0.02)
                station = PoliceStation(
                    name=s_name, district_id=db_districts[d_name], latitude=lat, longitude=lng,
                    geom=get_point_geom(lat, lng),
                )
                session.add(station)
                session.flush()
                db_stations[(d_name, s_name)] = station.id
                for idx, rank in enumerate(["Inspector", "Sub-Inspector"]):
                    session.add(Officer(
                        name=f"Officer KSP-{station.id}-{idx:02d}", badge_number=f"KSP-{station.id}-{idx:02d}",
                        rank=rank, station_id=station.id, status="ACTIVE",
                    ))
            session.commit()

            _set_job(detail="Seeding crime categories...")
            db_categories, db_subcategories = {}, {}
            for cat_name in df['CrimeGroup_Name'].dropna().unique():
                cat = CrimeCategory(name=cat_name, major_head=cat_name, minor_head="General")
                session.add(cat)
                session.flush()
                db_categories[cat_name] = cat.id
            for _, row in df.groupby(['CrimeGroup_Name', 'CrimeHead_Name']).size().reset_index().iterrows():
                c_name, sub_name = row['CrimeGroup_Name'], row['CrimeHead_Name']
                sub = CrimeSubcategory(name=sub_name, category_id=db_categories[c_name])
                session.add(sub)
                session.flush()
                db_subcategories[(c_name, sub_name)] = sub.id
            session.commit()

            _set_job(status="seeding_firs", detail=f"Seeding all {len(df)} FIRs...")
            ACCUSED_POOL = [
                {"name": f"Suspect {ACCUSED_NAMES[idx % len(ACCUSED_NAMES)]} #{idx}",
                 "age": random.randint(19, 50), "gender": "Male" if random.random() > 0.1 else "Female"}
                for idx in range(15)
            ]
            fir_counter = 1
            accused_counter = 1
            bulk_firs, bulk_victims, bulk_accused = [], [], []
            bulk_arrests, bulk_convictions, bulk_chargesheets, bulk_investigations = [], [], [], []
            fir_accused_links = []

            for _, row in df.iterrows():
                d_name, s_name = row['District_Name'], row['UnitName']
                cat_name, sub_name = row['CrimeGroup_Name'], row['CrimeHead_Name']
                station_id = db_stations.get((d_name, s_name))
                subcat_id = db_subcategories.get((cat_name, sub_name))
                if not station_id or not subcat_id:
                    continue

                year = int(row['FIR_YEAR']) if not pd.isna(row['FIR_YEAR']) else 2024
                month = int(row['FIR_MONTH']) if not pd.isna(row['FIR_MONTH']) and 0 < row['FIR_MONTH'] <= 12 else random.randint(1, 12)
                try:
                    day = int(row['FIR_Day']) if not pd.isna(row['FIR_Day']) and 0 < row['FIR_Day'] <= 28 else random.randint(1, 28)
                    dt = datetime(year, month, day)
                except Exception:
                    dt = datetime(year, month, 1)
                occurred_dt = dt - timedelta(hours=random.randint(1, 48))
                fir_number = f"KSP/{d_name[:3].upper()}/{year}/{fir_counter:06d}"

                stage = str(row['FIR_Stage']).strip()
                if stage in ['Convicted', 'Dis/Acq', 'Compounded', 'Traced']:
                    status = 'CLOSED'
                elif stage in ['Pending Trial', 'BoundOver']:
                    status = 'CHARGE_SHEETED'
                elif 'UI' in stage or 'Transfered' in stage:
                    status = 'INVESTIGATING'
                else:
                    status = 'REGISTERED'

                d_coords = DISTRICT_COORDS.get(d_name, (12.9716, 77.5946))
                lat = row['Latitude'] if not pd.isna(row['Latitude']) and row['Latitude'] > 0 else d_coords[0] + random.uniform(-0.015, 0.015)
                lng = row['Longitude'] if not pd.isna(row['Longitude']) and row['Longitude'] > 0 else d_coords[1] + random.uniform(-0.015, 0.015)
                desc = str(row['Place of Offence']) if not pd.isna(row['Place of Offence']) else f"Incident of {sub_name} registered."

                bulk_firs.append({
                    "id": fir_counter, "fir_number": fir_number, "police_station_id": station_id,
                    "subcategory_id": subcat_id, "date_reported": dt, "date_occurred": occurred_dt,
                    "description": desc, "status": status, "latitude": lat, "longitude": lng,
                    "geom": get_point_geom(lat, lng),
                })
                io_name = str(row['IOName']) if not pd.isna(row['IOName']) else random.choice(OFFICERS)
                bulk_investigations.append({
                    "fir_id": fir_counter, "assigned_officer": io_name,
                    "status": "COMPLETED" if status in ['CLOSED', 'CHARGE_SHEETED'] else "ONGOING",
                    "last_updated": dt + timedelta(days=2),
                })

                if fir_counter % SAMPLE_CHILD_RECORDS_EVERY_N == 0:
                    victim_count = int(row['VICTIM COUNT']) if not pd.isna(row['VICTIM COUNT']) else 0
                    for v_idx in range(min(5, victim_count)):
                        if v_idx == 0 and int(row['Female']) > 0:
                            gender, cat = "Female", "WOMAN"
                        elif v_idx == 1 and int(row['Girl']) > 0:
                            gender, cat = "Female", "CHILD"
                        elif v_idx == 2 and int(row['Boy']) > 0:
                            gender, cat = "Male", "CHILD"
                        else:
                            gender, cat = "Male", "GENERAL"
                        bulk_victims.append({
                            "fir_id": fir_counter, "name": f"Victim #{fir_counter}-{v_idx}",
                            "age": random.randint(10, 70), "gender": gender, "category": cat,
                            "injured": 1 if status in ['CHARGE_SHEETED', 'CLOSED'] else 0,
                            "dead": 1 if "Murder" in sub_name or "Attempted Murder" in sub_name else 0,
                        })
                    acc_count = int(row['Accused Count']) if not pd.isna(row['Accused Count']) else 0
                    for a_idx in range(min(4, acc_count)):
                        acc_chosen = random.choice(ACCUSED_POOL)
                        repeat_offender = random.random() > 0.8
                        bulk_accused.append({
                            "id": accused_counter, "name": f"{acc_chosen['name']}-{accused_counter}",
                            "age": acc_chosen['age'], "gender": acc_chosen['gender'],
                            "repeat_offender": repeat_offender,
                            "history_sheet": repeat_offender and random.random() > 0.6,
                            "gang": "Local Gang B" if repeat_offender and random.random() > 0.5 else None,
                            "prior_offenses_count": random.randint(1, 5) if repeat_offender else 0,
                            "status": "ACTIVE",
                        })
                        fir_accused_links.append((fir_counter, accused_counter))
                        arrest_count = int(row['Arrested Count\tNo.']) if not pd.isna(row['Arrested Count\tNo.']) else 0
                        if arrest_count > a_idx:
                            bulk_arrests.append({
                                "fir_id": fir_counter, "accused_id": accused_counter,
                                "arrest_date": dt + timedelta(days=random.randint(1, 10)),
                                "status": "ARRESTED", "officer": random.choice(OFFICERS), "court": "JMFC Court",
                            })
                        conv_count = int(row['Conviction Count']) if not pd.isna(row['Conviction Count']) else 0
                        if conv_count > a_idx and status == 'CLOSED':
                            bulk_convictions.append({
                                "fir_id": fir_counter, "accused_id": accused_counter,
                                "conviction_date": dt + timedelta(days=random.randint(90, 200)),
                                "sentence_months": random.choice([6, 12, 24, 36]), "status": "CONVICTED",
                                "court": "District Sessions Court", "sentence": "Rigorous Imprisonment",
                                "years": float(random.choice([0.5, 1.0, 2.0])), "fine": float(random.choice([1000, 2000])),
                            })
                        accused_counter += 1
                    cs_count = int(row['Accused_ChargeSheeted Count']) if not pd.isna(row['Accused_ChargeSheeted Count']) else 0
                    if cs_count > 0:
                        bulk_chargesheets.append({
                            "fir_id": fir_counter, "filed_date": dt + timedelta(days=25),
                            "sections": str(row['ActSection'])[:190] if not pd.isna(row['ActSection']) else "IPC 1860 U/s: 379",
                            "status": "FILED",
                        })
                fir_counter += 1

            _set_job(detail=f"Inserting {len(bulk_firs)} FIRs...")
            _bulk_insert_chunked(session, FIR, bulk_firs, label="fir_cases")
            _bulk_insert_chunked(session, Investigation, bulk_investigations, label="investigations")
            _bulk_insert_chunked(session, Victim, bulk_victims, label="victims")
            _bulk_insert_chunked(session, Accused, bulk_accused, label="accused")
            if fir_accused_links:
                for i in range(0, len(fir_accused_links), 20_000):
                    chunk = fir_accused_links[i:i + 20_000]
                    session.execute(fir_accused.insert(), [{"fir_id": f, "accused_id": a} for f, a in chunk])
                    session.commit()
            _bulk_insert_chunked(session, Arrest, bulk_arrests, label="arrests")
            _bulk_insert_chunked(session, Conviction, bulk_convictions, label="convictions")
            _bulk_insert_chunked(session, ChargeSheet, bulk_chargesheets, label="chargesheets")

            _set_job(detail="Building yearly/monthly analytics aggregates...")
            yearly_counts = df.groupby(['FIR_YEAR', 'CrimeGroup_Name']).size().reset_index(name='cnt')
            for _, row in yearly_counts.iterrows():
                y, cat_name, cnt = int(row['FIR_YEAR']), row['CrimeGroup_Name'], int(row['cnt'])
                prev = yearly_counts[(yearly_counts['FIR_YEAR'] == y - 1) & (yearly_counts['CrimeGroup_Name'] == cat_name)]
                inc = round(((cnt - prev.iloc[0]['cnt']) / prev.iloc[0]['cnt']) * 100.0, 2) if not prev.empty else round(random.uniform(-5.0, 10.0), 2)
                session.add(YearlyCrimeReview(year=y, head_of_crime=cat_name, count=cnt, increase_percentage=inc))
            session.commit()

            stat_counts = df.groupby(['District_Name', 'FIR_YEAR', 'FIR_MONTH', 'CrimeGroup_Name']).size().reset_index(name='cnt')
            stat_counts = stat_counts[stat_counts['FIR_YEAR'].isin([2023, 2024])]
            bulk_stats = []
            for _, row in stat_counts.iterrows():
                d_name, y, m, cat_name, cnt = row['District_Name'], int(row['FIR_YEAR']), int(row['FIR_MONTH']), row['CrimeGroup_Name'], int(row['cnt'])
                d_id, c_id = db_districts.get(d_name), db_categories.get(cat_name)
                if d_id and c_id:
                    census_name = CENSUS_DISTRICT_MAP.get(d_name)
                    pop = demographics.get(census_name, {}).get("population", 1_000_000)
                    bulk_stats.append({
                        "district_id": d_id, "year": y, "month": m, "category_id": c_id,
                        "total_count": cnt, "rate_per_lakh": round((cnt / pop) * 100000.0, 2),
                    })
            _bulk_insert_chunked(session, CrimeStatistic, bulk_stats, label="crime_statistics")

            for y, m in [(2024, 10), (2024, 11), (2024, 12)]:
                for dist_name, d_id in db_districts.items():
                    for cat_name, c_id in db_categories.items():
                        pred_count = random.randint(5, 45) if dist_name == "Bengaluru City" else random.randint(1, 10)
                        session.add(CrimeForecast(
                            district_id=d_id, year=y, month=m, category_id=c_id,
                            predicted_count=pred_count, confidence=round(random.uniform(0.75, 0.94), 2),
                        ))
            session.commit()

            _set_job(
                status="done",
                detail=f"Seeded {len(bulk_firs)} FIRs across {len(db_districts)} districts.",
                finished_at=datetime.utcnow().isoformat(),
                fir_count=len(bulk_firs),
            )
            logger.info(f"admin_seed: completed. {len(bulk_firs)} FIRs seeded.")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"admin_seed: job failed: {e}")
        _set_job(status="failed", detail=str(e), finished_at=datetime.utcnow().isoformat())


@router.post("/filestore-firs")
def trigger_seed(admin=Depends(get_current_admin)):
    """Starts the full FileStore FIR seed in a background thread. Admin-only. Refuses to
    start a second job while one is already running/queued."""
    with _job_lock:
        if _job_state["status"] in ("downloading", "seeding", "seeding_firs"):
            raise HTTPException(status_code=409, detail="A seed job is already running.")
        _job_state.update(status="queued", detail="Queued", started_at=datetime.utcnow().isoformat(),
                          finished_at=None, fir_count=None)

    thread = threading.Thread(target=_run_seed_job, daemon=True)
    thread.start()
    return {"status": "started", "detail": "Seed job started in the background. Poll GET /api/admin/seed/status."}


@router.get("/status")
def seed_status(admin=Depends(get_current_admin)):
    with _job_lock:
        return dict(_job_state)
