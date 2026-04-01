from fastapi import APIRouter

from ..config import INFLUX_IMU_TABLE
from ..influx import query_influx_sql

router = APIRouter(tags=["devices"])


@router.get("/devices")
def get_devices():
    """
    Return distinct device values from the raw IMU measurement.
    """
    sql = f"""
    SELECT DISTINCT device
    FROM {INFLUX_IMU_TABLE}
    ORDER BY device ASC
    """.strip()

    rows = query_influx_sql(sql)

    devices = [row["device"] for row in rows if "device" in row]

    return {
        "measurement": INFLUX_IMU_TABLE,
        "count": len(devices),
        "devices": devices,
    }