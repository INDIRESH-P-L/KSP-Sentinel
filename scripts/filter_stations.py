import csv

rows_in = list(csv.DictReader(open('karnataka_police_stations_osm.csv', encoding='utf-8')))
rows_out = []

EXCLUDE = ['hyderabad','telangana','andhra','mahabubnagar','ap checkpost',
           'abids','secunderabad','warangal','nellore','tirupati','kerala',
           'goa','maharashtra','tamil','chennai','coimbatore']

for r in rows_in:
    lat = float(r['latitude'])
    lng = float(r['longitude'])
    name = r['name'].lower()

    if any(x in name for x in EXCLUDE):
        continue

    # Tighten bbox to exclude most border state stations
    if not (11.5 <= lat <= 18.4 and 74.0 <= lng <= 78.2):
        continue

    rows_out.append(r)

for i, r in enumerate(rows_out, 1):
    r['id'] = i

with open('karnataka_police_stations_osm.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['id','name','district_id','taluk_id','latitude','longitude','geom'])
    writer.writeheader()
    writer.writerows(rows_out)

print(f'Filtered: {len(rows_in)} -> {len(rows_out)} stations')
for r in rows_out[:10]:
    print(r['id'], r['name'], r['latitude'], r['longitude'])
