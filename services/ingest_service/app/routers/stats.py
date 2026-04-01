from fastapi import APIRouter

from ..config import INFLUX_IMU_TABLE, INFLUX_TABLE
from ..influx import query_influx_sql

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats():
    """
    Return a compact operational summary of the stored data.
    """
    events_count_sql = f"SELECT COUNT(*) AS n FROM {INFLUX_TABLE}"
    imu_count_sql = f"SELECT COUNT(*) AS n FROM {INFLUX_IMU_TABLE}"
    devices_sql = f"""
    SELECT device, COUNT(*) AS n
    FROM {INFLUX_IMU_TABLE}
    GROUP BY device
    ORDER BY n DESC
    """.strip()

    events_rows = query_influx_sql(events_count_sql)
    imu_rows = query_influx_sql(imu_count_sql)
    device_rows = query_influx_sql(devices_sql)

    events_count = events_rows[0]["n"] if events_rows else 0
    imu_count = imu_rows[0]["n"] if imu_rows else 0

    return {
        "events_measurement": INFLUX_TABLE,
        "imu_measurement": INFLUX_IMU_TABLE,
        "events_count": events_count,
        "imu_count": imu_count,
        "devices": device_rows,
    }