"""
Fetches all police stations in Karnataka from OpenStreetMap (Overpass API)
and outputs a clean police_stations.csv with real GPS coordinates.
"""

import requests
import csv
import json
import re
import sys

OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Karnataka bounding box: south=11.5, west=74.0, north=18.5, east=78.5
# Using [out:json][timeout:90] with bbox — much faster than area-based
QUERY = """
[out:json][timeout:90][bbox:11.5,74.0,18.5,78.5];
(
  node["amenity"="police"];
  way["amenity"="police"];
  relation["amenity"="police"];
);
out center;
"""

DISTRICT_KEYWORDS = {
    "Bengaluru": ["Bengaluru", "Bangalore", "Bengaluru Urban"],
    "Mysuru": ["Mysuru", "Mysore"],
    "Mangaluru": ["Mangaluru", "Mangalore", "Dakshina Kannada"],
    "Belagavi": ["Belagavi", "Belgaum"],
    "Kalaburagi": ["Kalaburagi", "Gulbarga"],
    "Hubballi": ["Hubballi", "Hubli", "Dharwad"],
    "Ballari": ["Ballari", "Bellary"],
    "Bagalkot": ["Bagalkot"],
    "Bidar": ["Bidar"],
    "Chamarajanagar": ["Chamarajanagar"],
    "Chickballapura": ["Chickballapura", "Chikballapur"],
    "Chikkamagaluru": ["Chikkamagaluru", "Chikmagalur"],
    "Chitradurga": ["Chitradurga"],
    "Davanagere": ["Davanagere", "Davangere"],
    "Gadag": ["Gadag"],
    "Hassan": ["Hassan"],
    "Haveri": ["Haveri"],
    "Kodagu": ["Kodagu", "Coorg", "Madikeri"],
    "Kolar": ["Kolar", "K.G.F", "Kgf"],
    "Koppal": ["Koppal"],
    "Mandya": ["Mandya"],
    "Raichur": ["Raichur"],
    "Ramanagara": ["Ramanagara"],
    "Shivamogga": ["Shivamogga", "Shimoga"],
    "Tumakuru": ["Tumakuru", "Tumkur"],
    "Udupi": ["Udupi"],
    "Uttara Kannada": ["Uttara Kannada", "Karwar"],
    "Vijayanagara": ["Vijayanagara", "Hosapete"],
    "Vijayapur": ["Vijayapur", "Bijapur"],
    "Yadgir": ["Yadgir"],
}

# Simple district-id mapping based on our existing CSV structure
DISTRICT_IDS = {
    "Kalaburagi": 1,
    "Mysuru Dist": 2,
    "Mangaluru City": 3,
    "Coastal Security": 4,
    "Bengaluru City": 5,
    "Raichur": 6,
    "Kodagu": 7,
    "Mandya": 8,
    "Tumakuru": 9,
    "Haveri": 10,
    "Uttara Kannada": 11,
    "Ballari": 12,
    "Bengaluru Urban": 13,
    "Vijayanagara": 14,
    "Vijayapur": 15,
    "Yadgir": 16,
    "Koppal": 17,
    "Chitradurga": 18,
    "Hubballi": 19,
    "K.G.F": 20,
    "Dakshina Kannada": 21,
    "Davanagere": 22,
    "Bagalkot": 23,
    "Hassan": 24,
    "Gadag": 25,
    "Kolar": 26,
    "Belagavi City": 27,
    "Bidar": 28,
    "Ramanagara": 29,
    "Chickballapura": 30,
    "Bengaluru Rural": 31,
    "Chikkamagaluru": 32,
    "Udupi": 33,
    "Mysuru City": 34,
    "Chamarajanagar": 35,
    "Shivamogga": 36,
    "Belagavi Dist": 37,
    "Dharwad": 38,
    "Bengaluru Dist": 39,
    "Kalaburagi City": 40,
}

def guess_district_id(name, tags):
    """Try to guess district_id from station name or address tags."""
    addr = " ".join([
        tags.get("addr:district", ""),
        tags.get("addr:city", ""),
        tags.get("addr:state_district", ""),
        name or ""
    ]).lower()
    
    for dist, keywords in DISTRICT_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in addr:
                # Map to closest matching district_id
                for dname, did in DISTRICT_IDS.items():
                    if dist.lower() in dname.lower() or dname.lower() in dist.lower():
                        return did
    return 1  # fallback

def main():
    print("Querying OpenStreetMap Overpass API for Karnataka police stations...")

    headers = {
        "User-Agent": "KSP-Sentinel/1.0 (karnataka police crime mapping research)",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"Trying endpoint: {endpoint}")
            r = requests.post(endpoint, data={"data": QUERY}, headers=headers, timeout=100)
            print(f"  HTTP Status: {r.status_code}")
            if r.status_code == 200:
                response = r
                break
            else:
                print(f"  Non-200 response, trying next endpoint...")
        except requests.exceptions.RequestException as e:
            print(f"  Error: {e}, trying next endpoint...")

    if response is None:
        print("ERROR: All Overpass endpoints failed.")
        sys.exit(1)
    
    data = response.json()
    elements = data.get("elements", [])
    print(f"Received {len(elements)} elements from OpenStreetMap.")
    
    rows = []
    seen = set()
    
    for elem in elements:
        tags = elem.get("tags", {})
        name = tags.get("name", tags.get("name:en", "")).strip()
        
        # Get coordinates
        if elem["type"] == "node":
            lat = elem.get("lat")
            lng = elem.get("lon")
        else:
            center = elem.get("center", {})
            lat = center.get("lat")
            lng = center.get("lon")
        
        if not lat or not lng:
            continue
        
        # Skip if no meaningful name
        if not name:
            # Try to construct name from tags
            name = tags.get("operator", tags.get("official_name", "Unknown Police Station"))
        
        # Deduplicate by name+coords
        key = (round(lat, 4), round(lng, 4))
        if key in seen:
            continue
        seen.add(key)
        
        district_id = guess_district_id(name, tags)
        
        rows.append({
            "name": name,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "district_id": district_id,
            "tags": json.dumps(tags, ensure_ascii=False)
        })
    
    print(f"Filtered to {len(rows)} unique police station locations.")
    
    # Sort by district_id then name
    rows.sort(key=lambda r: (r["district_id"], r["name"]))
    
    # Write CSV
    output_file = "karnataka_police_stations_osm.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "district_id", "taluk_id", "latitude", "longitude", "geom"])
        writer.writeheader()
        for i, row in enumerate(rows, start=1):
            lat = row["latitude"]
            lng = row["longitude"]
            writer.writerow({
                "id": i,
                "name": row["name"],
                "district_id": row["district_id"],
                "taluk_id": "",
                "latitude": lat,
                "longitude": lng,
                "geom": f"POINT({lng} {lat})"
            })
    
    print(f"\nDone! Saved {len(rows)} police stations to: {output_file}")
    print("\nSample entries:")
    for row in rows[:5]:
        print(f"  - {row['name']} ({row['latitude']}, {row['longitude']})")

if __name__ == "__main__":
    main()
