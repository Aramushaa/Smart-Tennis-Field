# Siddha Dataset Contract (Post-Phase 2)

## 1. Purpose

This document defines how Siddha dataset rows are mapped into MQTT events and InfluxDB points inside the Smart Tennis Field infrastructure.

The contract exists to keep the system reproducible and consistent across:

- dataset replay
- MQTT transport
- ingestion
- time-series storage
- future HAR processing

Without an explicit contract, different services could interpret the same data differently. That would weaken maintainability, observability, and thesis defensibility.

---

## 2. Current Phase Context

**Current Phase:** Phase 2 — Dataset Validation (Completed)

### Implemented

- Siddha dataset replay through `siddha-sensor-sim`
- MQTT transport through EMQX
- `ingest-service` persistence into InfluxDB 3
- structured IMU storage
- validated end-to-end ingestion

### Current Data Flow

![Dataset contract data flow](dataset_contract_data_flow.svg)

---

## 3. Contract Scope

The Siddha contract spans four transformation layers:

1. source dataset row (`Parquet`)
2. internal normalized sample (`SensorSample`)
3. MQTT transport payload
4. persistence contract in InfluxDB (`events` and `imu_raw`)

This document defines the mapping rules across all four layers so that replay, storage, and future HAR processing interpret the same row consistently.

---

## 4. Source Dataset Schema

The Siddha simulator reads rows from the Parquet dataset using a validated source schema.

### Source Columns

- `device`
- `activity`
- `id`
- `acc_x`
- `acc_y`
- `acc_z`
- `gyro_x`
- `gyro_y`
- `gyro_z`
- `timestamp`

### Meaning of Each Source Column

- `device`: acquisition source, for example `phone` or `watch`
- `activity`: ground-truth activity label from Siddha
- `id`: recording or session identifier used for ordered replay
- `acc_x`, `acc_y`, `acc_z`: accelerometer axes
- `gyro_x`, `gyro_y`, `gyro_z`: gyroscope axes
- `timestamp`: logical dataset time inside the recording

---

## 5. Internal Normalized Sample Model

Inside `siddha-sensor-sim`, each validated dataset row is converted into a `SensorSample` dataclass with the fields:

- `device`
- `activity_gt`
- `recording_id`
- `dataset_ts`
- `acc_x`
- `acc_y`
- `acc_z`
- `gyro_x`
- `gyro_y`
- `gyro_z`

This normalized in-memory model is the stable contract between dataset parsing and MQTT publishing.

This internal normalization is important because it creates a stable handoff between:

- file parsing
- replay ordering
- MQTT publishing
- future processing logic

---

## 6. MQTT Topic Contract

### Topic Pattern

```text
tennis/sensor/<device>/events
```

### Example

```text
tennis/sensor/phone/events
```

### Why This Topic Shape

This topic design was chosen because it:

- keeps the namespace hierarchical
- allows wildcard subscription by `ingest-service`
- scales to multiple devices without changing consumer logic

The ingest layer subscribes using wildcard topics, including `tennis/sensor/+/events`.

---

## 7. MQTT Payload Contract

The simulator publishes JSON payloads built from each normalized sample.

### Payload Fields

- `device`
- `recording_id`
- `activity_gt`
- `dataset_ts`
- `acc_x`
- `acc_y`
- `acc_z`
- `gyro_x`
- `gyro_y`
- `gyro_z`
- `ts`

### Example Payload

```json
{
  "device": "phone",
  "recording_id": "11",
  "activity_gt": "A",
  "dataset_ts": 0.05,
  "acc_x": -2.77569058084895,
  "acc_y": -0.294898826381965,
  "acc_z": -2.38027008125201,
  "gyro_x": -2.46861868921189,
  "gyro_y": -12.001520214444,
  "gyro_z": -1.54664628877093,
  "ts": "2026-03-30T11:24:26.693346+00:00"
}
```

### Time Semantics Contract

The project uses three distinct time concepts:

| Name | Meaning | Lifecycle role |
| --- | --- | --- |
| `dataset_ts` | logical signal time inside the Siddha recording | ordering, querying, and future HAR window extraction |
| `ts` | wall-clock MQTT publish time | tracing and distributed-system timing |
| InfluxDB `time` | generated point timestamp used by the database | storage identity and ordering |

For structured IMU rows, InfluxDB `time` is not copied directly from the MQTT payload. Instead, it is generated from:

- a fixed base epoch (`2024-01-01T00:00:00Z`)
- `dataset_ts` converted to nanoseconds
- a per-key nanosecond collision offset

This preserves the semantic meaning of `dataset_ts` while ensuring that no rows are silently overwritten in storage.

---

## 8. Identity vs Metadata

Not every field in the contract contributes to storage identity.

For structured IMU storage in InfluxDB:

- identity is determined by:
  - measurement
  - tags: `device`, `recording_id`
  - generated InfluxDB timestamp

- metadata includes:
  - `activity_gt`
  - `dataset_ts`
  - IMU axis values

This distinction is important because `activity_gt` describes the sample but does not determine whether two points are considered the same by InfluxDB.

---

## 9. Duplicate Timestamp Behavior

The Siddha dataset contains multiple samples with identical:

- `device`
- `recording_id`
- `dataset_ts`

These samples differ in sensor values and may also differ in activity labels.

### Storage Problem

InfluxDB point identity is based on:

```text
measurement + tags + timestamp
```

Without disambiguation, rows sharing the same measurement, tags, and timestamp would overwrite one another.

### Resolution

---

## 10. Ingest Event Envelope Contract

Before persistence, `ingest-service` wraps received MQTT messages into a normalized envelope:

```json
{
  "ts": "...",
  "topic": "...",
  "source": "mqtt",
  "payload": {...}
}
```

This envelope is stored:

- in memory for debugging
- in the generic `events` measurement in InfluxDB

The envelope provides a generic event log independent of the structured IMU measurement.

---

## 11. InfluxDB Storage Contract

The ingest layer maintains two parallel persistence contracts for the same incoming MQTT sample:

- a generic event contract in `events` for tracing and debugging
- a structured signal contract in `imu_raw` for analytics and future HAR processing

### 11.1 Generic Event Storage

Measurement:

```text
events
```

Purpose:

- preserve normalized event history
- provide a generic debug and query layer

Stored structure:

- tags: `stream`, `source_id`
- field: `payload` as escaped JSON string
- timestamp: normalized event timestamp (`ts`) converted to epoch nanoseconds

### 11.2 Structured IMU Storage

Measurement:

```text
imu_raw
```

Measurement naming must remain consistent across docs, config, and code. If the project later standardizes on another name, all references must be updated together.

#### Tags

- `device`
- `recording_id`

#### Fields

- `acc_x`
- `acc_y`
- `acc_z`
- `gyro_x`
- `gyro_y`
- `gyro_z`
- `dataset_ts`
- `activity_gt`

#### Timestamp

The stored InfluxDB timestamp is not copied directly from either `dataset_ts` or `ts`.

It is generated from:

- a fixed base epoch (`2024-01-01T00:00:00Z`)
- `dataset_ts` converted to nanoseconds
- a nanosecond collision offset for rows that would otherwise share the same point identity

This is necessary because InfluxDB point identity is based on `measurement + tags + timestamp`.

Important:

- `activity_gt` is treated as metadata, not identity
- `dataset_ts` is preserved as a field for later querying and ML processing

---

## 12. Why the Contract Uses Structured IMU Fields

### Alternative 1 — JSON-only storage

Pros:

- simpler to implement

Cons:

- poor queryability
- poor fit for sliding-window ML
- requires JSON parsing later

### Alternative 2 — Structured Numeric Storage

Pros:

- queryable by SQL
- directly usable for HAR
- cleaner schema discipline

Cons:

- requires more design effort

Chosen approach:

- structured numeric IMU storage

This is the stronger option because the project is not only about storing messages, but about creating a processing-ready distributed pipeline.

---

## 13. Replay and Ordering Contract

The Siddha simulator replays rows in deterministic order by `recording_id` and `dataset_ts`, after applying optional filters.

### Replay Controls

- `replay_mode` (`realtime` or `fast`)
- `replay_speed`
- `loop_forever`
- `default_device_filter`
- `default_activity_filter`
- `default_recording_id_filter`
- `mqtt_qos`
- `mqtt_wait_for_publish`

Empty-string filter values are normalized to `None` before replay so that missing filter configuration does not accidentally exclude all rows.

### Ordering Note

The simulator enforces deterministic replay ordering by `recording_id` and `dataset_ts`. This ordering is intended for reproducibility and controlled experiments. It should be interpreted as a replay contract, not necessarily as a claim about absolute real-world simultaneity across all original acquisition sources.

### Why This Matters

This contract keeps the simulator useful for two different purposes:

- deterministic validation runs
- stress and replay-speed experiments

Correctness experiments and throughput experiments should not be conflated.

### Transport Reliability and Replay

Observed validation results showed that realtime replay was able to complete without loss under the tested configurations, while fast replay required stronger delivery controls.

| Configuration | Observed result in validation runs |
| --- | --- |
| `fast` + QoS 0 + no wait | data loss observed |
| `fast` + QoS 1 + `wait_for_publish=true` | 100% correct in validation runs |
| `realtime` under tested settings | completed without observed loss |

For deterministic validation, the recommended configuration is `fast` mode with QoS 1 and `wait_for_publish=true`.

---

## 14. Contract Verification

The contract can be verified at runtime through the following checks:

- source schema validation in the Siddha dataset loader
- deterministic replay ordering by `recording_id` and `dataset_ts`
- MQTT payload inspection in simulator logs or broker consumers
- schema inspection through `GET /events/schema`
- IMU row inspection through `GET /imu`
- count and device summaries through `GET /stats`

These checks help ensure that the documented contract matches the live system behavior.

---

## 15. Contract for Future HAR Integration

The HAR service will not consume arbitrary JSON directly from MQTT. It will consume structured windows derived from the raw IMU measurement.

Expected HAR input format:

```python
accelerometer = {"x": [...], "y": [...], "z": [...]}
gyroscope = {"x": [...], "y": [...], "z": [...]}
```

This means the current dataset contract must preserve:

- ordered numeric channels
- stable grouping keys
- logical signal time (`dataset_ts`)

Without that, Phase 3 would become fragile and non-reproducible.

---

## 16. Summary

This contract ensures that one Siddha row is transformed consistently across all stages of the pipeline:

```text
Parquet row
   ↓
SensorSample
   ↓
MQTT JSON payload
   ↓
Ingest event envelope
   ↓
Dual persistence:
  - events
  - imu_raw
```

This explicit contract is essential because it keeps the project:

- reproducible
- measurable
- maintainable
- ready for Phase 3 HAR processing
