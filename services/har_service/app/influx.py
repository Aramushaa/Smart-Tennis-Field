from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import settings


def query_influx_sql(sql: str) -> list[dict]:
    if not settings.influx_token:
        raise RuntimeError("HAR_INFLUX_TOKEN is empty")

    params = urlencode({
        "db": settings.influx_database,
        "q": sql,
    })
    url = f"{settings.influx_host}/api/v3/query_sql?{params}"

    req = Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {settings.influx_token}")

    with urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")

    return json.loads(body)