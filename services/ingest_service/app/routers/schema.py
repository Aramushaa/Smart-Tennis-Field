from fastapi import APIRouter

from ..config import INFLUX_IMU_TABLE, INFLUX_TABLE
from ..influx import query_influx_sql

router = APIRouter(tags=["schema"])


@router.get("/events/schema")
def get_schema():
    """
    Return schema information for both the generic events measurement
    and the structured IMU measurement.
    """
    events_sql = f"SHOW COLUMNS FROM {INFLUX_TABLE}"
    imu_sql = f"SHOW COLUMNS FROM {INFLUX_IMU_TABLE}"

    events_schema = query_influx_sql(events_sql)
    imu_schema = query_influx_sql(imu_sql)

    return {
        "events_measurement": INFLUX_TABLE,
        "events_schema": events_schema,
        "imu_measurement": INFLUX_IMU_TABLE,
        "imu_schema": imu_schema,
    }