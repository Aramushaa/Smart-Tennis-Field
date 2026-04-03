# 🎾 Phases — Smart Tennis Field Roadmap (Updated After Phase 2 Validation)

This document defines the evolution of the Smart Tennis Field thesis project from an MQTT transport MVP to a thesis-grade distributed IoT + AI processing system.

Each phase includes:

- goal
- deliverables
- definition of done
- thesis rationale

The project follows an infrastructure-first strategy:

**Data → Broker → Storage → Processing → Storage → API**

This ordering is intentional. Transport must be validated before persistence, persistence must be validated before AI processing, and the whole pipeline must remain measurable and reproducible.

---

## ✅ Phase 0 — MQTT Infrastructure (Completed)

### Goal

Validate reliable end-to-end event transport using MQTT in a Dockerized environment.

### Deliverables

- EMQX broker (Dockerized)
- Dummy publisher → `tennis/sensor/1/events`
- Subscriber confirming message receipt
- Topic naming convention defined
- JSON payload schema defined
- Basic QoS behavior understood

### Definition of Done

- Publisher → broker → subscriber verified
- Message integrity validated
- Topic structure documented
- Docker Compose reproducibility confirmed

### Thesis Rationale

This phase establishes the transport layer of the system. It proves that the project has a working event backbone before adding storage or processing logic.

---

## ✅ Phase 1 — Ingest Service + Time-Series Persistence (Completed)

### Goal

Transform MQTT messages into durable, queryable time-series data.

### Deliverables

- FastAPI ingest microservice
- Background MQTT worker
- Event normalization envelope
- In-memory ring buffer for debugging
- InfluxDB 3 Core integration via `/api/v3/write_lp`
- SQL query support via `/api/v3/query_sql`
- Token-based authentication
- Docker Compose orchestration
- REST endpoints:
  - `GET /health`
  - `GET /events`
  - `POST /publish`

### Event Envelope

```json
{
  "ts": "...",
  "topic": "...",
  "source": "mqtt",
  "payload": { "...": "..." }
}
```

### Definition of Done

- MQTT events written to InfluxDB 3
- Data persists across container restarts
- Time-range queries work correctly
- Token-based authentication verified
- Generic event schema established:
  - tags: `stream`, `source_id`
  - field: `payload`

### Thesis Rationale

This phase transforms the project from a transport demo into a real ingestion and persistence system. It establishes durable storage, queryability, and a proper API-facing ingest layer.

---

## ✅ Phase 2 — Dataset Validation Pipeline (Completed)

### Goal

Validate the distributed infrastructure using a real multi-sensor dataset instead of synthetic messages.

This is the first thesis-critical validation phase.

### Phase 2 Pipeline

```text
Siddha Dataset (Parquet)
        ↓
siddha-sensor-sim
        ↓
EMQX (MQTT Broker)
        ↓
ingest-service
        ↓
InfluxDB 3 (structured IMU storage)
```

### Deliverables

#### Siddha simulator

- New microservice: `siddha-sensor-sim`
- Reads Siddha dataset from Parquet
- Validates required columns
- Deterministic ordering by recording and timestamp
- Publishes rows via MQTT
- Supports replay modes (`realtime`, `fast`)
- Supports optional filters:
  - device
  - activity
  - recording_id

- Supports loop / one-pass replay control
- Uses Docker volume mount for dataset access

#### Ingest pipeline improvements

- Structured IMU storage in InfluxDB
- Separate raw measurement for sensor data
- Batch writer thread for line protocol writes
- Configurable batch size and flush interval
- Timestamp collision handling using nanosecond offsets
- Improved throughput under dataset load

### Structured IMU schema

Measurement:

- `imu_raw` (or project-wide unified equivalent)

Tags:

- `device`
- `recording_id`

Fields:

- `acc_x`, `acc_y`, `acc_z`
- `gyro_x`, `gyro_y`, `gyro_z`
- `dataset_ts`
- `activity_gt`

### Definition of Done

- ✔ Structured IMU data stored in InfluxDB
- ✔ No data loss under controlled replay conditions
- ✔ Duplicate timestamps handled via nanosecond offset
- ✔ Full dataset subset reproducible (row count matches source)
- ✔ Transport reliability validated under different MQTT configurations
- ✔ Data queryable by device / recording / time
- ✔ Replay order preserved
- ✔ Throughput significantly improved through batching
- ✔ Published count and stored count reconciled
- ✔ Pipeline deterministic and reproducible

### Phase 2 Evaluation Extensions

Beyond functional validation, Phase 2 produced the following empirical findings:

- **Timestamp collision detection and resolution:** The Siddha dataset contains multiple rows per `(device, recording_id, dataset_ts)`. Without the nanosecond offset, InfluxDB silently overwrites duplicates. This was measured and resolved.
- **Replay mode comparison (fast vs realtime):** Fast mode reveals transport-layer limitations that realtime mode masks due to natural inter-message delay.
- **MQTT QoS impact on data integrity:** QoS 0 under high throughput causes ~88% data loss. QoS 1 with `wait_for_publish` achieves 100% consistency.

### Phase 2 Conclusion

The ingestion pipeline is now:

- **Functionally correct** — all published samples are stored without silent loss
- **Reproducible** — deterministic replay with controlled configuration
- **Robust under controlled conditions** — validated across multiple MQTT/replay combinations

Remaining consideration:
- High-throughput reliability depends on MQTT configuration (QoS and publish flow control)

The system is ready for Phase 3 (HAR processing).

### Thesis Rationale

This phase proves that the project is not just a demo with fake messages. It validates the infrastructure with real structured sensor data and exposes the kinds of engineering issues that appear only under realistic load:

- schema mismatches
- write throughput bottlenecks
- blocking publish behavior
- timestamp collisions
- replay strategy tradeoffs

By solving these, the project becomes a validated ingestion infrastructure rather than a prototype.

---

## 🚀 Phase 3 — HAR Processing Microservice (Next Phase)

### Goal

Introduce a second microservice that consumes structured raw IMU data and performs human activity recognition using a provided ONNX model.

### Important principle

The HAR model is already provided.

This phase is **not** about training a new model.
It is about integrating an existing ML component into the distributed architecture in a clean and measurable way.

### Required Inputs

- `L2MU_plain_leaky.onnx`
- `labels.txt`
- `inference_engine.py`

### Planned Deliverables

- `har_service` Docker container
- Reads sliding windows from InfluxDB
- Converts rows into model input dictionaries:

```python
accelerometer = {"x": [...], "y": [...], "z": [...]}
gyroscope = {"x": [...], "y": [...], "z": [...]}
```

- Runs ONNX inference
- Writes predicted labels back into InfluxDB
- Exposes prediction results through the broader API layer if needed

### Planned Processing Loop

```text
InfluxDB (raw sensor data)
          ↓
      har-service
          ↓
InfluxDB (predictions)
```

### Definition of Done

- ONNX model runs inside Docker
- Sliding window queries implemented
- Model input conversion validated
- Predictions stored in a separate measurement/table
- Processing latency measurable
- HAR remains fully decoupled from ingest-service

### Thesis Rationale

This phase demonstrates the core thesis loop:

**Storage → Processing → Storage**

It proves that the architecture supports AI integration without coupling ML logic into the ingestion service.

---

## 🔮 Phase 4 — Real Edge Gateways (Deferred Until After HAR)

This phase introduces real producers only after the infrastructure and processing pipeline are stable.

### Phase 4A — Sensor Gateway

#### Goal

Replace the dataset simulator with real physical sensor integration.

#### Deliverables

- `sensor_gateway` microservice
- Reads from real hardware (BLE / UART / etc.)
- Publishes to `tennis/sensor/<id>/events`

#### Definition of Done

- Real sensor data stored in InfluxDB
- Timestamp synchronization strategy documented
- Gateway behaves as a proper producer in the same architecture

### Phase 4B — Vision Gateway

#### Goal

Add computer vision-based event producers.

#### Deliverables

- `vision_gateway` microservice
- Reads RTSP / USB / video source
- Performs YOLO-based ball detection
- Publishes to `tennis/camera/<id>/ball`

#### Definition of Done

- Ball detections stored in DB
- Frame processing latency measured
- Publish rate stable under test

### Thesis Rationale

Edge gateways are intentionally deferred until after the infrastructure is validated, so experimental AI and hardware do not get mixed into an unstable core pipeline.

---

## 🔬 Phase 5 — Domain Semantics / Rules Layer (Future)

### Goal

Convert low-level telemetry and predictions into tennis-level semantic events.

### Potential Deliverables

- `rules-engine` microservice
- Multi-stream correlation
- Detection of tennis semantics such as:
  - bounce
  - valid serve / fault
  - out event
  - alert generation

### Thesis Rationale

This phase would study distributed time-window alignment and semantic event derivation across multiple streams.

---

## 📊 Phase 6 — Observability and Evaluation (Cross-Cutting)

This phase is partly continuous and partly final-thesis evaluation.

### Core metrics to measure

- end-to-end latency (publish → storage)
- ingestion throughput (messages/sec at various replay speeds)
- HAR inference latency
- broker restart recovery
- DB reconnection behavior
- CPU usage of processing services
- replay mode comparison (`realtime` vs `fast`)
- container isolation behavior
- **data consistency** (published count vs stored count)
- **MQTT QoS impact** on delivery reliability
- **timestamp collision rate** in dataset

### Why this phase matters

The thesis contribution depends not only on architecture existing, but on it being measurable and reproducible.

---

## 🧭 Summary of Current Status

| Phase                                | Status       |
| ------------------------------------ | ------------ |
| Phase 0 — MQTT Infrastructure        | ✅ Completed |
| Phase 1 — Ingest + Persistence       | ✅ Completed |
| Phase 2 — Dataset Validation         | ✅ Completed |
| Phase 3 — HAR Microservice           | 🚀 Next      |
| Phase 4 — Real Edge Gateways         | ⏳ Deferred  |
| Phase 5 — Domain Semantics           | ⏳ Future    |
| Phase 6 — Observability / Evaluation | 🔄 Ongoing   |

---

## Final Note

The system has already crossed an important threshold:

It is no longer just an MQTT prototype.
It is now a **validated distributed ingestion infrastructure**.

That means the focus can now shift from debugging ingestion basics to integrating and evaluating processing services in a controlled way.
