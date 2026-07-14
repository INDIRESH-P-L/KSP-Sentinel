import os
import csv
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys

# Add backend app directory to path to import models
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from backend.app.database.models import (
    Base, District, PoliceStation, CrimeCategory, CrimeSubcategory,
    FIR, Victim, Accused, Arrest, Conviction, Investigation,
    CrimePrediction, CrimeHotspot
)
from backend.app.database.session import engine, SessionLocal

# Ensure directories exist
os.makedirs("datasets/raw", exist_ok=True)

# 1. Define Seed Data Structure
DISTRICTS_DATA = [
    {"name": "Bengaluru Urban", "population": 8443675, "risk_score": 88, "risk_factors": "High population density, tech hub."},
    {"name": "Bengaluru Rural", "population": 990923, "risk_score": 62, "risk_factors": "Highway transport hubs."},
    {"name": "Ballari", "population": 1000000, "risk_score": 55, "risk_factors": "Mining belt."},
    {"name": "Bagalkot", "population": 900000, "risk_score": 45, "risk_factors": "Agrarian disputes."},
    {"name": "Belagavi", "population": 4779661, "risk_score": 50, "risk_factors": "Border district."},
    {"name": "Bengaluru City", "population": 8443675, "risk_score": 88, "risk_factors": "Urban metropolis."},
    {"name": "Bidar", "population": 600000, "risk_score": 42, "risk_factors": "Border zone."},
    {"name": "Chamarajanagar", "population": 500000, "risk_score": 40, "risk_factors": "Rural district."},
    {"name": "Chikkaballapur", "population": 430000, "risk_score": 38, "risk_factors": "Peri-urban."},
    {"name": "Chikkamagaluru", "population": 600000, "risk_score": 36, "risk_factors": "Hill terrain."},
    {"name": "Chitradurga", "population": 1000000, "risk_score": 44, "risk_factors": "Transit corridors."},
    {"name": "Davanagere", "population": 1000000, "risk_score": 46, "risk_factors": "Agriculture and trade."},
    {"name": "Dharwad", "population": 1847023, "risk_score": 58, "risk_factors": "Commercial hub."},
    {"name": "Gadag", "population": 550000, "risk_score": 34, "risk_factors": "Rural clusters."},
    {"name": "Hassan", "population": 1300000, "risk_score": 39, "risk_factors": "Tourism and agriculture."},
    {"name": "Haveri", "population": 600000, "risk_score": 35, "risk_factors": "Agrarian."},
    {"name": "Kalaburagi", "population": 2566326, "risk_score": 50, "risk_factors": "Arid zone."},
    {"name": "Kodagu", "population": 250000, "risk_score": 33, "risk_factors": "Tourism and hills."},
    {"name": "Kolar", "population": 1200000, "risk_score": 37, "risk_factors": "Mining and peri-urban."},
    {"name": "Koppal", "population": 600000, "risk_score": 34, "risk_factors": "Rural."},
    {"name": "Mangaluru", "population": 2089627, "risk_score": 67, "risk_factors": "Port and coast."},
    {"name": "Mysuru", "population": 3001127, "risk_score": 54, "risk_factors": "Tourism center."},
    {"name": "Mandya", "population": 1000000, "risk_score": 36, "risk_factors": "Agriculture."},
    {"name": "Raichur", "population": 800000, "risk_score": 41, "risk_factors": "Border and irrigation."},
    {"name": "Ramanagara", "population": 900000, "risk_score": 39, "risk_factors": "Industrial belts."},
    {"name": "Shivamogga", "population": 1200000, "risk_score": 43, "risk_factors": "Agriculture and transit."},
    {"name": "Tumakuru", "population": 1100000, "risk_score": 47, "risk_factors": "Industrial growth."},
    {"name": "Udupi", "population": 900000, "risk_score": 42, "risk_factors": "Coastal and tourism."},
    {"name": "Uttara Kannada", "population": 800000, "risk_score": 41, "risk_factors": "Coastal and forested."},
    {"name": "Vijayapura", "population": 950000, "risk_score": 40, "risk_factors": "Border region."},
    {"name": "Yadgir", "population": 400000, "risk_score": 33, "risk_factors": "Rural development."}
]

STATIONS_DATA = {}
for d in DISTRICTS_DATA:
    name = d["name"]
    # Create a default central police station for each district
    STATIONS_DATA[name] = [
        {"name": f"{name} Central PS", "lat": 0.0, "lng": 0.0}
    ]

CATEGORIES_DATA = {
    "Theft & Burglary": ["House Break-in", "Vehicle Theft", "Chain Snatching", "Pickpocketing"],
    "Crimes Against Persons": ["Assault", "Attempted Murder", "Murder", "Kidnapping"],
    "Cyber Crime": ["Phishing Fraud", "Identity Theft", "Social Media Abuse", "Ransomware Attack"],
    "Narcotics": ["NDPS Possession", "Drug Trafficking", "Local Distribution"],
    "Economic Offenses": ["Corporate Embezzlement", "Land Scam", "Ponzi Scheme Fraud"],
    "Women & Child Safety": ["Domestic Violence", "Dowry Harassment", "POCSO Act Violations"]
}

VICTIMS_NAMES = ["Ramesh Kumar", "Sita Gowda", "Abdul Rahim", "Margaret D'Souza", "Vijay Patil", "Ananya Hegde", "Priya Nayak", "Mohammad Ali", "Sunitha R.", "Kiran K."]
ACCUSED_NAMES = ["Raghu 'Dada' Gowda", "Shailesh 'Spinner' Kumar", "Vikram 'Vicky' Singh", "Suresh 'Cyber' Murthy", "Manju 'Loco' Raju", "Pappu Yadav", "Shekhar Shetty", "Imran Khan", "Anthony Gonsalves", "Ravi Patil"]
OFFICERS = ["ACP Raghavan", "Inspector Girish", "Sub-Inspector Kavitha", "Inspector Harish", "Inspector Sandeep", "Sub-Inspector Smitha"]

def generate_csv_files():
    # 1. Population CSV
    with open("datasets/raw/population.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["district", "population"])
        for d in DISTRICTS_DATA:
            writer.writerow([d["name"], d["population"]])
            
    # 2. Districts CSV
    with open("datasets/raw/districts.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "population", "risk_score", "risk_factors"])
        for d in DISTRICTS_DATA:
            writer.writerow([d["name"], d["population"], d["risk_score"], d["risk_factors"]])
            
    # 3. Police Stations CSV
    with open("datasets/raw/police_stations.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "district", "latitude", "longitude"])
        for dist, stations in STATIONS_DATA.items():
            for s in stations:
                writer.writerow([s["name"], dist, s["lat"], s["lng"]])
                
    # 4. Crime Categories & Subcategories CSV
    with open("datasets/raw/crime_categories.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name"])
        for cat in CATEGORIES_DATA.keys():
            writer.writerow([cat])
            
    with open("datasets/raw/crime_subcategories.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "category"])
        for cat, subs in CATEGORIES_DATA.items():
            for sub in subs:
                writer.writerow([sub, cat])

    # Generate FIRs & Details
    firs = []
    victims = []
    accused = []
    arrests = []
    convictions = []
    
    # Pre-generate Accused details to make it easy to create repeat offenders
    accused_pool = []
    for idx, name in enumerate(ACCUSED_NAMES):
        acc_id = idx + 1
        age = random.randint(20, 50)
        gender = "Male" if random.random() > 0.1 else "Female"
        priors = random.randint(0, 5)
        status = "ACTIVE" if priors > 0 else "INACTIVE"
        accused_pool.append({
            "id": acc_id,
            "name": name,
            "age": age,
            "gender": gender,
            "prior_offenses_count": priors,
            "status": status
        })
        
    # Write accused CSV
    with open("datasets/raw/accused.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "age", "gender", "prior_offenses_count", "status"])
        for acc in accused_pool:
            writer.writerow([acc["id"], acc["name"], acc["age"], acc["gender"], acc["prior_offenses_count"], acc["status"]])

    # Generate 250 realistic FIRs spanning 2023 to 2026
    start_date = datetime(2023, 1, 1)
    fir_counter = 1
    
    for i in range(250):
        # Determine occurrence date
        days_offset = random.randint(0, 1260)  # ~3.5 years
        occurred_dt = start_date + timedelta(days=days_offset, hours=random.randint(0, 23))
        reported_dt = occurred_dt + timedelta(hours=random.randint(1, 48))
        
        # Select district and station
        dist_choice = random.choice(DISTRICTS_DATA)
        stations = STATIONS_DATA[dist_choice["name"]]
        station_choice = random.choice(stations)
        
        # Select category & subcategory
        cat_choice = random.choice(list(CATEGORIES_DATA.keys()))
        sub_choice = random.choice(CATEGORIES_DATA[cat_choice])
        
        # FIR ID code
        fir_number = f"KSP/{dist_choice['name'][:3].upper()}/{occurred_dt.year}/{fir_counter:04d}"
        
        # FIR Status progression
        status_opts = ["REGISTERED", "INVESTIGATING", "CHARGE_SHEETED", "CLOSED"]
        # Weigh based on age of case
        if occurred_dt.year == 2023:
            status = random.choice(["CLOSED", "CHARGE_SHEETED"])
        elif occurred_dt.year == 2024:
            status = random.choice(["INVESTIGATING", "CHARGE_SHEETED", "CLOSED"])
        else:
            status = random.choice(["REGISTERED", "INVESTIGATING"])
            
        # Coordinates with slight random noise around station
        lat = station_choice["lat"] + random.uniform(-0.015, 0.015)
        lng = station_choice["lng"] + random.uniform(-0.015, 0.015)
        
        # Description
        desc_templates = {
            "House Break-in": f"Complainant reported that on {occurred_dt.strftime('%d-%m-%Y')} night, unknown thieves broke open the front door lock of their residence and stole gold jewelry and cash.",
            "Vehicle Theft": f"Theft of two-wheeler parked in front of building. Vehicle details: Karnataka registration, black color model. Incident happened between evening and morning hours.",
            "Chain Snatching": "Two unidentified suspects riding a motorcycle approached the victim from behind and snatched a gold chain weighing 30 grams before fleeing towards the main highway.",
            "Pickpocketing": "Victim reports loss of wallet containing cash and ID cards from pocket while boarding the city transit bus during peak hours.",
            "Phishing Fraud": "Victim received a call posing as a bank manager, shared OTP, leading to unauthorized transfer of Rs 50,000 from account.",
            "Identity Theft": "Complainant discovered a duplicate profile using their photos and name, seeking money from contacts on social messaging platforms.",
            "Domestic Violence": "Complainant alleging harassment, verbal abuse, and physical assault by husband and in-laws, seeking police protection.",
            "Dowry Harassment": "Case registered regarding demands of additional dowry in cash and property, causing severe mental distress.",
            "NDPS Possession": "Police team on patrol intercepted a suspect carrying illicit recreational substances (cannabis/ganja) in a bag, seized during spot check.",
            "Drug Trafficking": "Intelligence-led raid led to interception of commercial quantities of narcotics transported in a cargo carrier vehicle.",
            "Assault": "Complainant was assaulted and threatened by a neighbor over a parking dispute, sustaining minor injuries.",
            "Murder": "Incident of murder reported. Deceased was attacked with sharp objects by rivals. Case registered and under investigation.",
            "Attempted Murder": "Fight broke out near local food stall; suspect stabbed victim with a knife, causing severe injuries. Victim currently hospitalised."
        }
        description = desc_templates.get(sub_choice, f"Complaint registered regarding case of {sub_choice} under relevant sections of the law. Details under verification.")

        firs.append({
            "id": fir_counter,
            "fir_number": fir_number,
            "station": station_choice["name"],
            "subcategory": sub_choice,
            "date_reported": reported_dt.isoformat(),
            "date_occurred": occurred_dt.isoformat(),
            "description": description,
            "status": status,
            "latitude": lat,
            "longitude": lng
        })
        
        # Link Victim
        victim_name = random.choice(VICTIMS_NAMES)
        v_age = random.randint(18, 75)
        v_gender = random.choice(["Male", "Female"])
        v_cat = "GENERAL"
        if v_age > 60:
            v_cat = "SENIOR_CITIZEN"
        elif v_gender == "Female":
            v_cat = "WOMAN"
        elif v_age < 18:
            v_cat = "CHILD"
            
        victims.append({
            "fir_id": fir_counter,
            "name": victim_name,
            "age": v_age,
            "gender": v_gender,
            "category": v_cat
        })
        
        # Link Accused (for 80% of cases)
        if random.random() < 0.8:
            # Pick from pool (creates repeat offenders)
            acc_chosen = random.choice(accused_pool)
            
            # Record links
            arrest_dt = reported_dt + timedelta(days=random.randint(1, 15))
            
            arrests.append({
                "fir_id": fir_counter,
                "accused_id": acc_chosen["id"],
                "arrest_date": arrest_dt.isoformat(),
                "status": "ARRESTED" if status in ["CHARGE_SHEETED", "CLOSED"] else "UNDER_INQUIRY"
            })
            
            if status == "CLOSED" and random.random() > 0.3:
                conv_dt = arrest_dt + timedelta(days=random.randint(90, 360))
                convictions.append({
                    "fir_id": fir_counter,
                    "accused_id": acc_chosen["id"],
                    "conviction_date": conv_dt.isoformat(),
                    "sentence_months": random.choice([6, 12, 24, 36, 120]),
                    "status": "CONVICTED"
                })
                
        fir_counter += 1

    # Write FIR CSV
    with open("datasets/raw/fir.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "fir_number", "police_station", "subcategory", "date_reported", "date_occurred", "description", "status", "latitude", "longitude"])
        for fir in firs:
            writer.writerow([fir["id"], fir["fir_number"], fir["station"], fir["subcategory"], fir["date_reported"], fir["date_occurred"], fir["description"], fir["status"], fir["latitude"], fir["longitude"]])
            
    # Write Victims CSV
    with open("datasets/raw/victims.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["fir_id", "name", "age", "gender", "category"])
        for v in victims:
            writer.writerow([v["fir_id"], v["name"], v["age"], v["gender"], v["category"]])
            
    # Write Arrests CSV
    with open("datasets/raw/arrest.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["fir_id", "accused_id", "arrest_date", "status"])
        for a in arrests:
            writer.writerow([a["fir_id"], a["accused_id"], a["arrest_date"], a["status"]])
            
    # Write Convictions CSV
    with open("datasets/raw/conviction.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["fir_id", "accused_id", "conviction_date", "sentence_months", "status"])
        for c in convictions:
            writer.writerow([c["fir_id"], c["accused_id"], c["conviction_date"], c["sentence_months"], c["status"]])

    print("Successfully generated all mock datasets CSV files.")
    return firs, victims, accused_pool, arrests, convictions

def seed_database(firs, victims, accused_pool, arrests, convictions):
    # Initialize connection
    print("Recreating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    
    try:
        # 1. Seed Districts
        districts_map = {}
        for d_info in DISTRICTS_DATA:
            dist = District(
                name=d_info["name"],
                population=d_info["population"],
                risk_score=d_info["risk_score"],
                risk_factors=d_info["risk_factors"]
            )
            session.add(dist)
            session.flush()
            districts_map[dist.name] = dist.id
            
        # 2. Seed Police Stations
        stations_map = {}
        for dist_name, stations in STATIONS_DATA.items():
            dist_id = districts_map[dist_name]
            for s_info in stations:
                station = PoliceStation(
                    name=s_info["name"],
                    district_id=dist_id,
                    latitude=s_info["lat"],
                    longitude=s_info["lng"]
                )
                session.add(station)
                session.flush()
                stations_map[station.name] = station.id
                
        # 3. Seed Categories & Subcategories
        categories_map = {}
        subcategories_map = {}
        for cat_name, subs in CATEGORIES_DATA.items():
            cat = CrimeCategory(name=cat_name)
            session.add(cat)
            session.flush()
            categories_map[cat.name] = cat.id
            
            for sub_name in subs:
                sub = CrimeSubcategory(name=sub_name, category_id=cat.id)
                session.add(sub)
                session.flush()
                subcategories_map[sub.name] = sub.id

        # 4. Seed Accused pool
        accused_map = {}
        for acc_info in accused_pool:
            acc = Accused(
                id=acc_info["id"],
                name=acc_info["name"],
                age=acc_info["age"],
                gender=acc_info["gender"],
                prior_offenses_count=acc_info["prior_offenses_count"],
                status=acc_info["status"]
            )
            session.add(acc)
            session.flush()
            accused_map[acc.id] = acc

        # 5. Seed FIRs, Victims, Arrests, Convictions, Investigations
        firs_orm_map = {}
        for f_info in firs:
            fir = FIR(
                id=f_info["id"],
                fir_number=f_info["fir_number"],
                police_station_id=stations_map[f_info["station"]],
                subcategory_id=subcategories_map[f_info["subcategory"]],
                date_reported=datetime.fromisoformat(f_info["date_reported"]),
                date_occurred=datetime.fromisoformat(f_info["date_occurred"]),
                description=f_info["description"],
                status=f_info["status"],
                latitude=f_info["latitude"],
                longitude=f_info["longitude"]
            )
            session.add(fir)
            session.flush()
            firs_orm_map[fir.id] = fir
            
            # Setup initial investigation
            inv = Investigation(
                fir_id=fir.id,
                assigned_officer=random.choice(OFFICERS),
                status="COMPLETED" if fir.status in ["CLOSED", "CHARGE_SHEETED"] else "ONGOING",
                last_updated=fir.date_reported + timedelta(days=1)
            )
            session.add(inv)

        # Seed Victims
        for v_info in victims:
            vic = Victim(
                fir_id=v_info["fir_id"],
                name=v_info["name"],
                age=v_info["age"],
                gender=v_info["gender"],
                category=v_info["category"]
            )
            session.add(vic)

        # Seed Arrests and mapping links
        for a_info in arrests:
            arr = Arrest(
                fir_id=a_info["fir_id"],
                accused_id=a_info["accused_id"],
                arrest_date=datetime.fromisoformat(a_info["arrest_date"]),
                status=a_info["status"]
            )
            session.add(arr)
            
            # Add to many-to-many relationship map
            fir_obj = firs_orm_map[a_info["fir_id"]]
            acc_obj = accused_map[a_info["accused_id"]]
            fir_obj.accused_list.append(acc_obj)

        # Seed Convictions
        for c_info in convictions:
            conv = Conviction(
                fir_id=c_info["fir_id"],
                accused_id=c_info["accused_id"],
                conviction_date=datetime.fromisoformat(c_info["conviction_date"]),
                sentence_months=c_info["sentence_months"],
                status=c_info["status"]
            )
            session.add(conv)

        # 6. Seed mock Predictions (Historical + Future)
        # Seed for next 3 months in 2026
        # Seeding for April, May, June 2026 for each district and category
        current_year = 2026
        for m in [4, 5, 6]: # April, May, June 2026
            for d_name, d_id in districts_map.items():
                for c_name, c_id in categories_map.items():
                    pred_count = random.randint(15, 80) if d_name == "Bengaluru City" else random.randint(2, 20)
                    pred = CrimePrediction(
                        district_id=d_id,
                        year=current_year,
                        month=m,
                        category_id=c_id,
                        predicted_count=pred_count,
                        confidence=round(random.uniform(0.78, 0.96), 2)
                    )
                    session.add(pred)

        # 7. Seed Hotspots
        for ps_name, ps_id in stations_map.items():
            station_info = next((s for slist in STATIONS_DATA.values() for s in slist if s["name"] == ps_name), None)
            if station_info:
                # Add 2 hotspots per station
                for h in range(2):
                    hot = CrimeHotspot(
                        police_station_id=ps_id,
                        latitude=station_info["lat"] + random.uniform(-0.01, 0.01),
                        longitude=station_info["lng"] + random.uniform(-0.01, 0.01),
                        intensity=round(random.uniform(0.4, 0.95), 2),
                        prediction_date=datetime.utcnow().date() + timedelta(days=random.randint(1, 14))
                    )
                    session.add(hot)

        session.commit()
        print("Database successfully seeded with simulated Karnataka crime data.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    firs, victims, accused_pool, arrests, convictions = generate_csv_files()
    seed_database(firs, victims, accused_pool, arrests, convictions)
