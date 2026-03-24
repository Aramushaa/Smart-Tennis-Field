# 🎾 Smart Tennis Field — Distributed MQTT Time-Series Infrastructure

Master Thesis Project
Docker-based IoT + Time-Series + AI Processing Pipeline

## 📖 Overview

This project implements a Dockerized, distributed, event-driven IoT infrastructure for collecting, storing, and processing multi-sensor data.

The system is designed to:
- Ingest real-time sensor streams via MQTT
- Persist them in a time-series database (InfluxDB 3 Core)
- Process them using independent microservices (HAR, future AI)
- Expose results via REST API
- Remain reproducible and measurable

This is not a demo-only project.
It is a validated distributed pipeline architecture.

## 🏗 Core Architecture

```
Dataset / Sensor Gateway
            ↓
        EMQX (MQTT Broker)
            ↓
      Ingest Service (FastAPI)
            ↓
       InfluxDB 3 Core
            ↑
      HAR Microservice
            ↓
         REST API
```

Architectural Principles:
- Event-driven (MQTT backbone)
- Ingestion separated from processing
- Time-series persistence layer
- Independent AI microservices
- Fully Dockerized and reproducible

## 🚀 Current Implemented Phases

✅ Phase 0 — MQTT Infrastructure
- EMQX broker (Dockerized)
- Publisher -> `tennis/sensor/1/events`
- Subscriber verification
- Topic naming conventions defined
- JSON payload schema defined

✅ Phase 1 — Ingest + Time-Series Persistence
- FastAPI ingest microservice
- Background MQTT worker
- Event normalization envelope
```json
{
  "ts": "...",
  "topic": "...",
  "source": "mqtt",
  "payload": {"...": "..."}
}
```
- InfluxDB 3 Core integration
- Line protocol writes (`/api/v3/write_lp`)
- SQL query endpoint (`/api/v3/query_sql`)
- Token-based authentication
- Time-range REST queries

🚀 Phase 2 — Dataset Validation (Infrastructure Validation)
- Siddha dataset sensor simulator
- Real multi-sensor streaming via MQTT
- Measurable ingestion throughput
- End-to-end latency validation

This phase validates the pipeline using real structured sensor data.

🚀 Phase 3 — HAR Processing Microservice
- Independent Docker container
- Reads sliding time windows from InfluxDB
- Runs activity recognition algorithm
- Writes classification labels back to InfluxDB

Processing loop:

```
Raw Sensor Data -> InfluxDB -> HAR Service -> InfluxDB (Labeled Results)
```

## 🧩 Services

| Service | Role |
| --- | --- |
| EMQX | MQTT broker |
| ingest-service | MQTT subscriber + normalization + persistence |
| influxdb3 | Time-series database |
| siddha-sensor-sim | Siddha dataset MQTT replay simulator |
| har-service | Activity recognition processor |
| vision-gateway | (Future) YOLO-based detection |
| sensor-gateway | (Future) Real hardware gateway |

## ⚙️ Quickstart (Docker Compose)

1. Start all services:
```bash
docker compose up -d --build
```

2. Create InfluxDB admin token:
```bash
docker exec -it influxdb3 influxdb3 create token --admin
```

3. Add tokens and config to `.env`:
```bash
INFLUX_ENABLED=1
INFLUX_TOKEN=YOUR_TOKEN

# Siddha Sensor Sim Configuration
SIDDHA_MQTT_BROKER_HOST=emqx
SIDDHA_MQTT_BROKER_PORT=1883
SIDDHA_MQTT_TOPIC_PREFIX=tennis/sensor
SIDDHA_DATASET_PATH=/app/dataset/data.parquet
SIDDHA_REPLAY_MODE=realtime
SIDDHA_REPLAY_SPEED=1.0
```

4. Restart services to load `.env`:
```bash
docker compose up -d
```

## 🌐 Endpoints

| Component | URL |
| --- | --- |
| EMQX Dashboard | http://localhost:18083 |
| InfluxDB 3 Core | http://localhost:8181 |
| Ingest API | http://localhost:8000 |

## 🔌 REST API Routes

- `GET /health`
- `GET /events?limit=10`
- `GET /events?from=...&to=...`
- `POST /publish`

## 📡 MQTT Configuration

| Host Port | Container Port |
| --- | --- |
| 2883 | 1883 |

If connecting from host machine, use `localhost:2883`.

## 📂 Project Structure

```
docs/
  Phases.md

services/
  ingest_service/
    app/
      main.py
      mqtt.py
      influx.py
      config.py
    Dockerfile
    requirements.txt

  siddha_sensor_sim/
    app/
      main.py
      publisher.py
      dataset_loader.py
      config.py
    Dockerfile
    requirements.txt

infra/
  docker-compose.yml

.env.example
README.md
```

## 📊 Thesis Evaluation Focus

The system is designed to measure:
- End-to-end latency
- Throughput under load
- Broker restart recovery
- DB reconnection logic
- HAR processing latency
- Container isolation behavior
- Resource usage (CPU/GPU)

This ensures the system is academically defensible.

## 🛑 Stop Services

```bash
docker compose down
```

Do not use `docker compose down -v` unless you want to delete the InfluxDB volume and regenerate tokens.

## 🛠 Troubleshooting

EMQX Port Conflict
- Change host port in `docker-compose.yml`: `2883:1883`

InfluxDB Auth Errors
- Verify `INFLUX_TOKEN` in `.env`
- Restart ingest-service
- If volume was deleted, regenerate token

MQTT Connection Issues
- `docker compose ps`
- `docker compose logs emqx ingest-service`

## 🧠 Thesis Direction

This project evolves from MQTT ingestion demo into a validated, reproducible, Docker-based distributed IoT + AI processing infrastructure.
Infrastructure validation precedes physical hardware and YOLO integration.

## 📌 Current Status

- MQTT Infrastructure: Stable
- Ingest + Persistence: Stable
- Dataset Validation: In Progress
- HAR Microservice: In Progress
- Vision Gateway: Planned
