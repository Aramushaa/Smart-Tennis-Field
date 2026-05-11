from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from .config import (
    CLEAN_TOPIC,
    DEFAULT_ACTIVITY_GT,
    MAX_ABS_ACC,
    MAX_ABS_GYRO,
    MAX_PAIR_AGE_SECONDS,
    MQTT_CLIENT_ID,
    MQTT_HOST,
    MQTT_PORT,
    QOS,
    RAW_TOPIC,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class RawSensorSample:
    sensor: str
    sensor_ts: float
    x: float
    y: float
    z: float
    wall_ts: str
    source: str
    device: str
    recording_id: str
    sampling_rate_hz: float


latest_acc: dict[tuple[str, str], RawSensorSample] = {}
clean_sample_idx: dict[tuple[str, str], int] = {}

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_float(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if value is None:
        raise ValueError(f"missing field: {key}")
    return float(value)


def parse_raw_payload(payload: dict[str, Any]) -> RawSensorSample:
    sensor = str(payload.get("sensor", "")).strip().lower()
    if sensor not in {"acc", "gyro"}:
        raise ValueError(f"unsupported sensor type: {sensor!r}")

    return RawSensorSample(
        sensor=sensor,
        sensor_ts=_as_float(payload, "sensor_ts"),
        x=_as_float(payload, "x"),
        y=_as_float(payload, "y"),
        z=_as_float(payload, "z"),
        wall_ts=str(payload.get("ts") or now_iso()),
        source=str(payload.get("source", "metawear")),
        device=str(payload.get("device", "watch")),
        recording_id=str(payload.get("recording_id", "unknown")),
        sampling_rate_hz=float(payload.get("sampling_rate_hz", 25)),
    )


def validate_sample(sample: RawSensorSample) -> None:
    bound = MAX_ABS_ACC if sample.sensor == "acc" else MAX_ABS_GYRO
    for axis, value in {"x": sample.x, "y": sample.y, "z": sample.z}.items():
        if abs(value) > bound:
            raise ValueError(
                f"{sample.sensor}.{axis} out of range: {value} > allowed abs {bound}"
            )


def build_clean_payload(acc: RawSensorSample, gyro: RawSensorSample) -> dict[str, Any]:
    key = (gyro.device, gyro.recording_id)
    idx = clean_sample_idx.get(key, 0)
    clean_sample_idx[key] = idx + 1

    # Use the gyro sample timestamp as the canonical row timestamp because we publish
    # one complete row when a gyro sample arrives and the latest acc sample is available.
    sensor_ts = gyro.sensor_ts

    return {
        "source": "metawear",
        "device": gyro.device,
        "recording_id": gyro.recording_id,
        "sensor_ts": sensor_ts,
        # Compatibility with existing Phase 3 ingest/HAR schema.
        "dataset_ts": sensor_ts,
        "sample_idx": idx,
        "acc_x": acc.x,
        "acc_y": acc.y,
        "acc_z": acc.z,
        "gyro_x": gyro.x,
        "gyro_y": gyro.y,
        "gyro_z": gyro.z,
        "activity_gt": DEFAULT_ACTIVITY_GT,
        "sampling_rate_hz": gyro.sampling_rate_hz,
        "quality": "ok",
        # Wall-clock timestamp for real-time database visualization.
        "ts": now_iso(),
    }


def maybe_publish_clean(sample: RawSensorSample) -> None:
    key = (sample.device, sample.recording_id)

    if sample.sensor == "acc":
        latest_acc[key] = sample
        return

    acc = latest_acc.get(key)
    if acc is None:
        logger.debug("Dropping gyro because no ACC sample exists yet | key=%s", key)
        return

    pair_age = abs(sample.sensor_ts - acc.sensor_ts)
    if pair_age > MAX_PAIR_AGE_SECONDS:
        logger.warning(
            "Dropping stale pair | key=%s | pair_age=%.3fs | max=%.3fs",
            key,
            pair_age,
            MAX_PAIR_AGE_SECONDS,
        )
        return

    clean_payload = build_clean_payload(acc, sample)
    result = client.publish(CLEAN_TOPIC, json.dumps(clean_payload), qos=QOS)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.error("Failed to publish clean payload | rc=%s", result.rc)


def on_connect(client_: mqtt.Client, userdata, flags, reason_code, properties=None) -> None:
    logger.info("Connected to MQTT | host=%s | port=%s | rc=%s", MQTT_HOST, MQTT_PORT, reason_code)
    client_.subscribe(RAW_TOPIC, qos=QOS)
    logger.info("Subscribed to raw topic: %s", RAW_TOPIC)
    logger.info("Publishing clean rows to: %s", CLEAN_TOPIC)


def on_message(client_: mqtt.Client, userdata, msg) -> None:
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        sample = parse_raw_payload(payload)
        validate_sample(sample)
        maybe_publish_clean(sample)
    except Exception as exc:
        logger.warning("Dropped raw message | topic=%s | error=%s", msg.topic, exc)


def main() -> None:
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            logger.info("Connecting to MQTT | host=%s | port=%s", MQTT_HOST, MQTT_PORT)
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as exc:
            logger.error("MQTT cleaner loop failed; retrying in 3s | error=%s", exc)
            time.sleep(3)


if __name__ == "__main__":
    main()
