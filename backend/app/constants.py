# KSP Sentinel Constants

# Crime Statuses
STATUS_REGISTERED = "REGISTERED"
STATUS_INVESTIGATING = "INVESTIGATING"
STATUS_CHARGESHEETED = "CHARGE_SHEETED"
STATUS_CLOSED = "CLOSED"

ALL_STATUSES = [STATUS_REGISTERED, STATUS_INVESTIGATING, STATUS_CHARGESHEETED, STATUS_CLOSED]

# Demographic Categories
VIC_SENIOR_CITIZEN = "SENIOR_CITIZEN"
VIC_WOMAN = "WOMAN"
VIC_CHILD = "CHILD"
VIC_GENERAL = "GENERAL"

# Default Map Center (Karnataka Centroid)
KARNATAKA_CENTER_LAT = 15.3173
KARNATAKA_CENTER_LNG = 75.7139
MAP_DEFAULT_ZOOM = 7

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
