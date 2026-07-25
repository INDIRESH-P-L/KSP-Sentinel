"""
Smart geocoder: cleans KSP PDF station names properly and geocodes using 
two strategies:
1. Search as "<station_name>, <district>, Karnataka" on Nominatim
2. Fall back to district center if not found

Merges with OSM data for best combined coverage.
"""
import re
import csv
import time
import requests
import os
import glob

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "KSP-Sentinel/1.0 (research)"}

DISTRICT_COORDS = {
    "Bagalkot": (16.1867, 75.6960), "Ballari": (15.1394, 76.9214),
    "Belagavi City": (15.8497, 74.4977), "Bengaluru City": (12.9716, 77.5946),
    "Bengaluru Urban": (12.9716, 77.5946), "Bengaluru Dist": (13.3000, 77.5800),
    "Bidar": (17.9104, 77.5199), "Chamarajanagar": (11.9261, 76.9437),
    "Chickballapura": (13.4355, 77.7275), "Chikkamagaluru": (13.3153, 75.7754),
    "Chitradurga": (14.2251, 76.3980), "Dakshina Kannada": (12.8736, 74.8430),
    "Davanagere": (14.4644, 75.9218), "Dharwad": (15.4589, 75.0078),
    "Gadag": (15.4165, 75.6322), "Hassan": (13.0068, 76.0996),
    "Haveri": (14.7939, 75.4041), "Hubballi Dharwad": (15.3647, 75.1240),
    "Kodagu": (12.4244, 75.7382), "Kolar": (13.1367, 78.1294),
    "Koppal": (15.3508, 76.1547), "Mandya": (12.5218, 76.8951),
    "Mangaluru City": (12.9141, 74.8560), "Mysuru City": (12.2958, 76.6394),
    "Mysuru Dist": (12.3050, 76.6200), "Raichur": (16.2120, 77.3566),
    "Ramanagara": (12.7153, 77.2791), "Shivamogga": (13.9299, 75.5681),
    "Tumakuru": (13.3379, 77.1173), "Udupi": (13.3409, 74.7421),
    "Uttara Kannada": (14.8086, 74.1321), "Vijayanagara": (15.2689, 76.3909),
    "Vijayapur": (16.8302, 75.7100), "Yadgir": (16.7703, 77.1381),
}

DISTRICT_IDS = {
    "Kalaburagi": 1, "Mysuru Dist": 2, "Mangaluru City": 3,
    "Bengaluru City": 5, "Raichur": 6, "Kodagu": 7, "Mandya": 8,
    "Tumakuru": 9, "Haveri": 10, "Ballari": 12, "Bengaluru Urban": 13,
    "Vijayanagara": 14, "Vijayapur": 15, "Yadgir": 16, "Koppal": 17,
    "Chitradurga": 18, "Hubballi Dharwad": 19, "Chikkamagaluru": 32,
    "Davanagere": 22, "Bagalkot": 23, "Hassan": 24, "Gadag": 25,
    "Chickballapura": 30, "Bengaluru Dist": 31, "Kolar": 26,
    "Belagavi City": 27, "Bidar": 28, "Ramanagara": 29,
    "Dharwad": 38, "Udupi": 33, "Mysuru City": 34,
    "Chamarajanagar": 35, "Shivamogga": 36, "Uttara Kannada": 11,
}


def clean_station_name(raw):
    """Extract just the station name from messy PDF text."""
    # Remove emails
    raw = re.sub(r'\S+@\S+|\S+\[at\]\S+', '', raw)
    # Remove phone numbers (STD codes + numbers)
    raw = re.sub(r'\d{4,5}-\s*\d+', '', raw)
    raw = re.sub(r'\b\d{10}\b', '', raw)
    # Remove leading designations/numbers like "-1", "-2", "()", etc.
    raw = re.sub(r'^\s*[-\d()\s]+', '', raw)
    # Remove trailing garbage
    raw = re.sub(r'[\-\s]+$', '', raw)
    # Remove "PS" suffix to get clean location name
    raw = re.sub(r'\s*P\.?S\.?\s*$', '', raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r'\s+', ' ', raw).strip()
    return raw


def geocode(name, district):
    """Try to find coordinates for a police station."""
    search_terms = [
        f"{name} Police Station, {district}, Karnataka, India",
        f"{name}, {district}, Karnataka, India",
        f"{name}, Karnataka, India",
    ]
    for query in search_terms:
        try:
            r = requests.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1, "countrycodes": "in"},
                headers=HEADERS,
                timeout=10,
            )
            results = r.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"]), "nominatim"
        except Exception:
            pass
        time.sleep(1.1)
    return None, None, None


def main():
    # Load existing OSM data as base
    osm_file = "karnataka_police_stations_osm.csv"
    osm_rows = []
    osm_names = set()
    if os.path.exists(osm_file):
        for r in csv.DictReader(open(osm_file, encoding="utf-8")):
            osm_rows.append(r)
            osm_names.add(r["name"].lower().strip())
    print(f"Loaded {len(osm_rows)} stations from OSM base.")

    # Now process the downloaded PDFs
    pdf_stations = []
    pdf_dir = "pdf_cache"
    
    # Map PDF filenames back to districts
    pdf_to_district = {
        "belagavi.pdf": "Belagavi City",
        "Hubli dharwad.pdf": "Hubballi Dharwad",
        "ballari.pdf": "Ballari",
        "bagalkot.pdf": "Bagalkot",
        "bidar.pdf": "Bidar",
        "chikkamangaluur.pdf": "Chikkamagaluru",
        "chitradurga.pdf": "Chitradurga",
        "dharwad.pdf": "Dharwad",
        "gadag.pdf": "Gadag",
        "hassan.pdf": "Hassan",
        "haveri.pdf": "Haveri",
        "kodagu.pdf": "Kodagu",
        "kolar.pdf": "Kolar",
        "koppal.pdf": "Koppal",
        "mandya.pdf": "Mandya",
        "raichur.pdf": "Raichur",
        "shivamogga.pdf": "Shivamogga",
        "tumkur.pdf": "Tumakuru",
        "udupi.pdf": "Udupi",
        "vijayapura.pdf": "Vijayapur",
    }

    for pdf_file, district in pdf_to_district.items():
        path = os.path.join(pdf_dir, pdf_file)
        if not os.path.exists(path):
            continue
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as e:
            print(f"Skip {pdf_file}: {e}")
            continue

        # Extract station mentions
        lines = text.split("\n")
        for line in lines:
            if re.search(r'\bP\.?S\.?\b', line, re.IGNORECASE):
                clean = clean_station_name(line)
                if len(clean) < 4 or len(clean) > 60:
                    continue
                # Skip generic names
                if clean.lower() in {"cen", "women", "traffic", "l&o", "crm", "extn", "rural", "town"}:
                    continue
                pdf_stations.append((clean, district))

    print(f"Extracted {len(pdf_stations)} clean station names from PDFs.")

    # Deduplicate
    seen_names = set(osm_names)
    to_geocode = []
    for name, district in pdf_stations:
        key = name.lower().strip()
        if key not in seen_names:
            seen_names.add(key)
            to_geocode.append((name, district))

    print(f"New stations to geocode (not in OSM): {len(to_geocode)}")
    
    geocoded = []
    for i, (name, district) in enumerate(to_geocode):
        print(f"  [{i+1}/{len(to_geocode)}] {name}, {district} ...", end=" ", flush=True)
        lat, lng, source = geocode(name, district)
        if lat and lng:
            print(f"-> ({round(lat,4)}, {round(lng,4)})")
            geocoded.append({
                "name": f"{name} PS",
                "district": district,
                "district_id": DISTRICT_IDS.get(district, 1),
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
            })
        else:
            # Use district center as approximate location
            dc = DISTRICT_COORDS.get(district)
            if dc:
                import random
                jitter_lat = dc[0] + random.uniform(-0.05, 0.05)
                jitter_lng = dc[1] + random.uniform(-0.05, 0.05)
                geocoded.append({
                    "name": f"{name} PS",
                    "district": district,
                    "district_id": DISTRICT_IDS.get(district, 1),
                    "latitude": round(jitter_lat, 6),
                    "longitude": round(jitter_lng, 6),
                })
                print(f"-> approx district center")
            else:
                print("-> SKIP")

    # Combine OSM + newly geocoded
    all_rows = []
    for i, r in enumerate(osm_rows, 1):
        all_rows.append({
            "id": i,
            "name": r["name"],
            "district_id": r["district_id"],
            "taluk_id": "",
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "geom": r["geom"],
        })

    offset = len(osm_rows)
    for i, r in enumerate(geocoded, offset + 1):
        lat, lng = r["latitude"], r["longitude"]
        all_rows.append({
            "id": i,
            "name": r["name"],
            "district_id": r["district_id"],
            "taluk_id": "",
            "latitude": lat,
            "longitude": lng,
            "geom": f"POINT({lng} {lat})",
        })

    output = "karnataka_police_stations_final.csv"
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id","name","district_id","taluk_id","latitude","longitude","geom"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nFinal combined CSV: {len(all_rows)} stations -> {output}")


if __name__ == "__main__":
    main()
