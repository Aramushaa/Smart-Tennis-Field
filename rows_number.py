import pandas as pd

df = pd.read_parquet("dataset/data.parquet")

subset = df[
    (df["device"] == "phone") &
    (df["id"].astype(str) == "11")
]

print("expected_rows =", len(subset))

dups = subset.groupby(["device", "id", "timestamp"]).size().reset_index(name="n")
dups = dups[dups["n"] > 1].sort_values("n", ascending=False)

print("duplicate timestamp groups =", len(dups))
print(dups.head(20))