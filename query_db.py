import annotated_types
from datetime import time
import os
import json
import urllib.request
from urllib.parse import urlencode

# Default fallback values
INFLUX_TOKEN = ""
INFLUX_HOST = "http://localhost:8181"
INFLUX_DATABASE = "events_full_rows"

# Attempt to read from .env file manually to avoid pip install python-dotenv
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("INFLUX_TOKEN="):
                INFLUX_TOKEN = line.split("=", 1)[1]
            elif line.startswith("INFLUX_HOST="):
                INFLUX_HOST = line.split("=", 1)[1]
            elif line.startswith("INFLUX_DATABASE="):
                INFLUX_DATABASE = line.split("=", 1)[1]

# Since we run this on the host machine, replace the Docker hostname with localhost
if "influxdb3" in INFLUX_HOST:
    INFLUX_HOST = INFLUX_HOST.replace("influxdb3", "localhost")

def query_influx(sql: str):
    if not INFLUX_TOKEN:
        print("Error: INFLUX_TOKEN is missing from .env file!")
        return

    params = urlencode({"db": INFLUX_DATABASE, "q": sql})
    url = f"{INFLUX_HOST}/api/v3/query_sql?{params}"

    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {INFLUX_TOKEN}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            print(f"\n--- Query Results for: {sql} ---\n")
            if not data:
                print("No results found.")
            for i, row in enumerate(data):
                print(f"Row {i+1}: {json.dumps(row, indent=2)}")
            print("-" * 40)
    except Exception as e:
        print(f"Query failed: {e}")

if __name__ == "__main__":
    print("🎾 Querying Smart Tennis Field InfluxDB Database...")

    query_influx("SELECT COUNT(*) AS n_rows FROM imu_raw;")

    # query_influx("SELECT device, COUNT(*) AS n_rows FROM imu_raw GROUP BY device ORDER BY n_rows DESC;")

    # query_influx("SELECT time, device, recording_id, activity_gt, dataset_ts, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z FROM imu_raw WHERE device = 'watch' AND recording_id = '1' AND dataset_ts = 0.15;")

    # query_influx("SELECT time, device, recording_id, activity_gt, dataset_ts, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z FROM imu_raw WHERE device = 'phone' AND recording_id = '11' AND activity_gt = 'A' ORDER BY dataset_ts ASC LIMIT 30;")
