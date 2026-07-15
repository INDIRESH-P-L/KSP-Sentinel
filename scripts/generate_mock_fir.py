import os
import pandas as pd
import numpy as np
import random

def generate_mock_data():
    districts = [
        "Bagalkot", "Ballari", "Belagavi City", "Belagavi Dist", "Bengaluru City",
        "Bengaluru Dist", "Bengaluru Urban", "Bengaluru Rural", "Bidar", "Chamarajanagar",
        "Chickballapura", "Chikkamagaluru", "Chitradurga", "Coastal Security Police",
        "Dakshina Kannada", "Davanagere", "Dharwad", "Gadag", "Hassan", "Haveri",
        "Hubballi Dharwad City", "K.G.F", "Kalaburagi", "Kalaburagi City", "Kodagu",
        "Kolar", "Koppal", "Mandya", "Mangaluru City", "Mysuru City", "Mysuru Dist",
        "Raichur", "Ramanagara", "Shivamogga", "Tumakuru", "Udupi", "Uttara Kannada",
        "Vijayanagara", "Vijayapur", "Yadgir"
    ]
    
    crime_groups = {
        "THEFT": ["Motor Vehicle Theft", "Bicycle Theft", "Theft from House", "Pickpocketing"],
        "MURDER": ["Murder for Gain", "Murder due to Enmity", "Dowry Murder", "Attempt to Murder"],
        "BURGLARY": ["House Breaking by Day", "House Breaking by Night", "Shop Burglary"],
        "CYBER CRIME": ["Cyber Fraud", "Identity Theft", "Phishing Scam", "Social Media Harassment"],
        "KIDNAPPING": ["Kidnapping of Children", "Kidnapping for Ransom", "Abduction"],
        "RIOTS": ["Communal Riots", "Political Riots", "Student Riots"],
        "ASSAULT": ["Assault on Public Servant", "Assault on Women", "Grievous Hurt"],
        "FRAUD": ["Cheating", "Forgery", "Embezzlement"]
    }
    
    stages = ["Convicted", "Dis/Acq", "Compounded", "Traced", "Pending Trial", "BoundOver", "UI", "Transfered"]
    complaint_modes = ["Written", "Oral", "Online", "Typed"]
    fir_types = ["Heinous", "Non Heinous"]
    
    officers = ["G.H.KUPPI (PSI)", "R S BIRADAR (PI)", "M.S.PATIL (PSI)", "A.K.NAIK (PI)", "S.B.DEVAR (PSI)"]
    
    rows = []
    
    for i in range(300):
        dist = random.choice(districts)
        station = f"{dist} Town PS" if random.random() > 0.3 else f"{dist} Rural PS"
        year = random.choice([2023, 2024])
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        
        cg = random.choice(list(crime_groups.keys()))
        ch = random.choice(crime_groups[cg])
        
        stage = random.choice(stages)
        comp_mode = random.choice(complaint_modes)
        ft = random.choice(fir_types)
        
        lat = random.uniform(12.0, 18.0)
        lng = random.uniform(74.0, 78.0)
        
        # Count values
        vic_count = random.randint(1, 4)
        male_v = random.randint(0, vic_count)
        female_v = vic_count - male_v
        boy_v = random.randint(0, male_v)
        girl_v = random.randint(0, female_v)
        
        acc_count = random.randint(0, 5)
        arrest_count = random.randint(0, acc_count)
        cs_count = random.randint(0, acc_count)
        
        conv_count = 0
        if stage == "Convicted" and acc_count > 0:
            conv_count = random.randint(1, acc_count)
            
        rows.append({
            'District_Name': dist,
            'UnitName': station,
            'FIR_YEAR': year,
            'FIR_MONTH': month,
            'FIR_Day': day,
            'FIR Type': ft,
            'FIR_Stage': stage,
            'Complaint_Mode': comp_mode,
            'CrimeGroup_Name': cg,
            'CrimeHead_Name': ch,
            'Latitude': lat,
            'Longitude': lng,
            'ActSection': f"IPC Section {random.randint(300, 500)}",
            'IOName': random.choice(officers),
            'Place of Offence': f"Near main bus stand, {dist}",
            'Male': male_v,
            'Female': female_v,
            'Boy': boy_v,
            'Girl': girl_v,
            'VICTIM COUNT': vic_count,
            'Accused Count': acc_count,
            'Arrested Count\tNo.': arrest_count,
            'Accused_ChargeSheeted Count': cs_count,
            'Conviction Count': conv_count
        })
        
    df = pd.DataFrame(rows)
    os.makedirs("datasets/raw/fir", exist_ok=True)
    df.to_csv("datasets/raw/fir/FIR_Details_Data.csv", index=False)
    print("Mock FIR_Details_Data.csv generated successfully with 300 rows!")

if __name__ == '__main__':
    generate_mock_data()
