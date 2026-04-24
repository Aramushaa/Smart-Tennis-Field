from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import settings


def escape_tag_value(value: str) -> str:
    return str(value).replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def escape_string_field(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def write_line_protocol(line: str) -> None:
    params = urlencode({"db": settings.influx_database})
    url = f"{settings.influx_host}/api/v3/write_lp?{params}"

    req = Request(
        url,
        data=line.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.influx_token}",
            "Content-Type": "text/plain; charset=utf-8",
        },
    )

    with urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        print(f"[INFLUX WRITE] status={resp.status} db={settings.influx_database} line={line}")
        if body:
            print(f"[INFLUX WRITE BODY] {body}")


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
