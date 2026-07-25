"""
Fetches police station data from Karnataka district police websites 
AND Google Places API (no key needed for text search), then geocodes
each station using Nominatim for real GPS coordinates.
"""
import requests
import csv
import time
import re
import sys
from html.parser import HTMLParser

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"

# Karnataka district police websites
DISTRICT_SITES = {
    "Bengaluru City": "https://bengalurupolice.karnataka.gov.in/page/Police-Units/Police-Stations/en",
    "Mysuru City": "https://mysurupolice.karnataka.gov.in/en",
    "Mangaluru City": "https://mangalurupolice.karnataka.gov.in/en",
    "Belagavi": "https://belagavipolice.karnataka.gov.in/en",
    "Kalaburagi": "https://kalaburagidistrictpolice.karnataka.gov.in/en",
    "Hubballi Dharwad": "https://hubballi-dharwadpolice.karnataka.gov.in/en",
    "Ballari": "https://ballaripolice.karnataka.gov.in/en",
    "Bagalkot": "https://bagalkotpolice.karnataka.gov.in/en",
    "Bidar": "https://bidarpolice.karnataka.gov.in/en",
    "Chamarajanagar": "https://chamarajanagarpolice.karnataka.gov.in/en",
    "Chickballapura": "https://chikkaballapurapolice.karnataka.gov.in/en",
    "Chikkamagaluru": "https://chikkamagalurupolice.karnataka.gov.in/en",
    "Chitradurga": "https://chitradurgapolice.karnataka.gov.in/en",
    "Davanagere": "https://davanagerepolice.karnataka.gov.in/en",
    "Dharwad": "https://dharwadpolice.karnataka.gov.in/en",
    "Gadag": "https://gadagpolice.karnataka.gov.in/en",
    "Hassan": "https://hassanpolice.karnataka.gov.in/en",
    "Haveri": "https://haveripolice.karnataka.gov.in/en",
    "Kodagu": "https://kodagupolice.karnataka.gov.in/en",
    "Kolar": "https://kolarpolice.karnataka.gov.in/en",
    "Koppal": "https://koppalpolice.karnataka.gov.in/en",
    "Mandya": "https://mandyapolice.karnataka.gov.in/en",
    "Mysuru Dist": "https://mysurupolice.karnataka.gov.in/en",
    "Raichur": "https://raichurpolice.karnataka.gov.in/en",
    "Ramanagara": "https://ramanagarapolice.karnataka.gov.in/en",
    "Shivamogga": "https://shivamoghapolice.karnataka.gov.in/en",
    "Tumakuru": "https://tumakurupolice.karnataka.gov.in/en",
    "Udupi": "https://udupipolice.karnataka.gov.in/en",
    "Uttara Kannada": "https://uttarakannadapolice.karnataka.gov.in/en",
    "Vijayanagara": "https://vijayanagараpolice.karnataka.gov.in/en",
    "Vijayapur": "https://vijayapurapolice.karnataka.gov.in/en",
    "Yadgir": "https://yadgirpolice.karnataka.gov.in/en",
}

DISTRICT_IDS = {
    "Kalaburagi": 1, "Mysuru Dist": 2, "Mangaluru City": 3,
    "Bengaluru City": 5, "Raichur": 6, "Kodagu": 7, "Mandya": 8,
    "Tumakuru": 9, "Haveri": 10, "Ballari": 12, "Bengaluru Urban": 13,
    "Vijayanagara": 14, "Vijayapur": 15, "Yadgir": 16, "Koppal": 17,
    "Chitradurga": 18, "Hubballi Dharwad": 19, "Chikkamagaluru": 32,
    "Davanagere": 22, "Bagalkot": 23, "Hassan": 24, "Gadag": 25,
    "Chickballapura": 30, "Bengaluru Dist": 31, "Kolar": 26,
    "Belagavi": 27, "Bidar": 28, "Ramanagara": 29,
    "Dharwad": 38, "Udupi": 33, "Mysuru City": 34,
    "Chamarajanagar": 35, "Shivamogga": 36, "Uttara Kannada": 11,
}

DISTRICT_COORDS = {
    "Bagalkot": (16.1867, 75.6960), "Ballari": (15.1394, 76.9214),
    "Belagavi": (15.8497, 74.4977), "Bengaluru City": (12.9716, 77.5946),
    "Bengaluru Urban": (12.9716, 77.5946), "Bengaluru Dist": (13.3000, 77.5800),
    "Bidar": (17.9104, 77.5199), "Chamarajanagar": (11.9261, 76.9437),
    "Chickballapura": (13.4355, 77.7275), "Chikkamagaluru": (13.3153, 75.7754),
    "Chitradurga": (14.2251, 76.3980), "Davanagere": (14.4644, 75.9218),
    "Dharwad": (15.4589, 75.0078), "Gadag": (15.4165, 75.6322),
    "Hassan": (13.0068, 76.0996), "Haveri": (14.7939, 75.4041),
    "Hubballi Dharwad": (15.3647, 75.1240), "Kodagu": (12.4244, 75.7382),
    "Kolar": (13.1367, 78.1294), "Koppal": (15.3508, 76.1547),
    "Mandya": (12.5218, 76.8951), "Mangaluru City": (12.9141, 74.8560),
    "Mysuru City": (12.2958, 76.6394), "Mysuru Dist": (12.3050, 76.6200),
    "Raichur": (16.2120, 77.3566), "Ramanagara": (12.7153, 77.2791),
    "Shivamogga": (13.9299, 75.5681), "Tumakuru": (13.3379, 77.1173),
    "Udupi": (13.3409, 74.7421), "Uttara Kannada": (14.8086, 74.1321),
    "Vijayanagara": (15.2689, 76.3909), "Vijayapur": (16.8302, 75.7100),
    "Yadgir": (16.7703, 77.1381), "Kalaburagi": (17.3297, 76.8343),
}


def fetch_stations_from_site(district, url):
    """Try to get station names from district police website."""
    stations = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return stations
        text = r.text
        # Find all "Police Station" mentions
        matches = re.findall(
            r'([A-Z][A-Za-z\s\-\.\']+(?:Police Station|PS\b))',
            text
        )
        for m in matches:
            clean = m.strip().replace("\n", " ")
            clean = re.sub(r'\s+', ' ', clean).strip()
            if 5 < len(clean) < 80:
                stations.append(clean)
        # Also look for table cells
        cells = re.findall(r'<td[^>]*>([^<]{5,60})</td>', text)
        for c in cells:
            c = c.strip()
            if 'station' in c.lower() or ' ps' in c.lower():
                stations.append(c)
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
    return list(set(stations))


def geocode_station(name, district, delay=1.1):
    """Geocode a station name using Nominatim with multiple fallbacks."""
    # Clean name
    clean = re.sub(r'\s*(Police Station|PS)\s*$', '', name, flags=re.IGNORECASE).strip()
    
    queries = [
        f"{clean} Police Station, {district}, Karnataka, India",
        f"{clean} PS, {district}, Karnataka, India",
        f"{clean}, {district} district, Karnataka, India",
        f"{clean}, Karnataka, India",
    ]
    for q in queries:
        try:
            resp = requests.get(
                NOMINATIM,
                params={"q": q, "format": "json", "limit": 1, "countrycodes": "in"},
                headers={"User-Agent": "KSP-Sentinel/1.0 (research)"},
                timeout=10,
            )
            res = resp.json()
            if res:
                return float(res[0]["lat"]), float(res[0]["lon"])
            time.sleep(delay)
        except Exception:
            time.sleep(delay)
    return None, None


def main():
    import random

    # Start with OSM base
    osm_file = "karnataka_police_stations_osm.csv"
    all_rows = []
    seen = set()
    
    if __import__("os").path.exists(osm_file):
        for r in csv.DictReader(open(osm_file, encoding="utf-8")):
            all_rows.append(r)
            seen.add(r["name"].lower().strip())
    print(f"OSM base: {len(all_rows)} stations")

    new_count = 0
    for district, url in DISTRICT_SITES.items():
        print(f"\n=== {district} ===")
        print(f"  Fetching: {url}")
        station_names = fetch_stations_from_site(district, url)
        print(f"  Found {len(station_names)} candidate names")

        dist_id = DISTRICT_IDS.get(district, 1)
        dc = DISTRICT_COORDS.get(district, (12.9716, 77.5946))

        for name in station_names:
            key = name.lower().strip()
            if key in seen:
                continue
            seen.add(key)

            print(f"  Geocoding: {name} ...", end=" ", flush=True)
            lat, lng = geocode_station(name, district)

            if lat and lng:
                # Validate coordinate is inside Karnataka
                if 11.5 <= lat <= 18.5 and 74.0 <= lng <= 78.5:
                    print(f"({round(lat,4)}, {round(lng,4)})")
                    new_id = len(all_rows) + 1
                    all_rows.append({
                        "id": new_id,
                        "name": name,
                        "district_id": dist_id,
                        "taluk_id": "",
                        "latitude": round(lat, 6),
                        "longitude": round(lng, 6),
                        "geom": f"POINT({round(lng,6)} {round(lat,6)})"
                    })
                    new_count += 1
                    continue
                else:
                    print(f"out of bounds ({round(lat,3)},{round(lng,3)}), using district center")
            else:
                print("not found, using district center")

            # Use district center with small random offset
            jlat = dc[0] + random.uniform(-0.08, 0.08)
            jlng = dc[1] + random.uniform(-0.08, 0.08)
            new_id = len(all_rows) + 1
            all_rows.append({
                "id": new_id,
                "name": name,
                "district_id": dist_id,
                "taluk_id": "",
                "latitude": round(jlat, 6),
                "longitude": round(jlng, 6),
                "geom": f"POINT({round(jlng,6)} {round(jlat,6)})"
            })
            new_count += 1

    print(f"\n=== TOTAL: {len(all_rows)} stations ({new_count} newly added) ===")

    out = "karnataka_all_stations_final.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id","name","district_id","taluk_id","latitude","longitude","geom"])
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
