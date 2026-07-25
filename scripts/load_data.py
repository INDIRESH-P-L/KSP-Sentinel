import os
import sys
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import text

# Add backend app directory to path to import models
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from backend.app.database.models import (
    Base, District, Taluk, PoliceStation, CrimeCategory, CrimeSubcategory,
    FIR, Victim, Accused, Arrest, Conviction, Investigation, ChargeSheet,
    Officer, MonthlyCrimeReview, YearlyCrimeReview, CrimeStatistic,
    CrimeEmbedding, CrimeCluster, CrimeForecast, CrimeRiskScore,
    CrimeAlert, CrimeNetwork, CrimeSimilarity, PatrolRoute, CrimeHotspot,
    fir_accused
)
from backend.app.database.session import engine, SessionLocal

# Restructured directories
RAW_FIR_PATH = "datasets/raw/fir/FIR_Details_Data.csv"
CLEANED_CENSUS_PATH = "datasets/cleaned/karnataka_census_2011.csv"

# Mapping from FIR District_Name to 2011 Census Name
CENSUS_DISTRICT_MAP = {
    "Bagalkot": "Bagalkot",
    "Ballari": "Bellary",
    "Belagavi City": "Belgaum",
    "Belagavi Dist": "Belgaum",
    "Bengaluru City": "Bangalore",
    "Bengaluru Dist": "Bangalore",
    "Bengaluru Urban": "Bangalore",
    "Bengaluru Rural": "Bangalore Rural",
    "Bidar": "Bidar",
    "Chamarajanagar": "Chamarajanagar",
    "Chickballapura": "Chikkaballapura",
    "Chikkamagaluru": "Chikmagalur",
    "Chitradurga": "Chitradurga",
    "CID": "Bangalore",
    "Coastal Security Police": "Udupi",
    "Dakshina Kannada": "Dakshina Kannada",
    "Davanagere": "Davanagere",
    "Dharwad": "Dharwad",
    "Gadag": "Gadag",
    "Hassan": "Hassan",
    "Haveri": "Haveri",
    "Hubballi Dharwad City": "Dharwad",
    "ISD Bengaluru": "Bangalore",
    "K.G.F": "Kolar",
    "Kalaburagi": "Gulbarga",
    "Kalaburagi City": "Gulbarga",
    "Karnataka Railways": "Bangalore",
    "Kodagu": "Kodagu",
    "Kolar": "Kolar",
    "Koppal": "Koppal",
    "Mandya": "Mandya",
    "Mangaluru City": "Dakshina Kannada",
    "Mysuru City": "Mysore",
    "Mysuru Dist": "Mysore",
    "Raichur": "Raichur",
    "Ramanagara": "Ramanagara",
    "Shivamogga": "Shimoga",
    "Tumakuru": "Tumkur",
    "Udupi": "Udupi",
    "Uttara Kannada": "Uttara Kannada",
    "Vijayanagara": "Bellary",
    "Vijayapur": "Bijapur",
    "Yadgir": "Yadgir"
}

DISTRICT_COORDS = {
    "Bagalkot": (16.1817, 75.6958),
    "Ballari": (15.1394, 76.9214),
    "Belagavi City": (15.8524, 74.5084),
    "Belagavi Dist": (15.8524, 74.5084),
    "Bengaluru City": (12.9778, 77.5714),
    "Bengaluru Dist": (12.9716, 77.5946),
    "Bengaluru Urban": (12.9716, 77.5946),
    "Bengaluru Rural": (13.0970, 77.3878),
    "Bidar": (17.9104, 77.5199),
    "Chamarajanagar": (11.9261, 76.9402),
    "Chickballapura": (13.4354, 77.7244),
    "Chikkamagaluru": (13.3180, 75.7760),
    "Chitradurga": (14.2251, 76.3980),
    "CID": (12.9778, 77.5714),
    "Coastal Security Police": (13.3409, 74.7421),
    "Dakshina Kannada": (12.8596, 74.8436),
    "Davanagere": (14.4644, 75.9218),
    "Dharwad": (15.4589, 75.0078),
    "Gadag": (15.4320, 75.6425),
    "Hassan": (13.0072, 76.1026),
    "Haveri": (14.7964, 75.4027),
    "Hubballi Dharwad City": (15.3524, 75.1384),
    "ISD Bengaluru": (12.9778, 77.5714),
    "K.G.F": (13.1368, 78.1292),
    "Kalaburagi": (17.3304, 76.8378),
    "Kalaburagi City": (17.3204, 76.8278),
    "Karnataka Railways": (12.9778, 77.5714),
    "Kodagu": (12.4244, 75.7380),
    "Kolar": (13.1368, 78.1292),
    "Koppal": (15.3468, 76.1553),
    "Mandya": (12.5218, 76.8951),
    "Mangaluru City": (12.8596, 74.8436),
    "Mysuru City": (12.3086, 76.6508),
    "Mysuru Dist": (12.3086, 76.6508),
    "Raichur": (16.2120, 77.3556),
    "Ramanagara": (12.7150, 77.2810),
    "Shivamogga": (13.9299, 75.5681),
    "Tumakuru": (13.3409, 77.1006),
    "Udupi": (13.3409, 74.7421),
    "Uttara Kannada": (14.8085, 74.1304),
    "Vijayanagara": (15.1394, 76.9214),
    "Vijayapur": (16.8302, 75.7100),
    "Yadgir": (16.7686, 77.1377)
}

ACCUSED_NAMES = ["Ramesh", "Suresh", "Manjunath", "Venkatesh", "Anand", "Vijay", "Kumar", "Girish", "Satish", "Shiva", "Rajesh", "Naveen", "Prakash", "Srinivas", "Kiran"]
OFFICERS = ["G.H.KUPPI (PSI)", "R S BIRADAR (PI)", "M.S.PATIL (PSI)", "A.K.NAIK (PI)", "S.B.DEVAR (PSI)"]

def load_real_census_data():
    print(f"Reading census data: {CLEANED_CENSUS_PATH}...")
    if not os.path.exists(CLEANED_CENSUS_PATH):
        # Census XLSX source (2011-IndiaStateDistSbDistTwnWrd-0000.xlsx via
        # scripts/extract_karnataka_census.py) isn't bundled in the repo -- every
        # per-district field this feeds has a documented literal fallback below
        # (pop=1000000, urb_rate=35.0, etc.), so skipping it degrades demographics
        # to defaults rather than blocking the FIR/crime-data seed entirely.
        print(f"  Not found -- proceeding without real census demographics "
              f"(districts will use default population/rate estimates).")
        return {}, []
    census_df = pd.read_csv(CLEANED_CENSUS_PATH)
    
    # Clean string names
    census_df['Name'] = census_df['Name'].astype(str).str.strip()
    
    # Extract districts
    dist_total = census_df[(census_df['Level'] == 'DISTRICT') & (census_df['TRU'] == 'Total')]
    dist_urban = census_df[(census_df['Level'] == 'DISTRICT') & (census_df['TRU'] == 'Urban')]
    
    # Store demographics
    demographics = {}
    for _, row in dist_total.iterrows():
        name = row['Name']
        # Find urban pop
        urb_match = dist_urban[dist_urban['Name'] == name]
        urb_pop = int(urb_match.iloc[0]['TOT_P']) if not urb_match.empty else 0
        
        tot_p = int(row['TOT_P'])
        tot_lit = int(row['P_LIT'])
        tot_work = int(row['TOT_WORK_P'])
        tot_non_work = int(row['NON_WORK_P'])
        
        urbanization_rate = round((urb_pop / tot_p) * 100.0, 2) if tot_p > 0 else 30.0
        literacy_rate = round((tot_lit / tot_p) * 100.0, 2) if tot_p > 0 else 75.0
        unemployment_rate = round((tot_non_work / tot_p) * 100.0, 2) if tot_p > 0 else 5.0
        poverty_rate = round(random.uniform(8.0, 22.0), 2)
        
        demographics[name] = {
            "population": tot_p,
            "urbanization_rate": urbanization_rate,
            "literacy_rate": literacy_rate,
            "unemployment_rate": unemployment_rate,
            "poverty_rate": poverty_rate,
            "male": int(row['TOT_M']),
            "female": int(row['TOT_F']),
            "urban": urb_pop,
            "rural": tot_p - urb_pop,
            "district_code": row['District']
        }
    
    # Extract taluks (subdistricts)
    taluks = []
    subdist_df = census_df[(census_df['Level'] == 'SUB-DISTRICT') & (census_df['TRU'] == 'Total')]
    for _, row in subdist_df.iterrows():
        taluks.append({
            "name": row['Name'],
            "district_code": row['District']
        })
        
    return demographics, taluks

def generate_csv_files():
    print("Generating derived raw CSV files in reorganized layout...")
    os.makedirs("datasets/raw/census", exist_ok=True)
    os.makedirs("datasets/raw/police", exist_ok=True)
    os.makedirs("datasets/raw/fir", exist_ok=True)
    
    # Write a quick summary of police stations
    print("Reading FIR to extract stations...")
    cols = ['District_Name', 'UnitName', 'Latitude', 'Longitude']
    df_ps = pd.read_csv(RAW_FIR_PATH, usecols=cols)
    df_ps['District_Name'] = df_ps['District_Name'].astype(str).str.strip()
    df_ps['UnitName'] = df_ps['UnitName'].astype(str).str.strip()
    
    stations = df_ps[['District_Name', 'UnitName']].drop_duplicates().sort_values(['District_Name', 'UnitName'])
    stations.to_csv("datasets/raw/police/police_stations.csv", index=False)
    print("Exported police_stations.csv.")

def seed_database():
    is_postgres = "postgresql" in engine.url.drivername
    if is_postgres:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()

    print("Recreating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # 1. Load Census Data
    demographics, taluks_data = load_real_census_data()

    # 2. Read FIR Dataset
    print(f"Reading FIR dataset: {RAW_FIR_PATH}...")
    # Load columns needed to save memory
    cols = [
        'District_Name', 'UnitName', 'FIR_YEAR', 'FIR_MONTH', 'FIR_Day',
        'FIR Type', 'FIR_Stage', 'Complaint_Mode', 'CrimeGroup_Name',
        'CrimeHead_Name', 'Latitude', 'Longitude', 'ActSection', 'IOName',
        'Place of Offence', 'Male', 'Female', 'Boy', 'Girl', 'VICTIM COUNT',
        'Accused Count', 'Arrested Count\tNo.', 'Accused_ChargeSheeted Count',
        'Conviction Count'
    ]
    df = pd.read_csv(RAW_FIR_PATH, usecols=cols)
    print(f"Loaded {len(df)} rows.")

    # Clean columns
    df['District_Name'] = df['District_Name'].astype(str).str.strip()
    df['UnitName'] = df['UnitName'].astype(str).str.strip()
    df['CrimeGroup_Name'] = df['CrimeGroup_Name'].astype(str).str.strip()
    df['CrimeHead_Name'] = df['CrimeHead_Name'].astype(str).str.strip()
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    
    session = SessionLocal()
    
    try:
        # Helper to construct Point/Polygon geometries
        def get_point_geom(lat, lng):
            if is_postgres:
                return f"SRID=4326;POINT({lng} {lat})"
            return f"POINT({lng} {lat})"
            
        def get_multipolygon_geom(lat, lng):
            if is_postgres:
                return f"SRID=4326;MULTIPOLYGON((({lng-0.1} {lat-0.1}, {lng+0.1} {lat-0.1}, {lng+0.1} {lat+0.1}, {lng-0.1} {lat+0.1}, {lng-0.1} {lat-0.1})))"
            return f"MULTIPOLYGON((({lng-0.1} {lat-0.1}, {lng+0.1} {lat-0.1}, {lng+0.1} {lat+0.1}, {lng-0.1} {lat+0.1}, {lng-0.1} {lat-0.1})))"

        # A. Seed Districts
        print("Seeding Districts and Taluks...")
        db_districts = {}
        unique_fir_dists = df['District_Name'].unique()
        
        for dist_name in unique_fir_dists:
            coords = DISTRICT_COORDS.get(dist_name, (12.9716, 77.5946))
            
            # Map to census name
            census_name = CENSUS_DISTRICT_MAP.get(dist_name)
            demo = demographics.get(census_name)
            
            if demo:
                pop = demo['population']
                urb_rate = demo['urbanization_rate']
                lit_rate = demo['literacy_rate']
                unemp_rate = demo['unemployment_rate']
                pov_rate = demo['poverty_rate']
                dist_code = demo['district_code']
            else:
                pop = 1000000
                urb_rate = 35.0
                lit_rate = 75.0
                unemp_rate = 5.0
                pov_rate = 15.0
                dist_code = None
                
            risk_score = int(urb_rate * 0.4 + unemp_rate * 4.0 + pov_rate * 1.5)
            risk_score = min(95, max(20, risk_score))
            
            d_obj = District(
                name=dist_name,
                population=pop,
                risk_score=risk_score,
                risk_factors=f"Risk based on urbanization {urb_rate}% and unemp {unemp_rate}%.",
                urbanization_rate=urb_rate,
                literacy_rate=lit_rate,
                unemployment_rate=unemp_rate,
                poverty_rate=pov_rate,
                geom=get_multipolygon_geom(coords[0], coords[1])
            )
            session.add(d_obj)
            session.flush()
            db_districts[dist_name] = d_obj.id
            
            # Seed risk score
            risk = CrimeRiskScore(
                district_id=d_obj.id,
                score=risk_score,
                safety_index=round(100.0 - risk_score * 0.8, 1),
                population_density=round(pop / 4500.0, 2)
            )
            session.add(risk)

            # Seed taluks for this district
            if dist_code:
                matched_taluks = [t['name'] for t in taluks_data if t['district_code'] == dist_code]
                for t_name in matched_taluks[:4]: # Seed top 4 taluks to keep it fast
                    tal = Taluk(
                        district_id=d_obj.id,
                        name=t_name,
                        geom=get_multipolygon_geom(coords[0] + random.uniform(-0.04, 0.04), coords[1] + random.uniform(-0.04, 0.04))
                    )
                    session.add(tal)

        # B. Seed Police Stations
        print("Seeding Police Stations...")
        db_stations = {}
        
        # Calculate average coordinates for stations
        station_avg_coords = df.groupby(['District_Name', 'UnitName'])[['Latitude', 'Longitude']].mean().reset_index()
        
        for _, row in station_avg_coords.iterrows():
            d_name = row['District_Name']
            s_name = row['UnitName']
            
            d_coords = DISTRICT_COORDS.get(d_name, (12.9716, 77.5946))
            lat = row['Latitude'] if not pd.isna(row['Latitude']) and row['Latitude'] > 0 else d_coords[0] + random.uniform(-0.02, 0.02)
            lng = row['Longitude'] if not pd.isna(row['Longitude']) and row['Longitude'] > 0 else d_coords[1] + random.uniform(-0.02, 0.02)
            
            dist_id = db_districts[d_name]
            station = PoliceStation(
                name=s_name,
                district_id=dist_id,
                latitude=lat,
                longitude=lng,
                geom=get_point_geom(lat, lng)
            )
            session.add(station)
            session.flush()
            db_stations[(d_name, s_name)] = station.id
            
            # Seed 2 Officers
            for idx, rank in enumerate(["Inspector", "Sub-Inspector"]):
                badge = f"KSP-{station.id}-{idx:02d}"
                off = Officer(
                    name=f"Officer {badge}",
                    badge_number=badge,
                    rank=rank,
                    station_id=station.id,
                    status="ACTIVE"
                )
                session.add(off)

        # C. Seed Categories & Subcategories
        print("Seeding Crime Categories & Subcategories...")
        db_categories = {}
        db_subcategories = {}
        
        cats = df['CrimeGroup_Name'].dropna().unique()
        for cat_name in cats:
            cat = CrimeCategory(name=cat_name, major_head=cat_name, minor_head="General")
            session.add(cat)
            session.flush()
            db_categories[cat_name] = cat.id
            
        subcats = df.groupby(['CrimeGroup_Name', 'CrimeHead_Name']).size().reset_index()
        for _, row in subcats.iterrows():
            c_name = row['CrimeGroup_Name']
            sub_name = row['CrimeHead_Name']
            cat_id = db_categories[c_name]
            
            sub = CrimeSubcategory(name=sub_name, category_id=cat_id)
            session.add(sub)
            session.flush()
            db_subcategories[(c_name, sub_name)] = sub.id

        # Slice the dataframe to get a sample, or use step=1 to load all rows
        step = int(os.environ.get("FIR_SAMPLE_STEP", "1"))
        df_sample = df.iloc[::step]
        print(f"Seeding {len(df_sample)} FIRs using step-slice of {step}...")
        
        # Pre-create some accused names
        ACCUSED_POOL = []
        for idx in range(15):
            ACCUSED_POOL.append({
                "name": f"Suspect {ACCUSED_NAMES[idx % len(ACCUSED_NAMES)]} #{idx}",
                "age": random.randint(19, 50),
                "gender": "Male" if random.random() > 0.1 else "Female"
            })
            
        fir_counter = 1
        
        bulk_firs = []
        bulk_victims = []
        bulk_accused = []
        bulk_arrests = []
        bulk_convictions = []
        bulk_chargesheets = []
        bulk_investigations = []
        bulk_embeddings = []
        
        # Mapping FIR ID to list of accused IDs
        fir_accused_links = []
        
        accused_counter = 1
        
        for _, row in df_sample.iterrows():
            d_name = row['District_Name']
            s_name = row['UnitName']
            cat_name = row['CrimeGroup_Name']
            sub_name = row['CrimeHead_Name']
            
            # Map foreign keys
            station_id = db_stations.get((d_name, s_name))
            subcat_id = db_subcategories.get((cat_name, sub_name))
            
            if not station_id or not subcat_id:
                continue
                
            # Date reported
            year = int(row['FIR_YEAR']) if not pd.isna(row['FIR_YEAR']) else 2024
            month = int(row['FIR_MONTH']) if not pd.isna(row['FIR_MONTH']) and row['FIR_MONTH'] > 0 and row['FIR_MONTH'] <= 12 else random.randint(1, 12)
            try:
                day = int(row['FIR_Day']) if not pd.isna(row['FIR_Day']) and row['FIR_Day'] > 0 and row['FIR_Day'] <= 28 else random.randint(1, 28)
                dt = datetime(year, month, day)
            except Exception:
                dt = datetime(year, month, 1)
                
            occurred_dt = dt - timedelta(hours=random.randint(1, 48))
            
            # FIR Number
            fir_number = f"KSP/{d_name[:3].upper()}/{year}/{fir_counter:05d}"
            
            # Status mapping
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
            
            # Add to bulk list
            fir_dict = {
                "id": fir_counter,
                "fir_number": fir_number,
                "police_station_id": station_id,
                "subcategory_id": subcat_id,
                "date_reported": dt,
                "date_occurred": occurred_dt,
                "description": desc,
                "status": status,
                "latitude": lat,
                "longitude": lng,
                "geom": get_point_geom(lat, lng)
            }
            bulk_firs.append(fir_dict)
            
            # Seeding Victims
            victim_count = int(row['VICTIM COUNT']) if not pd.isna(row['VICTIM COUNT']) else 0
            if victim_count > 0:
                for v_idx in range(min(5, victim_count)): # Caps at 5 per FIR
                    # match gender ratio
                    if v_idx == 0 and int(row['Female']) > 0:
                        gender = "Female"
                        cat = "WOMAN"
                    elif v_idx == 1 and int(row['Girl']) > 0:
                        gender = "Female"
                        cat = "CHILD"
                    elif v_idx == 2 and int(row['Boy']) > 0:
                        gender = "Male"
                        cat = "CHILD"
                    else:
                        gender = "Male"
                        cat = "GENERAL"
                        
                    bulk_victims.append({
                        "fir_id": fir_counter,
                        "name": f"Victim #{fir_counter}-{v_idx}",
                        "age": random.randint(10, 70),
                        "gender": gender,
                        "category": cat,
                        "injured": 1 if status in ['CHARGE_SHEETED', 'CLOSED'] else 0,
                        "dead": 1 if "Murder" in sub_name or "Attempted Murder" in sub_name else 0
                    })
            
            # Seeding Accused
            acc_count = int(row['Accused Count']) if not pd.isna(row['Accused Count']) else 0
            acc_links = []
            if acc_count > 0:
                for a_idx in range(min(4, acc_count)):
                    acc_chosen = random.choice(ACCUSED_POOL)
                    repeat_offender = random.random() > 0.8
                    history_sheet = repeat_offender and random.random() > 0.6
                    gang = "Local Gang B" if repeat_offender and random.random() > 0.5 else None
                    
                    acc_dict = {
                        "id": accused_counter,
                        "name": f"{acc_chosen['name']}-{accused_counter}",
                        "age": acc_chosen['age'],
                        "gender": acc_chosen['gender'],
                        "repeat_offender": repeat_offender,
                        "history_sheet": history_sheet,
                        "gang": gang,
                        "prior_offenses_count": random.randint(1, 5) if repeat_offender else 0,
                        "status": "ACTIVE"
                    }
                    bulk_accused.append(acc_dict)
                    acc_links.append(accused_counter)
                    fir_accused_links.append((fir_counter, accused_counter))
                    
                    # Seeding Arrests
                    arrest_count = int(row['Arrested Count\tNo.']) if not pd.isna(row['Arrested Count\tNo.']) else 0
                    if arrest_count > a_idx:
                        bulk_arrests.append({
                            "fir_id": fir_counter,
                            "accused_id": accused_counter,
                            "arrest_date": dt + timedelta(days=random.randint(1, 10)),
                            "status": "ARRESTED",
                            "officer": random.choice(OFFICERS),
                            "court": "JMFC Court"
                        })
                        
                    # Seeding Convictions
                    conv_count = int(row['Conviction Count']) if not pd.isna(row['Conviction Count']) else 0
                    if conv_count > a_idx and status == 'CLOSED':
                        bulk_convictions.append({
                            "fir_id": fir_counter,
                            "accused_id": accused_counter,
                            "conviction_date": dt + timedelta(days=random.randint(90, 200)),
                            "sentence_months": random.choice([6, 12, 24, 36]),
                            "status": "CONVICTED",
                            "court": "District Sessions Court",
                            "sentence": "Rigorous Imprisonment",
                            "years": float(random.choice([0.5, 1.0, 2.0])),
                            "fine": float(random.choice([1000, 2000]))
                        })
                    accused_counter += 1
            
            # Seeding ChargeSheet
            cs_count = int(row['Accused_ChargeSheeted Count']) if not pd.isna(row['Accused_ChargeSheeted Count']) else 0
            if cs_count > 0:
                bulk_chargesheets.append({
                    "fir_id": fir_counter,
                    "filed_date": dt + timedelta(days=25),
                    "sections": str(row['ActSection'])[:190] if not pd.isna(row['ActSection']) else "IPC 1860 U/s: 379",
                    "status": "FILED"
                })
                
            # Seeding Investigation
            io_name = str(row['IOName']) if not pd.isna(row['IOName']) else random.choice(OFFICERS)
            bulk_investigations.append({
                "fir_id": fir_counter,
                "assigned_officer": io_name,
                "status": "COMPLETED" if status in ['CLOSED', 'CHARGE_SHEETED'] else "ONGOING",
                "last_updated": dt + timedelta(days=2)
            })
            
            # Seeding mock embeddings (Tf-Idf sizes 384)
            mock_emb = [random.uniform(-0.1, 0.1) for _ in range(384)]
            bulk_embeddings.append({
                "fir_id": fir_counter,
                "embedding": str(mock_emb) if not is_postgres else mock_emb
            })
            
            fir_counter += 1

        # Bulk inserts to database
        print("Inserting FIRs into database...")
        session.bulk_insert_mappings(FIR, bulk_firs)
        session.flush()
        
        print("Inserting Victims into database...")
        session.bulk_insert_mappings(Victim, bulk_victims)
        
        print("Inserting Accused into database...")
        session.bulk_insert_mappings(Accused, bulk_accused)
        session.flush()
        
        # Link Many-to-Many accused list mapping
        print("Linking FIR cases to Accused...")
        insert_links = [{"fir_id": f, "accused_id": a} for f, a in fir_accused_links]
        if insert_links:
            session.execute(fir_accused.insert(), insert_links)
            
        print("Inserting Arrests, Convictions, Investigations, ChargeSheets, Embeddings...")
        session.bulk_insert_mappings(Arrest, bulk_arrests)
        session.bulk_insert_mappings(Conviction, bulk_convictions)
        session.bulk_insert_mappings(Investigation, bulk_investigations)
        session.bulk_insert_mappings(ChargeSheet, bulk_chargesheets)
        session.bulk_insert_mappings(CrimeEmbedding, bulk_embeddings)

        # E. Seed summarized Yearly Crime Reviews (Step 2 - from ENTIRE dataset)
        print("Calculating and seeding Yearly Crime Reviews...")
        yearly_counts = df.groupby(['FIR_YEAR', 'CrimeGroup_Name']).size().reset_index(name='cnt')
        for _, row in yearly_counts.iterrows():
            y = int(row['FIR_YEAR'])
            cat_name = row['CrimeGroup_Name']
            cnt = int(row['cnt'])
            
            # calculate decadal/yearly increase percentage
            prev = yearly_counts[(yearly_counts['FIR_YEAR'] == y - 1) & (yearly_counts['CrimeGroup_Name'] == cat_name)]
            inc = round(((cnt - prev.iloc[0]['cnt']) / prev.iloc[0]['cnt']) * 100.0, 2) if not prev.empty else round(random.uniform(-5.0, 10.0), 2)
            
            session.add(YearlyCrimeReview(
                year=y,
                head_of_crime=cat_name,
                count=cnt,
                increase_percentage=inc
            ))

        # F. Seed aggregated Crime Statistics (Step 12 - from ENTIRE dataset)
        print("Calculating and seeding monthly Crime Statistics...")
        stat_counts = df.groupby(['District_Name', 'FIR_YEAR', 'FIR_MONTH', 'CrimeGroup_Name']).size().reset_index(name='cnt')
        
        # To make it fast, we only insert stats for years 2023, 2024 (recent)
        stat_counts_filtered = stat_counts[stat_counts['FIR_YEAR'].isin([2023, 2024])]
        bulk_stats = []
        for _, row in stat_counts_filtered.iterrows():
            d_name = row['District_Name']
            y = int(row['FIR_YEAR'])
            m = int(row['FIR_MONTH'])
            cat_name = row['CrimeGroup_Name']
            cnt = int(row['cnt'])
            
            d_id = db_districts.get(d_name)
            c_id = db_categories.get(cat_name)
            
            if d_id and c_id:
                # get population
                census_name = CENSUS_DISTRICT_MAP.get(d_name)
                pop = demographics.get(census_name, {}).get("population", 1000000)
                rate = round((cnt / pop) * 100000.0, 2)
                
                bulk_stats.append({
                    "district_id": d_id,
                    "year": y,
                    "month": m,
                    "category_id": c_id,
                    "total_count": cnt,
                    "rate_per_lakh": rate
                })
        session.bulk_insert_mappings(CrimeStatistic, bulk_stats)

        # G. Seed predictions/forecasts for next 3 months (Step 12)
        print("Seeding Predictions...")
        for y, m in [(2024, 10), (2024, 11), (2024, 12)]:
            for dist_name, d_id in db_districts.items():
                for cat_name, c_id in db_categories.items():
                    pred_count = random.randint(5, 45) if dist_name == "Bengaluru City" else random.randint(1, 10)
                    session.add(CrimeForecast(
                        district_id=d_id,
                        year=y,
                        month=m,
                        category_id=c_id,
                        predicted_count=pred_count,
                        confidence=round(random.uniform(0.75, 0.94), 2)
                    ))

        # H. Seed Hotspots, Patrol Routes, Alerts, Networks, Case Similarity
        print("Seeding Hotspots and Patrol Routes...")
        for d_name, d_id in db_districts.items():
            stations_in_dist = [s for (d, s), sid in db_stations.items() if d == d_name]
            coords = DISTRICT_COORDS.get(d_name, (12.9716, 77.5946))
            
            for s_name in stations_in_dist[:2]: # seed top 2 stations per district
                sid = db_stations[(d_name, s_name)]
                
                # Hotspot
                session.add(CrimeHotspot(
                    police_station_id=sid,
                    latitude=coords[0] + random.uniform(-0.01, 0.01),
                    longitude=coords[1] + random.uniform(-0.01, 0.01),
                    intensity=round(random.uniform(0.4, 0.9), 2),
                    prediction_date=datetime.utcnow().date() + timedelta(days=random.randint(1, 10))
                ))
                
                # Route
                route_geom = f"LINESTRING({coords[1]} {coords[0]}, {coords[1]+0.01} {coords[0]+0.01})"
                if is_postgres:
                    route_geom = f"SRID=4326;{route_geom}"
                session.add(PatrolRoute(
                    name=f"Patrol Route for {s_name}",
                    description=f"Patrol route sweeps around station center.",
                    geom=route_geom
                ))
                
        # Seed active Alerts
        session.add(CrimeAlert(district_id=1, type="SPATIAL_SPIKE", message="High surge in property/vehicular thefts registered.", severity="CRITICAL"))
        session.add(CrimeAlert(district_id=2, type="CYBER_FRAUD", message="Financial fraud activity detected near transit highways.", severity="WARNING"))
        
        # Seed Accused Network links
        session.add(CrimeNetwork(source_accused_id=1, target_accused_id=2, connection_strength=2.5, common_firs_count=2))
        session.add(CrimeNetwork(source_accused_id=2, target_accused_id=3, connection_strength=1.5, common_firs_count=1))
        
        # Seed Case Similarity
        session.add(CrimeSimilarity(fir_id_1=1, fir_id_2=2, similarity_score=0.88))
        session.add(CrimeSimilarity(fir_id_1=2, fir_id_2=3, similarity_score=0.71))

        # Seed Clusters
        session.add(CrimeCluster(name="Bengaluru Zone", description="Heavy metropolitan cluster for cyber crime.", district_ids="1,5,6", count=450))

        session.commit()
        print("Database successfully seeded with Karnataka data warehouse records.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    generate_csv_files()
    seed_database()
