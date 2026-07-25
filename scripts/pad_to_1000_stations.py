import csv
import random

def generate_1000_stations():
    base_file = "d:/KSP-Sentinel/KSP-Sentinel/datasets/raw/police_stations.csv"
    out_file = "d:/KSP-Sentinel/KSP-Sentinel/karnataka_1000_stations.csv"
    
    # Read the 610 real stations we got from OpenStreetMap
    rows = []
    with open(base_file, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "name": r["name"],
                "district_id": int(r["district_id"]),
                "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]),
            })
            
    print(f"Loaded {len(rows)} real stations from OSM.")
    
    # We want to reach exactly 1012 stations (a realistic number for Karnataka)
    target = 1012
    needed = target - len(rows)
    
    # We will generate the remaining ones by picking a random district from our 
    # existing data, and placing a station nearby (within ~15-20km)
    
    districts = {}
    for r in rows:
        did = r["district_id"]
        if did not in districts:
            districts[did] = {"lats": [], "lngs": []}
        districts[did]["lats"].append(r["latitude"])
        districts[did]["lngs"].append(r["longitude"])
        
    print(f"Generating {needed} additional stations to reach {target}...")
    
    for i in range(needed):
        did = random.choice(list(districts.keys()))
        
        # Pick a random station in that district to cluster around
        base_lat = random.choice(districts[did]["lats"])
        base_lng = random.choice(districts[did]["lngs"])
        
        # Add random jitter between -0.15 and +0.15 degrees (~16km max)
        new_lat = base_lat + random.uniform(-0.15, 0.15)
        new_lng = base_lng + random.uniform(-0.15, 0.15)
        
        rows.append({
            "name": f"Rural Police Station Unit {i+1}",
            "district_id": did,
            "latitude": round(new_lat, 6),
            "longitude": round(new_lng, 6),
        })
        
    # Shuffle and re-id
    # random.shuffle(rows) # let's keep the real ones at the top for debugging
    
    for i, r in enumerate(rows, 1):
        r["id"] = i
        r["geom"] = f"POINT({r['longitude']} {r['latitude']})"
        r["taluk_id"] = ""
        
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id","name","district_id","taluk_id","latitude","longitude","geom"])
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Successfully generated {len(rows)} stations -> {out_file}")

if __name__ == '__main__':
    generate_1000_stations()
