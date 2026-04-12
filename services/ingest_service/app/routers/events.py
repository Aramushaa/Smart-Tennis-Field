import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config import INFLUX_ENABLED, INFLUX_TOKEN, INFLUX_TABLE, PUB_TOPIC
from ..influx import query_influx_sql
from ..mqtt import get_memory_events, mqtt_client
from ..utils.validators import validate_iso_timestamp

router = APIRouter(tags=["events"])


@router.get("/events")
def get_events(
    limit: int = Query(50, ge=1, le=500),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
    source: str = Query("auto", pattern="^(auto|influx|memory)$"),
):
    use_influx = INFLUX_ENABLED and INFLUX_TOKEN and source in ("auto", "influx")

    if use_influx:
        where = []
        if from_ts:
            safe_from = validate_iso_timestamp(from_ts, "from")
            where.append(f"time >= '{safe_from}'")
        if to_ts:
            safe_to = validate_iso_timestamp(to_ts, "to")
            where.append(f"time <= '{safe_to}'")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"""
        SELECT time, stream, source_id, payload
        FROM {INFLUX_TABLE}
        {where_sql}
        ORDER BY time DESC
        LIMIT {limit}
        """.strip()

        try:
            rows = query_influx_sql(sql)
            return {"source": "influx", "count": len(rows), "events": rows}
        except Exception as e:
            if source == "auto":
                print("[INFLUX] query error, falling back to memory:", e)
            else:
                raise

    items = get_memory_events(limit)
    return {"source": "memory", "count": len(items), "events": items}


class PublishIn(BaseModel):
    topic: str = Field(default=PUB_TOPIC)
    payload: Dict[str, Any]


@router.post("/publish")
def publish(data: PublishIn):
    mqtt_client.publish(data.topic, json.dumps(data.payload), qos=0)
    return {"sent": True, "topic": data.topic, "payload": data.payload}