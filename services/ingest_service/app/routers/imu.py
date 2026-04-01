from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..config import INFLUX_IMU_TABLE
from ..influx import query_influx_sql

router = APIRouter(tags=["imu"])


def _validate_timestamp(value: str, name: str) -> str:
    """Validate and normalize an ISO-8601 timestamp."""
    try:
        ts = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.isoformat()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timestamp for '{name}': {value!r}. Expected ISO-8601 format.",
        )


@router.get("/imu")
def get_imu(
    limit: int = Query(100, ge=1, le=5000),
    device: Optional[str] = Query(None),
    recording_id: Optional[str] = Query(None),
    activity_gt: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
    order_by: str = Query("dataset_ts", pattern="^(dataset_ts|time)$"),
    order_dir: str = Query("asc", pattern="^(asc|desc)$"),
):
    """
    Query structured IMU rows from the raw measurement.

    Supports filtering by:
    - device
    - recording_id
    - activity_gt
    - time range

    Supports ordering by:
    - dataset_ts (best for signal sequence analysis / HAR prep)
    - time (best for ingestion chronology)
    """
    where = []

    if device:
        where.append(f"device = '{device}'")
    if recording_id:
        where.append(f"recording_id = '{recording_id}'")
    if activity_gt:
        where.append(f"activity_gt = '{activity_gt}'")
    if from_ts:
        safe_from = _validate_timestamp(from_ts, "from")
        where.append(f"time >= '{safe_from}'")
    if to_ts:
        safe_to = _validate_timestamp(to_ts, "to")
        where.append(f"time <= '{safe_to}'")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    sql = f"""
    SELECT
        time,
        device,
        recording_id,
        activity_gt,
        dataset_ts,
        acc_x,
        acc_y,
        acc_z,
        gyro_x,
        gyro_y,
        gyro_z
    FROM {INFLUX_IMU_TABLE}
    {where_sql}
    ORDER BY {order_by} {order_dir.upper()}
    LIMIT {limit}
    """.strip()

    rows = query_influx_sql(sql)

    return {
        "measurement": INFLUX_IMU_TABLE,
        "count": len(rows),
        "filters": {
            "device": device,
            "recording_id": recording_id,
            "activity_gt": activity_gt,
            "from": from_ts,
            "to": to_ts,
            "order_by": order_by,
            "order_dir": order_dir,
        },
        "rows": rows,
    }