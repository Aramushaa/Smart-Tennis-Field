# Smart Tennis Field

Master Thesis Project — Politecnico di Torino  
Docker-based IoT, time-series, and AI processing pipeline

---

## Overview

This project implements a Dockerized, distributed, event-driven IoT architecture for ingesting, storing, and processing multi-sensor data in a reproducible and measurable way.

The pipeline is designed to cover the full lifecycle:

```text
Data → Broker → Storage → Processing → Storage → API
```

This is not a demo-only system. It is a distributed ingestion infrastructure built for validation, measurement, and later AI processing.

---

## Objectives

- Ingest high-frequency sensor streams via MQTT
- Persist structured telemetry in InfluxDB 3
- Keep ingestion and processing decoupled
- Support independent processing microservices such as HAR
- Run reproducibly through Docker Compose
- Enable measurable latency and throughput evaluation

---

## Architecture

```text
Siddha Dataset (Parquet)
        |
        v
siddha-sensor-sim ──── MQTT QoS configurable (0 or 1)
        |
        v
EMQX (MQTT Broker)
        |
        v
ingest-service (FastAPI) ──── batch writer thread
        |
        v
InfluxDB 3 Core ──── nanosecond-precision timestamps
        ^
        |
har-service (next phase)
        |
        v
Predictions / derived outputs
```

### Data Semantic Separation

The system explicitly separates data semantics from transport reliability:

| Concern | Mechanism | Responsibility |
| --- | --- | --- |
| Sensor time | `dataset_ts` field | Preserves original recording timeline |
| Storage identity | InfluxDB timestamp (ns) | Adjusted for uniqueness via collision offsets |
| Delivery guarantee | MQTT QoS + `wait_for_publish` | Ensures no message loss in transit |

This separation allows independent tuning of replay fidelity, storage correctness, and transport reliability without coupling the three.

---

## Architectural Principles

- Event-driven design with MQTT as the backbone
- Strict separation of ingestion and processing
- Structured time-series storage instead of JSON-only blobs
- Microservice-oriented deployment
- Docker-first reproducibility
- Deterministic replay and evaluation paths

---

## Implemented Phases

### Phase 0 — MQTT Infrastructure

- EMQX broker running in Docker
- Topic design for sensor and camera streams
- QoS 1 subscriptions in ingest service
- Pub/sub validation completed

Topics:

- `tennis/sensor/+/events`
- `tennis/camera/+/ball`

### Phase 1 — Ingest and Persistence

- FastAPI ingest microservice
- MQTT background worker with `ThreadPoolExecutor` for non-blocking writes
- Event normalization layer
- InfluxDB 3 integration through line protocol writes
- Batch writer thread with configurable `INFLUX_BATCH_SIZE` and `INFLUX_FLUSH_INTERVAL_MS`

Normalized event shape:

```json
{
  "ts": "...",
  "topic": "...",
  "source": "mqtt",
  "payload": {}
}
```

### Phase 2 — Dataset Validation

This is the completed validation phase for the ingestion infrastructure.

Implemented:

- Siddha dataset replay through `siddha-sensor-sim`
- Full replay of ~64,700 samples (phone recording 11) validated
- Structured storage in `imu_raw` measurement
- Deterministic ordering preserved
- Throughput improved through batching (batch size: 3000, flush interval: 500ms)
- Timestamp collision handling via nanosecond offset

Key engineering fixes:

- Batch writer thread in ingest service replaces per-message HTTP calls
- Non-blocking MQTT publishing in simulator with configurable `qos` and `wait_for_publish`
- Nanosecond collision offset for duplicate `(device, recording_id, dataset_ts)` tuples
- `activity_gt` stored as a string field (not a tag) to avoid InfluxDB schema conflicts

### Phase 3 — HAR Microservice

Planned next:

- Sliding-window extraction from InfluxDB
- ONNX inference integration
- Prediction results written back to InfluxDB

---

## ⚠️ Important Findings During Dataset Validation

### 1. Timestamp Collision in Dataset

During validation of the Siddha dataset, we observed that multiple distinct samples share the same combination of:

- `device`
- `recording_id`
- `dataset_ts`

**Example:** At a single timestamp (e.g., `dataset_ts = 12.35`), up to ~18 different samples exist with different IMU values and different activity labels.

**Problem:** InfluxDB identifies points using `measurement + tags + timestamp`. When using `dataset_ts` directly as the InfluxDB timestamp, multiple samples collapsed into a single point — silently overwriting each other. This produced row counts as low as 99–154 when the expected count was ~64,700.

**Solution:** A nanosecond offset mechanism was introduced in the ingest service (`_next_imu_timestamp_ns`). Each duplicate timestamp within a `(device, recording_id)` group is shifted by +1ns, +2ns, etc. This preserves all rows without affecting chronological ordering.

### 2. Data Loss Under High-Speed Replay (Critical)

When using:

```env
SIDDHA_REPLAY_MODE=fast
SIDDHA_MQTT_QOS=0
SIDDHA_MQTT_WAIT_FOR_PUBLISH=false
```

we observed significant data loss:

| Metric | Value |
| --- | --- |
| Published by simulator | ~64,700 |
| Stored in InfluxDB | ~8,000 |
| Loss rate | ~88% |

**Root cause analysis:**

1. **Fire-and-forget publishing:** With QoS 0 and no `wait_for_publish`, the simulator completes before MQTT delivers all messages.
2. **EMQX queue overflow:** The broker's internal per-client queue has a default cap. When the ingest service cannot consume fast enough (due to blocking HTTP writes to InfluxDB), EMQX drops overflow messages.
3. **MQTT network thread blocking:** Before the `ThreadPoolExecutor` fix, the ingest service performed synchronous HTTP writes inside the paho-mqtt network callback, stalling acknowledgement of incoming messages.

### 3. Reliable Ingestion Configuration (Recommended)

To ensure correct, complete ingestion:

**Option A — Fast mode with delivery guarantees (recommended for batch runs):**

```env
SIDDHA_REPLAY_MODE=fast
SIDDHA_MQTT_QOS=1
SIDDHA_MQTT_WAIT_FOR_PUBLISH=true
```

**Option B — Realtime mode (recommended for demonstration/live replay):**

```env
SIDDHA_REPLAY_MODE=realtime
SIDDHA_REPLAY_SPEED=1.0
```

Both configurations result in **100% data consistency** between the simulator output and the stored InfluxDB rows.

---

## 📊 Dataset Validation Results

| Case | Replay Mode | QoS | Wait for Publish | Batch Writer | Result |
| --- | --- | --- | --- | --- | --- |
| A | `fast` | 0 | `false` | ❌ | ❌ ~88% data loss |
| B | `fast` | 1 | `true` | ✅ | ✅ 100% correct |
| C | `realtime` | 0 | `false` | ✅ | ✅ 100% correct |
| D | `realtime` | 1 | `true` | ✅ | ✅ 100% correct |

**Baseline configuration:** Case B is used as the reference for all subsequent phases.

---

## 🧠 Design Decisions

### Timestamp Handling

We considered multiple approaches for handling InfluxDB point identity when the dataset contains many samples at the same `dataset_ts`:

| Option | Pros | Cons |
| --- | --- | --- |
| Use `dataset_ts` directly | Clean semantics | Causes overwrites for parallel activities |
| Use wall-clock time | Unique per message | Breaks dataset ordering and reproducibility |
| `dataset_ts` + nanosecond offset | Preserves both meaning and uniqueness | Slight implementation complexity |

**Selected:** `dataset_ts` + nanosecond offset, implemented in `_next_imu_timestamp_ns()`.

### `activity_gt` as Field vs Tag

Initially, `activity_gt` was modeled as a TAG. However, InfluxDB 3 enforces strict column-type schemas: once a column is registered as a field, it cannot be changed to a tag (or vice versa) without creating a new measurement. After encountering `HTTP 400: partial write` errors due to schema conflicts, `activity_gt` was stabilized as a **string field**.

### Batch Writer Architecture

Individual HTTP writes per MQTT message introduced severe throughput bottlenecks (~100 writes/sec). The ingest service was refactored to use:

- A background `_writer_loop()` thread
- A thread-safe `_WRITE_QUEUE` with configurable `INFLUX_BATCH_SIZE` (default: 3000)
- A periodic flush via `INFLUX_FLUSH_INTERVAL_MS` (default: 500ms) or immediate flush when the batch is full

This eliminated the MQTT callback blocking issue and enabled reliable ingestion at high replay speeds.

---

## Services

| Service | Role | Status |
| --- | --- | --- |
| `emqx` | MQTT broker | Stable |
| `ingest-service` | MQTT consumer, normalization, batch persistence | Stable |
| `influxdb3` | Time-series database | Stable |
| `siddha-sensor-sim` | Dataset-driven MQTT simulator | Stable |
| `har-service` | Activity recognition processor | Next phase |
| `vision-gateway` | YOLO-based ball detection | Planned |
| `sensor-gateway` | Hardware sensor integration | Planned |

---

## Project Structure

```text
docs/
  Architecture.md
  DatasetContract.md
  Phases.md
  Journal.md

services/
  ingest_service/
  siddha_sensor_sim/
  har_service/        # next phase

dataset/
  data.parquet

docker-compose.yml
.env.example
query_db.py
README.md
```

Notes:

- Each service has its own Dockerfile
- The dataset is mounted through Docker, not hardcoded into the containers

---

## Documentation Guide

If you want to understand the project beyond the quickstart, start with the documents in [`docs/`](docs/). Each one answers a different question and is meant to be read independently.

- **System-level view:** [`docs/Architecture.md`](docs/Architecture.md) — explains the main components, how data moves across the pipeline, and how the services interact.
- **Dataset and payload contract:** [`docs/DatasetContract.md`](docs/DatasetContract.md) — defines the structure of the Siddha-derived sensor data and the fields expected by the pipeline.
- **Roadmap and thesis direction:** [`docs/Phases.md`](docs/Phases.md) — lays out the implementation phases from infrastructure validation to processing, orchestration, and evaluation.
- **Development narrative:** [`docs/Journal.md`](docs/Journal.md) — the best place to follow what changed, why it changed, and how the system evolved over time.

---

## Quickstart

### 1. Start the system

```bash
docker compose up -d --build
```

### 2. Create an InfluxDB admin token

```bash
docker exec -it influxdb3 influxdb3 create token --admin
```

### 3. Configure `.env`

Minimum required values:

```env
INFLUX_ENABLED=1
INFLUX_TOKEN=YOUR_TOKEN
INFLUX_DATABASE=tennis_phase2_qos1
INFLUX_TABLE=events
INFLUX_IMU_TABLE=imu_raw
INFLUX_BATCH_SIZE=3000
INFLUX_FLUSH_INTERVAL_MS=500
```

Simulator-related values:

```env
SIDDHA_MQTT_BROKER_HOST=emqx
SIDDHA_MQTT_BROKER_PORT=1883
SIDDHA_DATASET_PATH=/app/dataset/data.parquet
SIDDHA_REPLAY_MODE=fast
SIDDHA_REPLAY_SPEED=1.0
SIDDHA_MQTT_QOS=1
SIDDHA_MQTT_WAIT_FOR_PUBLISH=true
```

### 4. Restart services after changing `.env`

```bash
docker compose up -d
```

### 5. Verify data ingestion

```bash
python query_db.py
```

---

## Endpoints

| Service | URL |
| --- | --- |
| EMQX Dashboard | `http://localhost:18083` |
| InfluxDB 3 | `http://localhost:8181` |
| Ingest API | `http://localhost:8000` |

## API

- `GET /health`
- `GET /events`
- `POST /publish`

## MQTT Access

| Host | Port |
| --- | --- |
| `localhost` | `2883` |

If you connect from the host machine, use `localhost:2883`.

---

## Data Model

### MQTT Payload

```json
{
  "device": "phone",
  "recording_id": "11",
  "activity_gt": "A",
  "dataset_ts": 0.05,
  "acc_x": -0.656,
  "acc_y": 2.243,
  "acc_z": -0.782,
  "gyro_x": -1.944,
  "gyro_y": -9.776,
  "gyro_z": -0.460,
  "ts": "2026-03-30T11:24:26.680834+00:00"
}
```

### InfluxDB Schema (`imu_raw`)

**Measurement:** `imu_raw`

**Tags:**

- `device` — sensor device identifier (e.g., `phone`, `watch`)
- `recording_id` — Siddha recording session ID

**Fields:**

- `acc_x`, `acc_y`, `acc_z` — accelerometer readings (float)
- `gyro_x`, `gyro_y`, `gyro_z` — gyroscope readings (float)
- `dataset_ts` — original timestamp within the Siddha recording (float)
- `activity_gt` — ground-truth activity label (string)

**Timestamp:** Nanosecond-precision epoch derived from `dataset_ts` with collision offset, anchored to `2024-01-01T00:00:00Z`.

---

## Performance Design

### Previous Bottlenecks

- One HTTP write per MQTT message (~100 writes/sec ceiling)
- Blocking simulator publish path (fire-and-forget without confirmation)
- Timestamp collisions causing silent point overwrites in InfluxDB
- Synchronous InfluxDB writes inside the paho-mqtt network callback

### Current Approach

- Batch writer thread in ingest service (`INFLUX_BATCH_SIZE=3000`, `INFLUX_FLUSH_INTERVAL_MS=500`)
- `ThreadPoolExecutor` for non-blocking MQTT message processing
- Configurable MQTT QoS and `wait_for_publish` in the simulator
- Collision-safe nanosecond timestamp generation for IMU rows

**Result:**

- Full dataset ingestion validated at 100% consistency
- Throughput is substantially higher than per-message writes
- Stored rows remain deterministic and queryable

---

## Evaluation Metrics

- End-to-end latency (publish → storage)
- Ingestion throughput (messages/sec at various replay speeds)
- HAR processing latency (Phase 3)
- Broker restart recovery
- Database reconnection behavior
- CPU usage during replay and inference
- Replay mode comparison (realtime vs fast)
- Data consistency (published count vs stored count)

---

## Troubleshooting

### InfluxDB errors

- Verify `INFLUX_TOKEN` is set and valid
- Verify `INFLUX_DATABASE` exists
- Database names must use only letters, numbers, underscores, or hyphens
- If you see `HTTP 400: partial write`, check for schema conflicts (field vs tag mismatch)
- InfluxDB 3 Core has a 5-database limit — delete unused databases with `docker exec influxdb3 influxdb3 database delete <name>`

### MQTT issues

```bash
docker compose logs emqx ingest-service
```

### Low throughput

- Increase `INFLUX_BATCH_SIZE` (default: 3000)
- Decrease `INFLUX_FLUSH_INTERVAL_MS` (default: 500ms)
- Check simulator replay mode and replay speed
- Ensure `wait_for_publish=true` is not bottlenecking fast mode

### Data loss

- Check MQTT QoS level — QoS 0 does not guarantee delivery
- Check if `SIDDHA_MQTT_WAIT_FOR_PUBLISH=true` is set
- Verify ingest service logs for `[INFLUX] batch write error` messages

---

## Thesis Contribution

This project demonstrates:

- A reproducible distributed IoT ingestion pipeline
- Separation of ingestion and AI processing
- Structured time-series modeling for ML workloads
- Measurable system performance under replayed sensor data
- Empirical validation of MQTT QoS and flow control impact on data consistency
- Practical timestamp collision resolution in time-series databases

---

## Current Status

| Component | Status |
| --- | --- |
| MQTT infrastructure | ✅ Stable |
| Ingest service | ✅ Stable |
| Dataset validation pipeline | ✅ Completed |
| Timestamp collision handling | ✅ Resolved |
| Batch writer | ✅ Implemented |
| HAR service | 🔜 Next |
| Vision gateway | 📋 Planned |
