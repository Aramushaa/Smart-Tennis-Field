import pandas as pd

df = pd.read_parquet("dataset/data.parquet")

subset = df[
    (df["device"] == "phone") &
    (df["id"].astype(str) == "11")
]

target_ts = 13.35  

rows = subset[subset["timestamp"] == target_ts].copy()

print(rows[[
    "device", "id", "timestamp",
    "acc_x", "acc_y", "acc_z",
    "gyro_x", "gyro_y", "gyro_z",
    "activity"
]].to_string(index=False))