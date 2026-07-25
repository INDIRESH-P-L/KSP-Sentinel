"""
Step 1: Download all district contact PDFs from KSP website
Step 2: Extract police station names using text parsing
Step 3: Geocode each station using Nominatim (OpenStreetMap)
Step 4: Merge with existing OSM data for best coverage
"""
import requests
import csv
import time
import re
import sys
import os

# Known district PDF filenames from the KSP storage directory
DISTRICT_PDFS = {
    "Bengaluru City":   "bengaluru city.pdf",
    "Bengaluru Dist":   "bengaluru rural.pdf",
    "Bengaluru Urban":  "bengaluru urban.pdf",
    "Mysuru City":      "mysuru city.pdf",
    "Mysuru Dist":      "mysuru.pdf",
    "Mangaluru City":   "mangaluru.pdf",
    "Belagavi City":    "belagavi.pdf",
    "Kalaburagi":       "kalaburagi.pdf",
    "Hubballi Dharwad": "Hubli dharwad.pdf",
    "Ballari":          "ballari.pdf",
    "Bagalkot":         "bagalkot.pdf",
    "Bidar":            "bidar.pdf",
    "Chamarajanagar":   "chamarajanagar.pdf",
    "Chickballapura":   "chikkaballapur.pdf",
    "Chikkamagaluru":   "chikkamangaluur.pdf",
    "Chitradurga":      "chitradurga.pdf",
    "Davanagere":       "davanagere.pdf",
    "Dharwad":          "dharwad.pdf",
    "Gadag":            "gadag.pdf",
    "Hassan":           "hassan.pdf",
    "Haveri":           "haveri.pdf",
    "Kodagu":           "kodagu.pdf",
    "Kolar":            "kolar.pdf",
    "Koppal":           "koppal.pdf",
    "Mandya":           "mandya.pdf",
    "Raichur":          "raichur.pdf",
    "Ramanagara":       "ramanagara.pdf",
    "Shivamogga":       "shivamogga.pdf",
    "Tumakuru":         "tumkur.pdf",
    "Udupi":            "udupi.pdf",
    "Uttara Kannada":   "uttara kannada.pdf",
    "Vijayanagara":     "vijayanagara.pdf",
    "Vijayapur":        "vijayapura.pdf",
    "Yadgir":           "yadgir.pdf",
}

BASE_URL = "https://ksp.karnataka.gov.in/storage/pdf-files/"

DISTRICT_IDS = {
    "Kalaburagi": 1, "Mysuru Dist": 2, "Mangaluru City": 3,
    "Bengaluru City": 5, "Raichur": 6, "Kodagu": 7, "Mandya": 8,
    "Tumakuru": 9, "Haveri": 10, "Ballari": 12, "Bengaluru Urban": 13,
    "Vijayanagara": 14, "Vijayapur": 15, "Yadgir": 16, "Koppal": 17,
    "Chitradurga": 18, "Hubballi Dharwad": 19, "Chikkamagaluru": 32,
    "Davanagere": 22, "Bagalkot": 23, "Hassan": 24, "Gadag": 25,
    "Chickballapura": 30, "Bengaluru Dist": 31,
    "Belagavi City": 27, "Bidar": 28, "Ramanagara": 29,
    "Dharwad": 38, "Udupi": 33, "Mysuru City": 34,
    "Chamarajanagar": 35, "Shivamogga": 36, "Uttara Kannada": 11,
    "Kolar": 26,
}

def geocode_station(name, district):
    """Use Nominatim to geocode a station by name + district in Karnataka."""
    headers = {"User-Agent": "KSP-Sentinel/1.0 (research)"}
    search = f"{name}, {district}, Karnataka, India"
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": search,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
        "addressdetails": 0,
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None, None

def extract_station_names_from_pdf_text(text, district):
    """Parse station names from KSP PDF text. 
    Pattern: lines containing 'PS' or 'Police Station'"""
    stations = set()
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        # Match lines like: "Madhugiri PS", "Aldur Police Station", "Gokul Road P.S."
        if re.search(r'\bP\.?S\.?\b|\bPolice\s+Station\b', line, re.IGNORECASE):
            # Clean up: remove phone numbers, emails, designations
            clean = re.sub(r'\b(PI|PSI|SI|CI|L&O|CRM|HQ)\b', '', line)
            clean = re.sub(r'\d{5,}', '', clean)          # remove phone numbers
            clean = re.sub(r'\S+@\S+', '', clean)          # remove emails
            clean = re.sub(r'\s+', ' ', clean).strip()
            if len(clean) > 4 and len(clean) < 80:
                stations.add(clean)
    return list(stations)

def main():
    try:
        import pdfplumber
    except ImportError:
        print("Installing pdfplumber...")
        os.system("pip install pdfplumber -q")
        import pdfplumber

    all_stations = []
    os.makedirs("pdf_cache", exist_ok=True)

    for district, pdf_name in DISTRICT_PDFS.items():
        pdf_url = BASE_URL + requests.utils.quote(pdf_name)
        local_path = f"pdf_cache/{pdf_name}"

        print(f"\n--- {district} ---")
        
        # Download PDF if not cached
        if not os.path.exists(local_path):
            try:
                r = requests.get(pdf_url, timeout=20, headers={"User-Agent": "KSP-Sentinel/1.0"})
                if r.status_code == 200:
                    with open(local_path, "wb") as f:
                        f.write(r.content)
                    print(f"  Downloaded {pdf_name} ({len(r.content)//1024} KB)")
                else:
                    print(f"  SKIP: HTTP {r.status_code} for {pdf_url}")
                    continue
            except Exception as e:
                print(f"  SKIP: {e}")
                continue
        else:
            print(f"  Using cached {pdf_name}")

        # Extract text from PDF
        try:
            import pdfplumber
            with pdfplumber.open(local_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            station_names = extract_station_names_from_pdf_text(text, district)
            print(f"  Found {len(station_names)} station mentions")
            for name in station_names[:5]:
                print(f"    - {name}")
        except Exception as e:
            print(f"  PDF parse error: {e}")
            continue

        dist_id = DISTRICT_IDS.get(district, 1)
        
        for raw_name in station_names:
            all_stations.append({
                "name": raw_name,
                "district": district,
                "district_id": dist_id,
            })

    print(f"\nTotal raw station mentions: {len(all_stations)}")
    print("Now geocoding via Nominatim (1 req/sec rate limit)...")

    rows = []
    seen = set()
    for i, s in enumerate(all_stations):
        key = s["name"].lower().strip()
        if key in seen:
            continue
        seen.add(key)

        lat, lng = geocode_station(s["name"], s["district"])
        if lat and lng:
            rows.append({
                "id": len(rows) + 1,
                "name": s["name"],
                "district_id": s["district_id"],
                "taluk_id": "",
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "geom": f"POINT({round(lng,6)} {round(lat,6)})"
            })
            print(f"  [{len(rows)}] {s['name']} -> ({round(lat,4)}, {round(lng,4)})")
        else:
            print(f"  [?] {s['name']} -> not found")

        time.sleep(1.1)  # Nominatim rate limit: 1 req/sec

    # Write output
    with open("ksp_geocoded_stations.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id","name","district_id","taluk_id","latitude","longitude","geom"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone! Geocoded {len(rows)} stations -> ksp_geocoded_stations.csv")

if __name__ == "__main__":
    main()
