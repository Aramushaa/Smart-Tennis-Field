# Siddha Dataset Contract

## 1. Purpose

This document defines how Siddha dataset rows are mapped into MQTT events and InfluxDB points.

The contract keeps the system reproducible across dataset replay, MQTT transport, ingestion, and storage. Without it, different services could interpret the same data differently.

For the full data model and identity semantics, see [Architecture.md](Architecture.md).

---

## 2. Source Dataset Schema

The Siddha simulator reads rows from the Parquet dataset. Required columns:

| Column | Meaning |
| --- | --- |
| `device` | Acquisition source (`phone`, `watch`) |
| `activity` | Ground-truth activity label |
| `id` | Recording/session identifier |
| `acc_x`, `acc_y`, `acc_z` | Accelerometer axes |
| `gyro_x`, `gyro_y`, `gyro_z` | Gyroscope axes |
| `timestamp` | Logical time inside the recording |

---

## 3. Internal Normalized Model

Each validated dataset row is converted into a `SensorSample` dataclass:

| SensorSample field | Source column |
| --- | --- |
| `device` | `device` |
| `activity_gt` | `activity` |
| `recording_id` | Derived session identifier: `<activity>_<id>` |
| `dataset_ts` | `timestamp` |
| `sample_idx` | Computed duplicate-order index, preserved for inspection and future identity strengthening |
| `acc_x`, `acc_y`, `acc_z` | `acc_x`, `acc_y`, `acc_z` |
| `gyro_x`, `gyro_y`, `gyro_z` | `gyro_x`, `gyro_y`, `gyro_z` |

This model is the stable handoff between dataset parsing and MQTT publishing.

For Siddha replay, `recording_id` is derived as `<activity>_<id>` (for example `A_11`) rather than using the raw dataset `id` directly. This avoids ambiguity between labeled sessions that reuse the same raw `id` across different activities.

---

## 4. MQTT Topic Contract

Pattern:

```text
tennis/sensor/<device>/events
```

Example: `tennis/sensor/phone/events`

The ingest layer subscribes using `tennis/sensor/+/events`.

---

## 5. MQTT Payload Contract

The simulator publishes JSON payloads with these fields:

```json
{
  "device": "phone",
  "recording_id": "A_11",
  "activity_gt": "A",
  "dataset_ts": 0.05,
  "sample_idx": 0,
  "acc_x": -2.776,
  "acc_y": -0.295,
  "acc_z": -2.380,
  "gyro_x": -2.469,
  "gyro_y": -12.002,
  "gyro_z": -1.547,
  "ts": "2026-03-30T11:24:26.693346+00:00"
}
```

For timestamp and identity semantics, see [Architecture.md — Timestamp Semantics](Architecture.md#4-timestamp-semantics) and [Data Identity Model](Architecture.md#5-data-identity-model).

---

## 6. Ingest Event Envelope

Before persistence, `ingest-service` wraps received MQTT messages into a normalized envelope:

```json
{
  "ts": "...",
  "topic": "...",
  "source": "mqtt",
  "payload": {...}
}
```

This envelope is stored in memory for debugging and in the generic `events` measurement in InfluxDB.

---

## 7. InfluxDB Mapping Rules

Each incoming MQTT sample produces two writes:

1. **Generic event** → `events` measurement (full payload as JSON string)
2. **Structured IMU** → `imu_raw` measurement (numeric fields, tags)

For the complete `imu_raw` schema, tags, fields, and timestamp derivation, see [Architecture.md — Data Model](Architecture.md#3-data-model).

For the current validated Siddha configuration, `recording_id` is derived as `<activity>_<id>`, while `sample_idx` is retained as a field rather than a tag. This keeps duplicate-order metadata available without making it part of the current storage identity.

---

## 8. Replay and Ordering

The simulator derives a session identifier `<activity>_<id>` and replays rows in deterministic order consistent with session, device, logical timestamp, and duplicate-order index.

Replay controls:

| Setting | Purpose |
| --- | --- |
| `replay_mode` | `realtime` or `fast` |
| `replay_speed` | Multiplier for realtime mode |
| `loop_forever` | One-pass or continuous replay |
| `mqtt_qos` | Delivery guarantee level |
| `mqtt_wait_for_publish` | Block until broker acknowledges |

Empty-string filter values are normalized to `None` so that missing configuration does not accidentally exclude all rows.

For transport reliability findings, see [Architecture.md — Data Integrity](Architecture.md#7-data-integrity-and-transport-reliability).

---

## 9. Contract Verification

The contract can be verified at runtime:

- Source schema validation in the dataset loader
- MQTT payload inspection in simulator logs
- Schema inspection via `GET /events/schema`
- IMU row inspection via `GET /imu`
- Count summaries via `GET /stats`
