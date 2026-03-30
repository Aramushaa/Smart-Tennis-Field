# Smart Tennis Field

Master Thesis Project - Politecnico di Torino  
Docker-based IoT, time-series, and AI processing pipeline

## Overview

This project implements a Dockerized, distributed, event-driven IoT architecture for ingesting, storing, and processing multi-sensor data in a reproducible and measurable way.

The pipeline is designed to cover the full lifecycle:

```text
Data -> Broker -> Storage -> Processing -> Storage -> API
```

This is not a demo-only system. It is a distributed ingestion infrastructure built for validation, measurement, and later AI processing.

## Objectives

- Ingest high-frequency sensor streams via MQTT
- Persist structured telemetry in InfluxDB 3
- Keep ingestion and processing decoupled
- Support independent processing microservices such as HAR
- Run reproducibly through Docker Compose
- Enable measurable latency and throughput evaluation

## Architecture

```text
Siddha Dataset (Parquet)
        |
        v
siddha-sensor-sim
        |
        v
EMQX (MQTT Broker)
        |
        v
ingest-service (FastAPI)
        |
        v
InfluxDB 3 Core
        ^
        |
har-service (next phase)
        |
        v
Predictions / derived outputs
```

## Architectural Principles

- Event-driven design with MQTT as the backbone
- Strict separation of ingestion and processing
- Structured time-series storage instead of JSON-only blobs
- Microservice-oriented deployment
- Docker-first reproducibility
- Deterministic replay and evaluation paths

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
- Event normalization layer
- InfluxDB 3 integration through line protocol writes

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
- Full replay of 64,697 samples
- Structured storage in `imu_raw`
- Deterministic ordering preserved
- Throughput improved through batching
- Timestamp collision handling added

Key engineering fixes:

- Batch writer thread in ingest service
- Non-blocking MQTT publishing in simulator
- Nanosecond collision offset for duplicate `(device, recording_id, dataset_ts)`

### Phase 3 - HAR Microservice

Planned next:

- Sliding-window extraction from InfluxDB
- ONNX inference integration
- Prediction results written back to InfluxDB

## Services

| Service | Role |
| --- | --- |
| `emqx` | MQTT broker |
| `ingest-service` | MQTT consumer, normalization, persistence |
| `influxdb3` | Time-series database |
| `siddha-sensor-sim` | Dataset-driven simulator |
| `har-service` | Activity recognition processor, next phase |
| `vision-gateway` | Future YOLO-based detection |
| `sensor-gateway` | Future hardware integration |

## Project Structure

```text
docs/
  Architecture.md
  DatasetContract.md
  Phases.md

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

- Each service has its own Dockerfile
- The dataset is mounted through Docker, not hardcoded into the containers

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

```bash
INFLUX_ENABLED=1
INFLUX_TOKEN=YOUR_TOKEN
INFLUX_DATABASE=tennis_phase2_1_qos1
INFLUX_TABLE=events
INFLUX_IMU_TABLE=imu_raw
```

Simulator-related values:

```bash
SIDDHA_MQTT_BROKER_HOST=emqx
SIDDHA_MQTT_BROKER_PORT=1883
SIDDHA_DATASET_PATH=/app/dataset/data.parquet
SIDDHA_REPLAY_MODE=realtime
SIDDHA_REPLAY_SPEED=1.0
```

### 4. Restart services after changing `.env`

```bash
docker compose up -d
```

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

## Data Model

### MQTT Payload

```json
{
  "device": "phone",
  "recording_id": "11",
  "activity_gt": "A",
  "dataset_ts": 0.05,
  "acc_x": 0.0,
  "gyro_x": 0.0,
  "ts": "..."
}
```

### InfluxDB Schema

Measurement:

- `imu_raw`

Tags:

- `device`
- `recording_id`

Fields:

- `acc_x`
- `acc_y`
- `acc_z`
- `gyro_x`
- `gyro_y`
- `gyro_z`
- `dataset_ts`
- `activity_gt`

## Performance Design

### Previous bottlenecks

- One HTTP write per MQTT message
- Blocking simulator publish path
- Timestamp collisions causing point overwrites

### Current approach

- Batch writer thread in ingest service
- Configurable batch size and flush interval
- Non-blocking MQTT publishing in the simulator
- Collision-safe timestamp generation for IMU rows

Result:

- Full dataset ingestion is feasible
- Throughput is substantially higher
- Stored rows remain deterministic and queryable

## Evaluation Metrics

- End-to-end latency
- Ingestion throughput
- HAR processing latency
- Broker restart recovery
- Database reconnection behavior
- CPU usage during replay and inference
- Replay mode comparison

## Troubleshooting

### InfluxDB errors

- Check `INFLUX_TOKEN`
- Check `INFLUX_DATABASE`
- Database names must use only letters, numbers, underscores, or hyphens

### MQTT issues

```bash
docker compose logs emqx ingest-service
```

### Low throughput

- Check `INFLUX_BATCH_SIZE`
- Check `INFLUX_FLUSH_INTERVAL_MS`
- Check simulator replay mode and replay speed

## Thesis Contribution

This project demonstrates:

- A reproducible distributed IoT ingestion pipeline
- Separation of ingestion and AI processing
- Structured time-series modeling for ML workloads
- Measurable system performance under replayed sensor data

## Current Status

| Component | Status |
| --- | --- |
| MQTT | Stable |
| Ingest | Stable |
| Dataset pipeline | Completed |
| HAR service | Next |
| Vision gateway | Planned |
