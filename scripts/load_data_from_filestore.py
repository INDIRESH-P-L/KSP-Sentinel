"""Seeds ksp_sentinel.db with the FULL Karnataka FIR dataset (~1.67M rows across all 41
districts), sourced from FIR4.csv..FIR9.csv in the Zoho Catalyst FileStore `ksp` folder --
NOT from a local datasets/raw/fir/ file. This is deliberately a separate script from
scripts/load_data.py (which reads a local Kaggle CSV and only samples 1-in-60 rows for a
lightweight demo DB); this one is for "give me everything the FileStore actually has."

Why a from-scratch FIR insert instead of importing load_data.py:
  * load_data.py's seed_database() hardcodes RAW_FIR_PATH (a local file) and drops/recreates
    ALL tables including districts/categories built from that specific file's structure --
    reusing it as a library function would mean either duplicating its 700 lines to swap one
    path, or risking a second run silently clobbering data seeded by this script. A parallel
    script with the same district/station/category-building logic (kept in lockstep
    deliberately) is more predictable than fighting that coupling.

Size budget (see the conversation this was built from for the arithmetic): the existing
demo DB spends ~9.4KB/FIR, of which ~88% is a 384-float mock embedding used only for the
demo semantic-search fallback. At 1.67M FIRs that would be ~15GB -- nowhere close to a 1GB
disk. This script:
  - Inserts EVERY fir_cases row from all 9 FileStore files (~1.67M) -- this is the row that
    drives every dashboard chart/KPI/district ranking, so it must be complete, not sampled.
  - Skips crime_embeddings entirely (demo-only mock vectors; dropping them saves ~85% of the
    old per-FIR footprint and doesn't remove any real functionality -- FAISS/cosine search
    was already running on synthetic embeddings, not real ones).
  - Generates victims/accused/arrests/convictions/chargesheets for only a small deterministic
    sample of FIRs (SAMPLE_CHILD_RECORDS_EVERY_N below) so case-detail/timeline views still
    have real-looking sub-records to render, without paying the ~60x volume cost of doing it
    for all 1.67M cases.
  - Still builds YearlyCrimeReview / CrimeStatistic / CrimeForecast from the FULL dataset's
    aggregates (a GROUP BY over 1.67M rows costs nothing extra in row count), so those
    analytics reflect the complete data even though child-record detail doesn't.

Requires Catalyst SDK credentials (zcatalyst_sdk.initialize()) -- run this from a
Catalyst-authenticated environment (Catalyst CLI login, or on AppSail), same requirement as
backend/app/filestore_data.py. It cannot be exercised from a plain unauthenticated shell.

Usage:
    cd backend  (so `python -m app...`-style imports resolve the same as the rest of the app)
    python ../scripts/load_data_from_filestore.py
"""
import os
import sys
import io
import random
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from backend.app.database.models import (
    Base, District, Taluk, PoliceStation, CrimeCategory, CrimeSubcategory,
    FIR, Victim, Accused, Arrest, Conviction, Investigation, ChargeSheet,
    Officer, YearlyCrimeReview, CrimeStatistic, CrimeRiskScore, CrimeForecast,
    fir_accused,
)
from backend.app.database.session import engine, SessionLocal
from backend.app.logging import logger

# Reuse the exact district coordinate/census-mapping tables from load_data.py rather than
# forking a second copy that could drift out of sync.
from load_data import DISTRICT_COORDS, CENSUS_DISTRICT_MAP, ACCUSED_NAMES, OFFICERS, load_real_census_data

FILESTORE_FOLDER_ENV = "CATALYST_FOLDER_ID"  # same env var filestore_data.py reads
FIR_FILE_NAMES = [f"FIR{n}.csv" for n in range(4, 10)]  # FIR4.csv .. FIR9.csv

# Every Nth FIR (by insertion order) gets victims/accused/arrests/convictions/chargesheets.
# 1.67M / 300 =~ 5,570 cases with full sub-record detail -- enough for the case-detail /
# timeline views to always have real examples without paying the full per-row cost 1.67M times.
SAMPLE_CHILD_RECORDS_EVERY_N = 300

# Columns actually used from the FIR CSVs. Matches scripts/load_data.py's `cols` list --
# see that script for why each one is needed (station/category derivation, dates, status,
# child-record counts).
FIR_COLUMNS = [
    'District_Name', 'UnitName', 'FIR_YEAR', 'FIR_MONTH', 'FIR_Day',
    'FIR_Stage', 'CrimeGroup_Name', 'CrimeHead_Name', 'Latitude', 'Longitude',
    'ActSection', 'IOName', 'Place of Offence', 'Male', 'Female', 'Boy', 'Girl',
    'VICTIM COUNT', 'Accused Count', 'Arrested Count\tNo.',
    'Accused_ChargeSheeted Count', 'Conviction Count',
]

# Tolerant header matching: the FileStore split files may not use byte-identical column
# names/casing/whitespace to the single Kaggle CSV load_data.py was built against.
_COLUMN_ALIASES = {
    'Arrested Count\tNo.': ['Arrested Count\tNo.', 'Arrested Count No.', 'Arrested Count'],
    'Accused_ChargeSheeted Count': ['Accused_ChargeSheeted Count', 'Accused ChargeSheeted Count', 'ChargeSheeted Count'],
    'VICTIM COUNT': ['VICTIM COUNT', 'Victim Count', 'VictimCount'],
}


def _get_catalyst_app():
    import zcatalyst_sdk
    return zcatalyst_sdk.initialize()


def _download_fir_csvs() -> list[pd.DataFrame]:
    """Downloads FIR4.csv..FIR9.csv from the Catalyst FileStore `ksp` folder and parses
    each into a DataFrame restricted to FIR_COLUMNS. Skips (with a logged warning) any file
    that's missing, fails to download, or is missing required columns -- a partial dataset
    from 8 files is far better than the whole run aborting because file #9 hiccuped."""
    app = _get_catalyst_app()
    folder_id = os.environ.get(FILESTORE_FOLDER_ENV)
    if not folder_id:
        raise RuntimeError(
            f"{FILESTORE_FOLDER_ENV} is not set. Set it to the `ksp` FileStore folder id "
            f"(see .env / backend/.env -- the same value backend/app/filestore_data.py uses)."
        )
    folder = app.file_store().get_folder_instance(int(folder_id))

    files_by_name = {}
    listing = folder.get_paged_files()
    if isinstance(listing, dict):
        listing = listing.get("data", []) or []
    for f in listing:
        name = f.get("file_name") if isinstance(f, dict) else getattr(f, "file_name", None)
        fid = f.get("id") if isinstance(f, dict) else getattr(f, "id", None)
        if name in FIR_FILE_NAMES:
            files_by_name[name] = fid

    dataframes = []
    for name in FIR_FILE_NAMES:
        file_id = files_by_name.get(name)
        if file_id is None:
            logger.warning(f"load_data_from_filestore: '{name}' not found in FileStore folder; skipping.")
            continue
        try:
            raw = folder.download_file(int(file_id))
            if isinstance(raw, str):
                raw = raw.encode("utf-8", errors="ignore")
            header = pd.read_csv(io.BytesIO(raw), nrows=0).columns
            # Resolve each wanted column to whatever header name is actually present.
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
                logger.error(f"load_data_from_filestore: '{name}' is missing columns {missing}; skipping this file.")
                continue
            df = pd.read_csv(io.BytesIO(raw), usecols=list(resolved.values()))
            df = df.rename(columns={v: k for k, v in resolved.items()})
            dataframes.append(df)
            print(f"  Loaded {name}: {len(df)} rows.")
        except Exception as e:
            logger.error(f"load_data_from_filestore: failed to download/parse '{name}' ({e}); skipping.")
            continue

    if not dataframes:
        raise RuntimeError("No FIR CSVs could be loaded from FileStore -- nothing to seed.")
    return dataframes


def _bulk_insert_chunked(session, model, rows: list[dict], chunk_size: int = 20_000, label: str = ""):
    """bulk_insert_mappings on 1.67M dicts at once holds the whole list AND its SQL
    translation in memory simultaneously; chunking keeps peak memory bounded and gives
    visible progress on a run that otherwise looks hung for several minutes."""
    total = len(rows)
    for i in range(0, total, chunk_size):
        session.bulk_insert_mappings(model, rows[i:i + chunk_size])
        session.commit()
        if label:
            print(f"    {label}: {min(i + chunk_size, total)}/{total}")


def seed_database_from_filestore():
    is_postgres = "postgresql" in engine.url.drivername
    if is_postgres:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()

    # Download FIRST, drop/recreate tables only once we know we actually have data to
    # replace them with. This table currently holds a real, working seeded database --
    # a FileStore/auth failure here must NOT wipe it out from under a failed run.
    print("Downloading FIR CSVs from Catalyst FileStore...")
    frames = _download_fir_csvs()
    df = pd.concat(frames, ignore_index=True)
    print(f"Combined dataset: {len(df)} total FIR rows across {len(frames)} file(s).")

    demographics, taluks_data = load_real_census_data() if os.path.exists(
        os.path.join(os.path.dirname(__file__), "..", "datasets", "cleaned", "karnataka_census_2011.csv")
    ) else ({}, [])

    print("Download succeeded -- recreating database tables now...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    df['District_Name'] = df['District_Name'].astype(str).str.strip()
    df['UnitName'] = df['UnitName'].astype(str).str.strip()
    df['CrimeGroup_Name'] = df['CrimeGroup_Name'].astype(str).str.strip()
    df['CrimeHead_Name'] = df['CrimeHead_Name'].astype(str).str.strip()
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

    session = SessionLocal()

    try:
        def get_point_geom(lat, lng):
            if is_postgres:
                return f"SRID=4326;POINT({lng} {lat})"
            return f"POINT({lng} {lat})"

        def get_multipolygon_geom(lat, lng):
            if is_postgres:
                return f"SRID=4326;MULTIPOLYGON((({lng-0.1} {lat-0.1}, {lng+0.1} {lat-0.1}, {lng+0.1} {lat+0.1}, {lng-0.1} {lat+0.1}, {lng-0.1} {lat-0.1})))"
            return f"MULTIPOLYGON((({lng-0.1} {lat-0.1}, {lng+0.1} {lat-0.1}, {lng+0.1} {lat+0.1}, {lng-0.1} {lat+0.1}, {lng-0.1} {lat-0.1})))"

        # A. Districts + Taluks (identical logic to load_data.py)
        print("Seeding Districts and Taluks...")
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
                matched_taluks = [t['name'] for t in taluks_data if t['district_code'] == dist_code]
                for t_name in matched_taluks[:4]:
                    session.add(Taluk(
                        district_id=d_obj.id, name=t_name,
                        geom=get_multipolygon_geom(coords[0] + random.uniform(-0.04, 0.04), coords[1] + random.uniform(-0.04, 0.04)),
                    ))
        session.commit()

        # B. Police Stations + Officers
        print("Seeding Police Stations...")
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

        # C. Categories & Subcategories
        print("Seeding Crime Categories & Subcategories...")
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

        # D. FIRs -- EVERY row, not a sample. Child records only for every Nth FIR.
        print(f"Seeding ALL {len(df)} FIRs (child records sampled every {SAMPLE_CHILD_RECORDS_EVERY_N}th case)...")
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
        skipped_no_station_or_subcat = 0

        for _, row in df.iterrows():
            d_name, s_name = row['District_Name'], row['UnitName']
            cat_name, sub_name = row['CrimeGroup_Name'], row['CrimeHead_Name']
            station_id = db_stations.get((d_name, s_name))
            subcat_id = db_subcategories.get((cat_name, sub_name))
            if not station_id or not subcat_id:
                skipped_no_station_or_subcat += 1
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

            # Lightweight investigation row for every FIR (needed for status/timeline views).
            io_name = str(row['IOName']) if not pd.isna(row['IOName']) else random.choice(OFFICERS)
            bulk_investigations.append({
                "fir_id": fir_counter, "assigned_officer": io_name,
                "status": "COMPLETED" if status in ['CLOSED', 'CHARGE_SHEETED'] else "ONGOING",
                "last_updated": dt + timedelta(days=2),
            })

            # Full child-record detail only for the sampled subset.
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

        if skipped_no_station_or_subcat:
            print(f"  Skipped {skipped_no_station_or_subcat} rows with no matching station/subcategory.")

        print(f"Inserting {len(bulk_firs)} FIRs...")
        _bulk_insert_chunked(session, FIR, bulk_firs, label="fir_cases")
        print(f"Inserting {len(bulk_investigations)} investigations...")
        _bulk_insert_chunked(session, Investigation, bulk_investigations, label="investigations")
        print(f"Inserting {len(bulk_victims)} sampled victims...")
        _bulk_insert_chunked(session, Victim, bulk_victims, label="victims")
        print(f"Inserting {len(bulk_accused)} sampled accused...")
        _bulk_insert_chunked(session, Accused, bulk_accused, label="accused")

        if fir_accused_links:
            print(f"Linking {len(fir_accused_links)} FIR-accused pairs...")
            for i in range(0, len(fir_accused_links), 20_000):
                chunk = fir_accused_links[i:i + 20_000]
                session.execute(fir_accused.insert(), [{"fir_id": f, "accused_id": a} for f, a in chunk])
                session.commit()

        print(f"Inserting {len(bulk_arrests)} arrests, {len(bulk_convictions)} convictions, {len(bulk_chargesheets)} chargesheets...")
        _bulk_insert_chunked(session, Arrest, bulk_arrests, label="arrests")
        _bulk_insert_chunked(session, Conviction, bulk_convictions, label="convictions")
        _bulk_insert_chunked(session, ChargeSheet, bulk_chargesheets, label="chargesheets")

        # E. Yearly Crime Reviews -- from the FULL dataset, same as load_data.py.
        print("Calculating and seeding Yearly Crime Reviews...")
        yearly_counts = df.groupby(['FIR_YEAR', 'CrimeGroup_Name']).size().reset_index(name='cnt')
        for _, row in yearly_counts.iterrows():
            y, cat_name, cnt = int(row['FIR_YEAR']), row['CrimeGroup_Name'], int(row['cnt'])
            prev = yearly_counts[(yearly_counts['FIR_YEAR'] == y - 1) & (yearly_counts['CrimeGroup_Name'] == cat_name)]
            inc = round(((cnt - prev.iloc[0]['cnt']) / prev.iloc[0]['cnt']) * 100.0, 2) if not prev.empty else round(random.uniform(-5.0, 10.0), 2)
            session.add(YearlyCrimeReview(year=y, head_of_crime=cat_name, count=cnt, increase_percentage=inc))
        session.commit()

        # F. Monthly Crime Statistics -- full dataset, recent years only (same cutoff as load_data.py).
        print("Calculating and seeding monthly Crime Statistics...")
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

        # G. Forecasts -- unchanged simple placeholder, same as load_data.py.
        print("Seeding Predictions...")
        for y, m in [(2024, 10), (2024, 11), (2024, 12)]:
            for dist_name, d_id in db_districts.items():
                for cat_name, c_id in db_categories.items():
                    pred_count = random.randint(5, 45) if dist_name == "Bengaluru City" else random.randint(1, 10)
                    session.add(CrimeForecast(
                        district_id=d_id, year=y, month=m, category_id=c_id,
                        predicted_count=pred_count, confidence=round(random.uniform(0.75, 0.94), 2),
                    ))
        session.commit()

        print(f"Done. Seeded {len(bulk_firs)} FIRs (full dataset) across {len(db_districts)} districts, "
              f"with sampled child-record detail on {len(bulk_firs) // SAMPLE_CHILD_RECORDS_EVERY_N} cases.")

    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database_from_filestore()
