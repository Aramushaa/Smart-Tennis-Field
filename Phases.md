# 🎾 Phases — Smart Tennis Field Roadmap (Updated — Infrastructure-First Version)

This file defines the evolution from MQTT MVP to a thesis-grade distributed IoT + AI processing system.

Each phase includes:
- Goal
- Deliverables
- Definition of Done
- Notes (Thesis Rationale)

## ✅ Phase 0 — MQTT Infrastructure (Completed)

Goal: Validate reliable end-to-end event transport using MQTT in a Dockerized environment.

Deliverables:
- EMQX broker (Dockerized)
- Dummy publisher -> `tennis/sensor/1/events`
- Subscriber confirming message receipt
- Topic naming convention defined
- JSON payload schema defined
- QoS understanding documented

Definition of Done:
- Publisher -> broker -> subscriber verified
- Message integrity validated
- Topic structure documented
- Docker Compose reproducibility confirmed

Notes (Thesis Rationale):
- This phase validates transport-layer reliability before persistence or AI logic.
- It establishes MQTT as the system’s event backbone.

## ✅ Phase 1 — Ingest Service + Time-Series Persistence (Completed)

Goal: Transform MQTT messages into durable, queryable time-series data.

Deliverables:
- FastAPI ingest microservice
- Background MQTT worker (lifecycle managed via FastAPI lifespan)
- Event normalization envelope
```json
{
  "ts": "...",
  "topic": "...",
  "source": "mqtt",
  "payload": {"...": "..."}
}
```
- In-memory ring buffer (debug)
- InfluxDB 3 Core integration via `/api/v3/write_lp`
- SQL query via `/api/v3/query_sql`
- Token-based authentication
- Docker Compose orchestration

Definition of Done:
- MQTT events written to InfluxDB 3
- Data persists across container restarts
- Time-range queries return correct data
- Token-based authentication verified
- Schema with tags: `stream`, `source_id`
- Field: `payload` (JSON string)

Notes (Thesis Rationale):
- This phase establishes decoupled ingestion, durable storage, and queryable time-series architecture.
- It transforms the project into a real distributed ingestion system.

## 🚀 Phase 2 — Dataset Validation Pipeline (New Core Phase)

This replaces the previous “Real Producers” phase.

Goal: Validate the infrastructure using a real multi-sensor dataset instead of synthetic data. This is the first thesis-critical validation step.

### Phase 2A — Siddha Dataset Sensor Simulation

Goal: Simulate real sensor streams using the Siddha dataset.

Deliverables:
- New microservice: `siddha-sensor-sim`
- Reads Siddha dataset (offline source)
- Publishes rows via MQTT
- Simulates realistic timing (streamed, not bulk dump)
- Configurable publish rate

Pipeline:
```
Siddha Dataset
      ↓
EMQX (MQTT Broker)
      ↓
Ingest Service
      ↓
InfluxDB 3
```

Definition of Done:
- Real dataset fully ingested
- Data queryable via REST
- Throughput measured
- No message loss
- End-to-end latency measurable

Notes (Thesis Rationale):
- This phase proves the pipeline is not demo-only.
- It handles real structured multi-sensor data.
- It is reproducible and measurable.
- This transforms the project into a validated IoT ingestion infrastructure.

## 🚀 Phase 3 — HAR Processing Microservice (New Processing Layer)

Goal: Introduce a second microservice that consumes time-series data and performs activity recognition.

### Phase 3A — HAR Service

Deliverables:
- `har-service` Docker container
- Reads sliding windows from InfluxDB
- Runs activity recognition algorithm
- Writes predicted labels back to InfluxDB
- Results queryable via REST

Processing Loop:
```
InfluxDB (raw sensor data)
          ↓
   HAR Service
          ↓
InfluxDB (labeled results)
```

Definition of Done:
- Activity labels generated from real dataset
- Labels stored in DB
- Processing latency measured
- Sliding window logic documented
- System remains decoupled

Notes (Thesis Rationale):
- This phase demonstrates data -> storage -> processing -> storage loop.
- It validates microservice separation.
- It integrates AI without coupling to ingestion.
- This is the core distributed systems contribution.

## 🔮 Phase 4 — Real Edge Gateways (Deferred After Validation)

Now that infrastructure is validated, we introduce physical/AI producers.

### Phase 4A — Sensor Gateway (ST AIoT Craft)

Deliverables:
- `sensor-gateway` service
- Reads real hardware output (BLE/UART/etc.)
- Publishes to `tennis/sensor/<id>/events`

Definition of Done:
- Real sensor data stored in DB
- Timestamp synchronization validated
- Edge vs server timestamp strategy documented

### Phase 4B — Vision Gateway (YOLO)

Deliverables:
- `vision-gateway` service
- Reads RTSP / USB / video file
- YOLO-based ball detection
- Publishes to `tennis/camera/<id>/ball`

Definition of Done:
- Ball detections stored in DB
- Publish rate stable
- Frame processing latency measured
- GPU/CPU usage documented

Notes (Thesis Rationale):
- Vision and hardware are added only after infrastructure stability, dataset validation, and processing microservice proof.
- This avoids coupling experimental AI to unstable infrastructure.

## 🔬 Phase 5 — Domain Semantics Layer (Rules Engine)

Goal: Convert telemetry + HAR output into tennis-level events.

Deliverables:
- `rules-engine` microservice
- Multi-stream time correlation
- Detect: bounce, serve valid/fault, out
- Publishes alerts to `tennis/alerts/<type>`

Definition of Done:
- Deterministic rule evaluation
- Reproducible alerts
- Multi-stream window alignment documented

Notes (Thesis Rationale):
- This is where distributed correlation and time-window alignment are studied.

## 🧭 Phase 6 — Control Unit (System Orchestration)

Goal: Introduce system-level state and control plane.

Deliverables:
- `control-unit` service
- Match states: idle, warmup, match, maintenance
- Publishes commands
- Heartbeat monitoring

Definition of Done:
- Services respond to commands
- System mode changes behavior
- Failure scenarios handled

## 📊 Phase 7 — Observability Layer

Goal: Make the system measurable and visible.

### Phase 7A — Grafana MVP

Deliverables:
- InfluxDB datasource
- Panels: events per minute, stream breakdown, HAR label distribution, latency metrics

Definition of Done:
- Real-time ingestion visible
- Historical exploration possible

### Phase 7B — Custom Dashboard (Optional)

Deliverables:
- React/Next.js UI
- WebSocket live feed
- Event replay

## 🔐 Phase 8 — Security Layer

Goal: Secure distributed microservices.

Deliverables:
- JWT authentication
- Role-based access
- MQTT ACL (optional)
- Secured REST endpoints

Definition of Done:
- Unauthorized access blocked
- Roles enforced

## 🧪 Phase 9 — Thesis Evaluation and Validation

Goal: Produce measurable, reproducible academic results.

Deliverables:
- Infrastructure metrics: end-to-end latency, throughput under load, broker restart behavior, DB reconnection logic, service restart recovery
- Processing metrics: HAR inference time, sliding window size impact, CPU usage, memory usage
- Edge AI metrics (if implemented): YOLO FPS, GPU utilization, publish rate stability
- Documentation: architecture diagrams, event schema specification, Docker deployment guide, limitations and tradeoffs, future work

Definition of Done:
- Fully reproducible Docker deployment
- Measured performance metrics
- Infrastructure validated on real dataset
- Processing microservice validated
- Academic documentation ready
