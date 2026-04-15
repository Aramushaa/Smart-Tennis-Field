# Phases — Smart Tennis Field Roadmap

Each phase depends on the previous one: transport must be validated before persistence, persistence before processing.

| Phase | Status |
| --- | --- |
| Phase 0 — MQTT Infrastructure | Completed |
| Phase 1 — Ingest + Persistence | Completed |
| Phase 2 — Dataset Validation | Completed |
| Phase 3 — HAR Microservice | Next |
| Phase 4 — Real Edge Gateways | Deferred |
| Phase 5 — Domain Semantics | Future |
| Phase 6 — Observability / Evaluation | Ongoing |

---

## Phase 0 — MQTT Infrastructure (Completed)

**Goal:** Validate reliable end-to-end event transport using MQTT in a Dockerized environment.

**Deliverables:**

- EMQX broker in Docker
- Publisher → broker → subscriber verified
- Topic naming convention (`tennis/sensor/+/events`, `tennis/camera/+/ball`)
- JSON payload schema defined
- Basic QoS behavior understood

**Done when:** Message integrity validated, Docker Compose reproducibility confirmed.

---

## Phase 1 — Ingest Service + Persistence (Completed)

**Goal:** Transform MQTT messages into durable, queryable time-series data.

**Deliverables:**

- FastAPI ingest microservice with background MQTT worker
- Event normalization envelope
- In-memory ring buffer for debugging
- InfluxDB 3 integration via line protocol writes and SQL queries
- Token-based authentication
- REST endpoints: `GET /health`, `GET /events`, `POST /publish`

**Done when:** MQTT events persist in InfluxDB across container restarts, time-range queries work, authentication verified.

**Note:** Data identity was not yet fully addressed. Phase 2 finalized the current Siddha identity model with derived session identifiers and preserved duplicate-order metadata.

---

## Phase 2 — Dataset Validation Pipeline (Completed)

**Goal:** Validate the infrastructure using the Siddha multi-sensor dataset instead of synthetic messages.

**Deliverables:**

- `siddha-sensor-sim` microservice: reads Parquet, publishes via MQTT with configurable replay modes, filters, and QoS
- Structured IMU storage in `imu_raw` measurement
- Batch writer thread replacing per-message HTTP writes
- Derived Siddha session identifiers (`<activity>_<id>`) to avoid ambiguity between labeled sampling sessions
- Preserved `sample_idx` metadata for duplicate-order tracking and future schema strengthening
- Validated end-to-end ingestion with ~2M rows

For the `imu_raw` schema, identity model, and validated configurations, see [Architecture.md](Architecture.md).

**Done when:**

- No data loss under validated configurations (QoS 1 + `wait_for_publish=true`)
- Session separation and replay ordering validated under the current Siddha identity model
- Row count matches source dataset
- Replay order preserved
- Pipeline deterministic and reproducible

**Scope boundaries:** Phase 2 does not include ML inference, real hardware, or multi-sensor fusion. Ingestion infrastructure is validated independently before processing.

---

## Phase 3 — HAR Processing Microservice (Next)

**Goal:** Integrate an existing ONNX HAR model as a separate microservice that consumes structured IMU data.

This phase is about integrating an existing ML component into the architecture, not training a new model.

**Deliverables:**

- `har_service` Docker container
- Sliding-window extraction from InfluxDB (DB polling, not MQTT streaming)
- Model input conversion:

```python
accelerometer = {"x": [...], "y": [...], "z": [...]}
gyroscope = {"x": [...], "y": [...], "z": [...]}
```

- ONNX inference using `L2MU_plain_leaky.onnx`
- Predictions written back to InfluxDB

**Data access:** DB polling over MQTT streaming — deterministic, reproducible, easier to evaluate.

**Target metrics:**

- HAR inference latency per window
- End-to-end latency from `dataset_ts` to prediction
- Throughput (windows/second)
- CPU usage under load

**Done when:** ONNX model runs in Docker, predictions stored in a separate measurement, HAR remains decoupled from ingest-service.

---

## Phase 4 — Real Edge Gateways (Deferred)

Real producers are introduced only after infrastructure and processing are stable. The Siddha simulator remains as a deterministic baseline.

### 4A — Sensor Gateway

- `sensor_gateway` microservice reading from real hardware (BLE/UART)
- Publishes to `tennis/sensor/<id>/events`

### 4B — Vision Gateway

- `vision_gateway` microservice with YOLO-based ball detection
- Reads RTSP/USB/video sources
- Publishes to `tennis/camera/<id>/ball`

---

## Phase 5 — Domain Semantics (Future)

Convert low-level telemetry and predictions into tennis-level semantic events (bounce, serve, fault, out).

---

## Phase 6 — Observability and Evaluation (Ongoing)

### Core Metrics

- End-to-end latency (publish → storage)
- Ingestion throughput at various replay speeds
- HAR inference latency
- Broker restart recovery
- Data consistency (published vs stored count)
- MQTT QoS impact on delivery
- Replay mode comparison (`realtime` vs `fast`)

### Methodology

Experiments use controlled configurations (replay mode, QoS, batch size) and measure correctness, latency, throughput, and resource usage for reproducible and comparable results.
