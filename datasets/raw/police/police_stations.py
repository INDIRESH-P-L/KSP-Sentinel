import pandas as pd

df = pd.read_csv("fir.csv")

stations = (
    df[['District_Name', 'PoliceStation_Name']]
    .drop_duplicates()
    .sort_values(['District_Name', 'PoliceStation_Name'])
)

stations.to_csv("police_stations.csv", index=False)