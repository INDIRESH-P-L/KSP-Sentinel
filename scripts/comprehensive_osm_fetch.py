"""
Comprehensive Karnataka police station fetcher using multiple Overpass queries.
Uses every possible OSM tagging scheme for police stations.
Karnataka bbox: S=11.5, W=74.0, N=18.5, E=78.35
"""
import requests
import csv
import json
import time

ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

HEADERS = {
    "User-Agent": "KSP-Sentinel/1.0 (Karnataka police mapping research)",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
}

BBOX = "11.5,74.0,18.5,78.35"

# Multiple queries targeting different OSM tagging schemes
QUERIES = [
    # 1. Standard amenity=police
    f"""[out:json][timeout:90][bbox:{BBOX}];
(node["amenity"="police"];way["amenity"="police"];relation["amenity"="police"];);
out center;""",

    # 2. Name contains "Police Station" or "PS" 
    f"""[out:json][timeout:90][bbox:{BBOX}];
(node["name"~"Police Station",i];way["name"~"Police Station",i];);
out center;""",

    # 3. Name contains " PS" 
    f"""[out:json][timeout:90][bbox:{BBOX}];
(node["name"~" PS$",i];way["name"~" PS$",i];);
out center;""",

    # 4. government=police or law_enforcement=police
    f"""[out:json][timeout:90][bbox:{BBOX}];
(node["government"="police"];node["office"="government"]["name"~"police",i];);
out center;""",
]

DISTRICT_MAP = [
    # (name_pattern, district_name, district_id, center_lat, center_lng)
    ("bagalkot|badami|hungund|mudhol|jamkhandi|bilagi|ilkal", "Bagalkot", 23, 16.1867, 75.6960),
    ("ballari|hospet|hosapete|sandur|siruguppa|bellary", "Ballari", 12, 15.1394, 76.9214),
    ("belagavi|belgaum|chikkodi|gokak|raibag|athani|bailhongal|khanapur|nippani|savadatti", "Belagavi", 27, 15.8497, 74.4977),
    ("bengaluru|bangalore|bengaluru city|whitefield|byatarayanapura|yelahanka|kr puram|indiranagar|cubbon|shivajinagar|jayanagar|sadashivanagar|rajajinagar|magadi road|hebbal|peenya|majestic|ejipura|koramangala|madiwala|hulimavu|banaswadi|electronic city", "Bengaluru City", 5, 12.9716, 77.5946),
    ("bidar|humnabad|bhalki|aurad|basavakalyan", "Bidar", 28, 17.9104, 77.5199),
    ("chamarajanagar|kollegal|gundlupet|hanur|yelandur", "Chamarajanagar", 35, 11.9261, 76.9437),
    ("chickballapur|chikkaballapur|gauribidanur|sidlaghatta|bagepalli|chintamani|gudibande", "Chickballapura", 30, 13.4355, 77.7275),
    ("chikkamagaluru|chikmagalur|kadur|tarikere|mudigere|koppa|sringeri|n.r.pura", "Chikkamagaluru", 32, 13.3153, 75.7754),
    ("chitradurga|challakere|holalkere|hiriyur|hosadurga|molakalmuru", "Chitradurga", 18, 14.2251, 76.3980),
    ("davanagere|davangere|harihar|channagiri|nyamati|jagalur|harapanahalli", "Davanagere", 22, 14.4644, 75.9218),
    ("dharwad|alnavar|kalghatgi|navalagund|kalaghatagi", "Dharwad", 38, 15.4589, 75.0078),
    ("gadag|betageri|nargund|lakshmeshwar|mundargi|shirahatti|ron", "Gadag", 25, 15.4165, 75.6322),
    ("hassan|belur|holenarasipur|arsikere|alur|sakleshpur|channarayapatna", "Hassan", 24, 13.0068, 76.0996),
    ("haveri|hirekerur|savanur|hanagal|ranebennur|byadagi|shiggaon", "Haveri", 10, 14.7939, 75.4041),
    ("hubballi|hubli|dharwad|unkal|navanagar|gokul road|keshwapur|vidyagiri|ghantikeri|kasabapeth|kamaripeth|ashoknagar", "Hubballi Dharwad", 19, 15.3647, 75.1240),
    ("kalaburagi|gulbarga|afzalpur|aland|chincholi|chitapur|jewargi|sedam|shahabad|wadi", "Kalaburagi", 1, 17.3297, 76.8343),
    ("kodagu|coorg|madikeri|somwarpet|virajpet|kushalnagar|ponnampet", "Kodagu", 7, 12.4244, 75.7382),
    ("kgf|kolar gold|kolar|srinivaspur|chintamani|malur|mulbagal|bangarpet", "Kolar", 26, 13.1367, 78.1294),
    ("koppal|gangavathi|kushtagi|yelbarga", "Koppal", 17, 15.3508, 76.1547),
    ("mandya|srirangapatna|krishnarajapete|maddur|nagamangala|pandavapura|malavalli|shrirangapattana", "Mandya", 8, 12.5218, 76.8951),
    ("mangaluru|mangalore|sullia|bantwal|belthangady|puttur|uppinangady|dakshina kannada", "Mangaluru City", 3, 12.9141, 74.8560),
    ("mysuru|mysore|nanjangud|hunsur|heggadadevankote|t.narasipur|periyapatna|krishnarajanagara", "Mysuru City", 34, 12.2958, 76.6394),
    ("raichur|sindhanur|manvi|devadurga|lingasugur|maski|mudgal", "Raichur", 6, 16.2120, 77.3566),
    ("ramanagara|magadi|channapatna|kanakapura", "Ramanagara", 29, 12.7153, 77.2791),
    ("shivamogga|shimoga|bhadravathi|sagar|sorab|tirthahalli|hosanagara|shikaripur", "Shivamogga", 36, 13.9299, 75.5681),
    ("tumakuru|tumkur|tiptur|chikkanayakanhalli|madhugiri|pavagada|sira|kunigal|gubbi|koratagere", "Tumakuru", 9, 13.3379, 77.1173),
    ("udupi|kundapura|karkala|manipal|brahmavar", "Udupi", 33, 13.3409, 74.7421),
    ("uttara kannada|karwar|ankola|sirsi|kumta|honavar|mundgod|haliyal|joida|yellapur|supa", "Uttara Kannada", 11, 14.8086, 74.1321),
    ("vijayanagara|hosapete|hagaribommanahalli|kampli|hagari|kudligi|siruguppa", "Vijayanagara", 14, 15.2689, 76.3909),
    ("vijayapur|bijapur|basavana bagewadi|indi|muddebihal|sindagi|talikot|muddebihal", "Vijayapur", 15, 16.8302, 75.7100),
    ("yadgir|shorapur|raichur|gurumitkal|shahpur", "Yadgir", 16, 16.7703, 77.1381),
    ("bengaluru rural|devanahalli|doddaballapura|hosakote|nelamangala", "Bengaluru Dist", 31, 13.3000, 77.5800),
]


def guess_district(name, lat, lng):
    """Guess district from name or coordinates."""
    name_lower = name.lower()
    for pattern, district, did, dlat, dlng in DISTRICT_MAP:
        for kw in pattern.split("|"):
            if kw.strip() in name_lower:
                return district, did
    # Fallback to coordinate proximity
    best, best_dist = None, float("inf")
    for pattern, district, did, dlat, dlng in DISTRICT_MAP:
        d = (lat - dlat)**2 + (lng - dlng)**2
        if d < best_dist:
            best_dist = d
            best = (district, did)
    return best if best else ("Unknown", 1)


def run_query(query, endpoint):
    """Run a single Overpass query and return parsed elements."""
    try:
        r = requests.post(endpoint, data={"data": query}, headers=HEADERS, timeout=100)
        if r.status_code == 200:
            return r.json().get("elements", [])
    except Exception as e:
        print(f"  Query error: {e}")
    return []


def main():
    all_stations = {}  # key=(round_lat,round_lng) -> station dict

    for qi, query in enumerate(QUERIES, 1):
        print(f"\nRunning query {qi}/{len(QUERIES)}...")
        elements = []
        for endpoint in ENDPOINTS:
            print(f"  Trying {endpoint}...")
            elements = run_query(query, endpoint)
            if elements:
                print(f"  Got {len(elements)} elements")
                break
            time.sleep(3)

        for elem in elements:
            tags = elem.get("tags", {})
            name = (tags.get("name") or tags.get("name:en") or "").strip()
            if not name:
                continue

            if elem["type"] == "node":
                lat = elem.get("lat")
                lng = elem.get("lon")
            else:
                c = elem.get("center", {})
                lat = c.get("lat")
                lng = c.get("lon")

            if not lat or not lng:
                continue

            # Key by rounded coordinates to deduplicate
            key = (round(lat, 4), round(lng, 4))
            if key in all_stations:
                continue

            # Basic Karnataka bounds check
            if not (11.3 <= lat <= 18.6 and 73.8 <= lng <= 78.6):
                continue

            district, did = guess_district(name, lat, lng)
            all_stations[key] = {
                "name": name,
                "district_id": did,
                "district": district,
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
            }

        print(f"  Running total: {len(all_stations)} unique stations")
        time.sleep(5)  # Be polite to Overpass

    # Sort by district then name
    rows = sorted(all_stations.values(), key=lambda r: (r["district_id"], r["name"]))
    
    out = "karnataka_police_stations_comprehensive.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id","name","district_id","taluk_id","latitude","longitude","geom"])
        writer.writeheader()
        for i, r in enumerate(rows, 1):
            lat, lng = r["latitude"], r["longitude"]
            writer.writerow({
                "id": i,
                "name": r["name"],
                "district_id": r["district_id"],
                "taluk_id": "",
                "latitude": lat,
                "longitude": lng,
                "geom": f"POINT({lng} {lat})",
            })

    print(f"\nSaved {len(rows)} stations to {out}")
    print("\nTop districts:")
    from collections import Counter
    c = Counter(r["district"] for r in rows)
    for district, count in c.most_common(10):
        print(f"  {district}: {count}")


if __name__ == "__main__":
    main()
