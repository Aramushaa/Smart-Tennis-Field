# services/ingest_service/app/influx.py
import json
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from .utils.time_utils import now_iso
from typing import Any, Deque, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import (
    INFLUX_BATCH_SIZE,
    INFLUX_DATABASE,
    INFLUX_ENABLED,
    INFLUX_FLUSH_INTERVAL_MS,
    INFLUX_HOST,
    INFLUX_IMU_TABLE,
    INFLUX_TABLE,
    INFLUX_TOKEN,
)


MAX_RETRIES = 3


@dataclass
class QueueItem:
    line: str
    retries: int = 0


_WRITE_QUEUE: Deque[QueueItem] = deque()
_QUEUE_LOCK = threading.Lock()
_FLUSH_SIGNAL = threading.Event()
_STOP_SIGNAL = threading.Event()
_WRITER_THREAD: Optional[threading.Thread] = None

_FAILED_BATCH_COUNT = 0
_RETRIED_LINE_COUNT = 0
_DROPPED_LINE_COUNT = 0


def iso_to_epoch_nanos(ts: str) -> int:
    """
    Convert ISO timestamp to epoch nanoseconds.
    Handles:
      - "2026-02-10T16:59:10.239950Z"
      - "2026-02-10T16:59:10+00:00"
    """
    ts = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1_000_000_000)


def parse_topic(topic: str) -> tuple[str, str]:
    parts = topic.split("/")
    stream = parts[1] if len(parts) > 1 else "unknown"
    source_id = parts[2] if len(parts) > 2 else "unknown"
    return stream, source_id


def _write_lp_v3(line_protocol: str, db: str, precision: str = "s") -> None:
    if not INFLUX_TOKEN:
        raise RuntimeError("INFLUX_TOKEN is empty")

    params = urlencode({"db": db, "precision": precision})
    url = f"{INFLUX_HOST}/api/v3/write_lp?{params}"

    req = Request(url, data=line_protocol.encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {INFLUX_TOKEN}")
    req.add_header("Content-Type", "text/plain; charset=utf-8")

    import urllib.error

    try:
        with urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 202, 204):
                raise RuntimeError(f"Influx write failed HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP Error {e.code}: {e.reason} - Body: {body}")


def _enqueue_line(line: str) -> None:
    with _QUEUE_LOCK:
        _WRITE_QUEUE.append(QueueItem(line=line))
        if len(_WRITE_QUEUE) >= INFLUX_BATCH_SIZE:
            _FLUSH_SIGNAL.set()


def _drain_lines(limit: Optional[int] = None) -> list[QueueItem]:
    with _QUEUE_LOCK:
        if not _WRITE_QUEUE:
            return []

        if limit is None:
            limit = len(_WRITE_QUEUE)

        items: list[QueueItem] = []
        for _ in range(min(limit, len(_WRITE_QUEUE))):
            items.append(_WRITE_QUEUE.popleft())

        return items


def _requeue_failed_items(items: list[QueueItem]) -> None:
    """
    Put retryable items back at the FRONT of the queue so they are not delayed
    behind newer data. Drop items that exceeded MAX_RETRIES.
    """
    global _RETRIED_LINE_COUNT, _DROPPED_LINE_COUNT

    retryable: list[QueueItem] = []
    dropped = 0

    for item in items:
        if item.retries < MAX_RETRIES:
            item.retries += 1
            retryable.append(item)
        else:
            dropped += 1

    if retryable:
        with _QUEUE_LOCK:
            # appendleft reverses order, so we insert in reversed order
            for item in reversed(retryable):
                _WRITE_QUEUE.appendleft(item)
        _RETRIED_LINE_COUNT += len(retryable)
        _FLUSH_SIGNAL.set()

    if dropped > 0:
        _DROPPED_LINE_COUNT += dropped
        print(
            f"[INFLUX] CRITICAL: dropped {dropped} lines after {MAX_RETRIES} retries"
        )


def _flush_lines(items: list[QueueItem]) -> None:
    if not items:
        return

    payload = "\n".join(item.line for item in items)
    _write_lp_v3(payload, db=INFLUX_DATABASE, precision="ns")


def _writer_loop() -> None:
    global _FAILED_BATCH_COUNT

    flush_interval = max(INFLUX_FLUSH_INTERVAL_MS, 1) / 1000.0

    while not _STOP_SIGNAL.is_set():
        _FLUSH_SIGNAL.wait(timeout=flush_interval)
        _FLUSH_SIGNAL.clear()

        while True:
            items = _drain_lines(INFLUX_BATCH_SIZE)
            if not items:
                break

            try:
                _flush_lines(items)
            except Exception as e:
                _FAILED_BATCH_COUNT += 1
                print(f"[INFLUX] batch write error ({len(items)} lines): {e}")
                _requeue_failed_items(items)
                break

    # Final drain on shutdown
    while True:
        items = _drain_lines(INFLUX_BATCH_SIZE)
        if not items:
            break

        try:
            _flush_lines(items)
        except Exception as e:
            _FAILED_BATCH_COUNT += 1
            print(f"[INFLUX] batch write error | lines={len(items)} | error={e}")
            print("[INFLUX] retrying failed batch immediately")
            _requeue_failed_items(items)
            break


def start_influx_writer() -> None:
    global _WRITER_THREAD

    if not INFLUX_ENABLED:
        return
    if _WRITER_THREAD and _WRITER_THREAD.is_alive():
        return

    _STOP_SIGNAL.clear()
    _FLUSH_SIGNAL.clear()
    _WRITER_THREAD = threading.Thread(
        target=_writer_loop,
        daemon=True,
        name="influx-writer",
    )
    _WRITER_THREAD.start()


def stop_influx_writer() -> None:
    global _WRITER_THREAD

    if not _WRITER_THREAD:
        return

    _STOP_SIGNAL.set()
    _FLUSH_SIGNAL.set()
    _WRITER_THREAD.join(timeout=5)
    _WRITER_THREAD = None


def write_event_to_influx(ev: Dict[str, Any]) -> None:
    if not INFLUX_ENABLED:
        return

    topic = ev.get("topic", "unknown")
    stream, source_id = parse_topic(topic)
    ts_epoch = iso_to_epoch_nanos(ev.get("ts") or now_iso())

    payload_str = json.dumps(ev.get("payload", {}), ensure_ascii=False)
    escaped_payload = payload_str.replace("\\", "\\\\").replace('"', '\\"')
    line = (
        f'{INFLUX_TABLE},stream={stream},source_id={source_id} '
        f'payload="{escaped_payload}" {ts_epoch}'
    )
    _enqueue_line(line)


def query_influx_sql(sql: str) -> list[dict]:
    if not INFLUX_TOKEN:
        raise RuntimeError("INFLUX_TOKEN is empty")

    params = urlencode({"db": INFLUX_DATABASE, "q": sql})
    url = f"{INFLUX_HOST}/api/v3/query_sql?{params}"

    req = Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {INFLUX_TOKEN}")

    with urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def get_influx_writer_stats() -> dict:
    with _QUEUE_LOCK:
        queue_depth = len(_WRITE_QUEUE)

    return {
        "queue_depth": queue_depth,
        "failed_batch_count": _FAILED_BATCH_COUNT,
        "retried_line_count": _RETRIED_LINE_COUNT,
        "dropped_line_count": _DROPPED_LINE_COUNT,
        "writer_thread_alive": _WRITER_THREAD.is_alive() if _WRITER_THREAD else False,
        "max_retries": MAX_RETRIES,
    }


def write_imu_raw_to_influx(payload: dict) -> None:
    """
    Write structured IMU data into a dedicated measurement (imu_raw).
    """
    if not INFLUX_ENABLED:
        return

    try:
        device = payload.get("device", "unknown")
        recording_id = payload.get("recording_id", "unknown")
        sample_idx = int(payload.get("sample_idx", 0))

        acc_x = float(payload["acc_x"])
        acc_y = float(payload["acc_y"])
        acc_z = float(payload["acc_z"])
        gyro_x = float(payload["gyro_x"])
        gyro_y = float(payload["gyro_y"])
        gyro_z = float(payload["gyro_z"])

        dataset_ts = float(payload.get("dataset_ts", 0.0))
        activity_gt = payload.get("activity_gt", "unknown")

        base_epoch_ns = 1704067200_000_000_000
        dataset_ts_ns = int(dataset_ts * 1_000_000_000)
        ts_epoch = base_epoch_ns + dataset_ts_ns

        escaped_activity_gt = (
            str(activity_gt).replace("\\", "\\\\").replace('"', '\\"')
        )

        line = (
            f"{INFLUX_IMU_TABLE},device={device},recording_id={recording_id},sample_idx={sample_idx} "
            f"acc_x={acc_x},acc_y={acc_y},acc_z={acc_z},"
            f"gyro_x={gyro_x},gyro_y={gyro_y},gyro_z={gyro_z},"
            f'dataset_ts={dataset_ts},activity_gt="{escaped_activity_gt}" {ts_epoch}'
        )

        _enqueue_line(line)
    except Exception as e:
        print(f"[Influx IMU] Error: {e}")