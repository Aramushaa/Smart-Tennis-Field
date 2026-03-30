# FastAPI entrypoint (the ingest service)

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .config import INFLUX_ENABLED, INFLUX_TOKEN, INFLUX_TABLE, PUB_TOPIC
from .mqtt import start_mqtt_thread, stop_mqtt, get_memory_events, mqtt_client
from .influx import query_influx_sql, start_influx_writer, stop_influx_writer


def _validate_timestamp(value: str, name: str) -> str:
    """Validate and normalize an ISO-8601 timestamp to prevent SQL injection."""
    try:
        ts = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.isoformat()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timestamp for '{name}': {value!r}. Expected ISO-8601 format.",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if INFLUX_ENABLED:
        start_influx_writer()
    start_mqtt_thread()
    print("[APP] startup complete")

    yield

    # Shutdown
    stop_mqtt()
    if INFLUX_ENABLED:
        stop_influx_writer()
    print("[APP] shutdown complete")


app = FastAPI(title="ingest-service", version="0.3.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ingest-service", "influx_enabled": INFLUX_ENABLED}


@app.get("/events")
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
            safe_from = _validate_timestamp(from_ts, "from")
            where.append(f"time >= '{safe_from}'")
        if to_ts:
            safe_to = _validate_timestamp(to_ts, "to")
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


@app.post("/publish")
def publish(data: PublishIn):
    mqtt_client.publish(data.topic, json.dumps(data.payload), qos=0)
    return {"sent": True, "topic": data.topic, "payload": data.payload}
