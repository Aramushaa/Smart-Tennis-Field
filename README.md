# Smart Tennis Field

Master Thesis Project - Politecnico di Torino  
Docker-based IoT, time-series, and AI processing pipeline

---

## Overview

This project implements a Dockerized, distributed, event-driven IoT architecture for ingesting, storing, and processing multi-sensor data in a reproducible and measurable way.

The pipeline is designed to cover the full lifecycle:

```text
Data -> Broker -> Storage -> Processing -> Storage -> API
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

![Smart Tennis Field IoT pipeline](docs/smart_tennis_field_iot_pipeline.svg)

### Data Flow

```text
Parquet Dataset
-> SiddhaDatasetLoader
-> MQTT Publisher
-> EMQX Broker
-> Ingest Service
-> InfluxDB
```

During dataset loading:

- rows are sorted deterministically
- duplicate timestamps are detected
- `sample_idx` is assigned per group

This ensures that:

- replay is reproducible
- all samples are preserved
- no collisions occur in storage

### Data Semantic Separation

The system explicitly separates signal time, sample identity, storage time, and transport guarantees:

| Concern | Mechanism | Responsibility |
| --- | --- | --- |
| Sensor time | `dataset_ts` field | Preserves the original recording timeline |
| Sample identity | `(device, recording_id, dataset_ts, sample_idx)` | Uniquely identifies duplicate samples |
| Storage time | InfluxDB `time` derived from `dataset_ts` | Provides deterministic ordering in storage |
| Delivery guarantee | MQTT QoS + `wait_for_publish` | Controls transport reliability |

This separation allows replay fidelity, transport guarantees, and storage correctness to be reasoned about independently.

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

### Phase 0 - MQTT Infrastructure

- EMQX broker running in Docker
- Topic design for sensor and camera streams
- QoS 1 subscriptions in ingest service
- Pub/sub validation completed

Topics:

- `tennis/sensor/+/events`
- `tennis/camera/+/ball`

### Phase 1 - Ingest and Persistence

- FastAPI ingest microservice
- MQTT background worker
- In-memory event buffer for debugging
- Queue-based batch persistence to InfluxDB through a background writer thread
- InfluxDB 3 integration through line protocol writes
- Batch writer controlled by `INFLUX_BATCH_SIZE` and `INFLUX_FLUSH_INTERVAL_MS`
- Explorer UI available for manual inspection

Normalized event shape:

```json
{
  "ts": "...",
  "topic": "...",
  "source": "mqtt",
  "payload": {}
}
```

### Phase 2 - Dataset Validation

This is the completed validation phase for the ingestion infrastructure.

Implemented:

- Siddha dataset replay through `siddha-sensor-sim`
- Structured storage in `imu_raw`
- Deterministic ordering preserved
- Throughput improved through batching
- Explicit duplicate-sample indexing through `sample_idx`

Key engineering fixes:

- Batch writer thread in ingest service replaces per-message HTTP writes
- Configurable MQTT QoS and `wait_for_publish` in the simulator
- `sample_idx` is assigned during dataset loading and propagated through MQTT into InfluxDB tags
- `activity_gt` is stored as a string field, not a tag, to avoid InfluxDB schema conflicts

### Phase 3 - HAR Microservice

Planned next:

- Sliding-window extraction from InfluxDB
- ONNX inference integration
- Prediction results written back to InfluxDB

---

## Timestamp And Identity Model

The project uses four distinct concepts:

| Name | Meaning | Where it comes from | Where it is used |
| --- | --- | --- | --- |
| `dataset_ts` | Logical signal time inside the Siddha recording | Parquet dataset | Stored in `imu_raw`, used for signal ordering and future HAR windows |
| `sample_idx` | Duplicate index inside one logical timestamp group | Dataset loader | Distinguishes samples that share the same `dataset_ts` |
| `ts` | Wall-clock publish timestamp | Simulator at MQTT publish time | Stored in normalized events and used for generic event tracing |
| `time` | InfluxDB point timestamp | Derived from `dataset_ts` by converting it to nanoseconds and anchoring it to a fixed base epoch | Used by InfluxDB for storage ordering |

Important clarification:

- `dataset_ts` keeps the original dataset timing
- `sample_idx` makes duplicate sample identity explicit
- `time` is part of InfluxDB storage and is not treated as the semantic event time
- no artificial `+1ns`, `+2ns`, or collision-offset strategy is used

### Handling Duplicate Timestamps (Data Identity Model)

The Siddha dataset contains multiple samples sharing the same:

- device
- recording_id
- dataset timestamp (`dataset_ts`)

This means that the tuple `(device, recording_id, dataset_ts)` is not sufficient to uniquely identify a sample.

Instead of modifying timestamps artificially, the system introduces an explicit duplicate index:

- `sample_idx`: an integer assigned per group of duplicate samples

This index is computed as:

- `0` -> first sample at a given timestamp
- `1` -> second sample
- `2` -> third sample
- `...`

As a result, each sample is uniquely identified by:

```text
(device, recording_id, dataset_ts, sample_idx)
```

This approach:

- preserves the original dataset timing
- avoids hidden timestamp manipulation
- makes data identity explicit and reproducible

### Design Choice: Explicit vs Implicit Uniqueness

Two approaches were considered:

1. Implicit uniqueness through timestamp offsets
2. Explicit uniqueness through `sample_idx`

The second approach was chosen because:

- it preserves the semantic meaning of time
- it avoids hidden transformations
- it makes debugging and querying easier
- it aligns better with time-series data modeling principles

Earlier iterations considered nanosecond offsets to prevent collisions. The current model replaces that approach with explicit duplicate indexing.

---

## Important Findings During Dataset Validation

### 1. Duplicate Samples Must Be Modeled Explicitly

The key issue was not "bad timestamps" but duplicate samples sharing the same logical dataset time. Explicit indexing was required to preserve those rows without changing the recorded timeline.

### 2. Data Loss Under High-Speed Replay

When using:

```env
SIDDHA_REPLAY_MODE=fast
SIDDHA_MQTT_QOS=0
SIDDHA_MQTT_WAIT_FOR_PUBLISH=false
```

significant data loss can occur because transport guarantees are relaxed while publish rate is high.

Primary causes:

- fire-and-forget publishing
- broker-side queue pressure
- consumers not draining fast enough under aggressive replay

### 3. Reliable Ingestion Configuration

Recommended for batch runs:

```env
SIDDHA_REPLAY_MODE=fast
SIDDHA_MQTT_QOS=1
SIDDHA_MQTT_WAIT_FOR_PUBLISH=true
```

Recommended for demos:

```env
SIDDHA_REPLAY_MODE=realtime
SIDDHA_REPLAY_SPEED=1.0
```

---

## Deterministic Replay

The simulator replays dataset samples in a deterministic order:

1. Data is sorted by:
   - `recording_id`
   - `device`
   - `timestamp`
   - `sample_idx`
2. Duplicate samples are explicitly indexed using `sample_idx`
3. Samples are streamed using a generator (`yield`), enabling:
   - memory-efficient processing
   - large dataset replay

This guarantees reproducibility across runs.

---

## Services

| Service | Role | Status |
| --- | --- | --- |
| `emqx` | MQTT broker | Stable |
| `ingest-service` | MQTT consumer, normalization, batch persistence | Stable |
| `influxdb3` | Time-series database | Stable |
| `influxdb3-explorer` | Explorer UI for schema and query inspection | Stable |
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
  smart_tennis_field_iot_pipeline.svg

services/
  ingest_service/
  siddha_sensor_sim/
  har_service/        # next phase

dataset/
  data.parquet

docker-compose.yml
.env.example
README.md
```

Notes:

- each service has its own Dockerfile
- the dataset is mounted through Docker, not hardcoded into the containers

---

## Documentation Guide

If you want to understand the project beyond the quickstart, start with the documents in [`docs/`](docs/). Each one answers a different question and is meant to be read independently.

- System-level view: [`docs/Architecture.md`](docs/Architecture.md)
- Dataset and payload contract: [`docs/DatasetContract.md`](docs/DatasetContract.md)
- Roadmap and thesis direction: [`docs/Phases.md`](docs/Phases.md)
- Development narrative: [`docs/Journal.md`](docs/Journal.md)

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

Recommended baseline:

```env
INFLUX_ENABLED=1
INFLUX_TOKEN=YOUR_TOKEN
INFLUX_DATABASE=tennis_phase2_qos1
INFLUX_TABLE=events
INFLUX_IMU_TABLE=imu_raw
INFLUX_BATCH_SIZE=3000
INFLUX_FLUSH_INTERVAL_MS=500

SIDDHA_MQTT_BROKER_HOST=emqx
SIDDHA_MQTT_BROKER_PORT=1883
SIDDHA_DATASET_PATH=/app/dataset/data.parquet
SIDDHA_REPLAY_MODE=fast
SIDDHA_REPLAY_SPEED=1.0
SIDDHA_MQTT_QOS=1
SIDDHA_MQTT_WAIT_FOR_PUBLISH=true
SIDDHA_LOOP_FOREVER=false

SIDDHA_DEFAULT_DEVICE_FILTER=
SIDDHA_DEFAULT_ACTIVITY_FILTER=
SIDDHA_DEFAULT_RECORDING_ID_FILTER=
```

### 4. Restart after changing `.env`

```bash
docker compose up -d
```

### 5. Open the dashboards

- EMQX Dashboard: `http://localhost:18083`
- InfluxDB 3 Explorer: `http://localhost:8888`
- Ingest API: `http://localhost:8000`

---

## Endpoints

| Service | URL |
| --- | --- |
| EMQX Dashboard | `http://localhost:18083` |
| InfluxDB 3 | `http://localhost:8181` |
| InfluxDB 3 Explorer | `http://localhost:8888` |
| Ingest API | `http://localhost:8000` |

### Docker Networking Note

When connecting services from inside the Docker network, use Compose service names rather than `localhost`.

Examples:

- Ingest service -> InfluxDB: `http://influxdb3:8181`
- Simulator -> MQTT broker: `emqx:1883`

Use `localhost` only from the host machine, for example:

- `http://localhost:8181`
- `http://localhost:8888`
- `localhost:2883`

---

## API

### Health

- `GET /health` - service readiness and basic configuration state

### Generic events

- `GET /events` - query normalized event history from InfluxDB or memory fallback
- `POST /publish` - publish a test payload to MQTT

### Structured IMU data

- `GET /imu` - query structured raw IMU rows with filters such as `device`, `recording_id`, `activity_gt`, time range, and ordering

### Operational inspection

- `GET /devices` - list distinct device values in `imu_raw`
- `GET /stats` - compact summary of events count, IMU count, and per-device counts
- `GET /events/schema` - inspect schemas for `events` and `imu_raw`

---

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
  "sample_idx": 0,
  "acc_x": -0.656,
  "acc_y": 2.243,
  "acc_z": -0.782,
  "gyro_x": -1.944,
  "gyro_y": -9.776,
  "gyro_z": -0.460,
  "ts": "2026-03-30T11:24:26.680834+00:00"
}
```

### InfluxDB Data Model (`imu_raw`)

Each IMU sample is stored using the following structure:

Measurement:

- `imu_raw`

Tags:

- `device`
- `recording_id`
- `sample_idx`

Fields:

- `acc_x`, `acc_y`, `acc_z`
- `gyro_x`, `gyro_y`, `gyro_z`
- `dataset_ts`
- `activity_gt`

Time:

- derived from `dataset_ts` converted to nanoseconds and anchored to a fixed base epoch for InfluxDB storage

Example line protocol:

```text
imu_raw,device=phone,recording_id=11,sample_idx=2 acc_x=...,acc_y=...,gyro_x=...,dataset_ts=12.35,activity_gt="A" 1704067212350000000
```

Notes:

- `sample_idx` is part of the point identity as a tag
- no artificial timestamp offsets are used
- multiple samples can share the same timestamp-derived storage time but remain distinct due to `sample_idx`

### Example Query

To retrieve all samples for a given timestamp:

```sql
SELECT *
FROM imu_raw
WHERE recording_id = '11'
  AND dataset_ts = 12.35
ORDER BY sample_idx ASC
```

Results will include multiple rows distinguished by `sample_idx`.

---

## Performance Design

### Previous Bottlenecks

- one HTTP write per MQTT message
- blocking publish configuration during validation experiments
- duplicate samples requiring explicit identity modeling
- insufficient delivery guarantees under aggressive replay

### Current Approach

- batch writer thread in ingest service
- queue-based line protocol buffering
- configurable MQTT QoS and `wait_for_publish` in the simulator
- `sample_idx`-based identity for duplicate IMU rows

Result:

- full dataset ingestion can be made deterministic
- throughput is substantially higher than per-message writes
- stored rows remain queryable and reproducible

---

## Operational Verification

After startup, verify the system in this order:

1. `GET /health` on the ingest service
2. Open InfluxDB Explorer at `http://localhost:8888`
3. In the Explorer UI, connect to `http://localhost:8181`
4. Check schema with `GET /events/schema`
5. Check row counts with `GET /stats`
6. Query sample rows with `GET /imu?limit=20&order_by=dataset_ts&order_dir=asc`

Note:

- from containers, use `http://influxdb3:8181`
- from the host browser, use `http://localhost:8181`

---

## Evaluation Metrics

- end-to-end latency
- ingestion throughput at different replay settings
- broker restart recovery
- database reconnection behavior
- HAR processing latency in the next phase
- replay mode comparison
- published count versus stored count

---

## Security Notes

- Do not hardcode InfluxDB tokens in source files
- Keep secrets in `.env`, and never commit real tokens
- Expose only the ports needed for development and debugging
- Validate API query parameters before building SQL conditions
- Use Docker service names for internal communication instead of exposing extra ports unnecessarily

---

## Troubleshooting

### InfluxDB errors

- verify `INFLUX_TOKEN` is set and valid
- verify `INFLUX_DATABASE` exists
- database names must use only letters, numbers, underscores, or hyphens
- if you see `HTTP 400: partial write`, check for schema conflicts such as field versus tag mismatch

### MQTT issues

```bash
docker compose logs emqx ingest-service
```

### Explorer connectivity issues

- from the host browser, prefer `http://localhost:8181`
- from containers, use `http://influxdb3:8181`
- if Explorer loads but cannot connect, confirm `influxdb3` is running and port `8181` is exposed

### Low throughput

- increase `INFLUX_BATCH_SIZE`
- decrease `INFLUX_FLUSH_INTERVAL_MS`
- check replay mode and replay speed
- use QoS 1 with `SIDDHA_MQTT_WAIT_FOR_PUBLISH=true` for reliable validation runs

### Data loss

- QoS 0 does not guarantee delivery
- verify `SIDDHA_MQTT_WAIT_FOR_PUBLISH=true` for strict runs
- inspect ingest logs for batch write errors

---

## Thesis Contribution

This project demonstrates:

- a reproducible distributed IoT ingestion pipeline
- separation of ingestion and AI processing
- structured time-series modeling for ML workloads
- measurable system performance under replayed sensor data
- empirical validation of MQTT QoS and flow-control impact on data consistency
- explicit duplicate-sample identity with `sample_idx` instead of hidden timestamp mutation

---

## Current Status

| Component | Status |
| --- | --- |
| MQTT infrastructure | Stable |
| Ingest service | Stable |
| Dataset validation pipeline | Completed |
| Explorer-based observability | Available |
| Duplicate timestamp handling | Implemented |
| Batch writer | Implemented |
| HAR service | Next |
| Vision gateway | Planned |
