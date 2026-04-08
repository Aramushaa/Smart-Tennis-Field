# Phases — Smart Tennis Field Roadmap (Updated After Phase 2 Validation)

This document defines the evolution of the Smart Tennis Field thesis project from an MQTT transport MVP to a thesis-grade distributed IoT and AI processing system.

Each phase includes:

- goal
- deliverables
- definition of done
- thesis rationale

The project follows an infrastructure-first strategy:

**Data -> Broker -> Storage -> Processing -> Storage -> API**

This ordering is intentional. Transport must be validated before persistence, persistence must be validated before AI processing, and the whole pipeline must remain measurable and reproducible.

---

## Phase Status Convention

Each phase is classified as:

- **Completed:** implemented and validated experimentally
- **Validated:** results measured and reproducible
- **Next:** ready to be implemented
- **Deferred:** intentionally postponed
- **Future:** conceptual only

This convention is used to distinguish design intent from experimentally supported results.

---

## Phase Dependency Model

Each phase depends strictly on the previous one:

| Phase | Depends on | Reason |
| --- | --- | --- |
| Phase 1 | Phase 0 | ingestion requires reliable transport |
| Phase 2 | Phase 1 | dataset validation requires persistence |
| Phase 3 | Phase 2 | HAR requires structured, validated data |
| Phase 4 | Phase 3 | real sensors require stable processing |
| Phase 5 | Phase 3-4 | semantics require reliable predictions and validated producers |

This dependency model keeps scope controlled and prevents later phases from masking failures in earlier layers.

---

## Phase 0 — MQTT Infrastructure (Completed)

### Goal

Validate reliable end-to-end event transport using MQTT in a Dockerized environment.

### Deliverables

- EMQX broker (Dockerized)
- Dummy publisher -> `tennis/sensor/1/events`
- Subscriber confirming message receipt
- Topic naming convention defined
- JSON payload schema defined
- Basic QoS behavior understood

### Definition of Done

- Publisher -> broker -> subscriber verified
- Message integrity validated
- Topic structure documented
- Docker Compose reproducibility confirmed

### Thesis Rationale

This phase establishes the transport layer of the system. It proves that the project has a working event backbone before adding storage or processing logic.

---

## Phase 1 — Ingest Service + Time-Series Persistence (Completed)

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

## Phase 2 — Dataset Validation Pipeline (Completed)

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

- new microservice: `siddha-sensor-sim`
- reads Siddha dataset from Parquet
- validates required columns
- deterministic ordering by recording and timestamp
- publishes rows via MQTT
- supports replay modes: `realtime`, `fast`
- supports optional filters:
  - device
  - activity
  - recording_id
- supports loop and one-pass replay control
- uses Docker volume mount for dataset access

#### Ingest pipeline improvements

- structured IMU storage in InfluxDB
- separate raw measurement for sensor data
- batch writer thread for line protocol writes
- configurable batch size and flush interval
- timestamp collision handling using nanosecond offsets
- improved throughput under dataset load

### Structured IMU Schema

Measurement:

- `imu_raw`

Tags:

- `device`
- `recording_id`

Fields:

- `acc_x`, `acc_y`, `acc_z`
- `gyro_x`, `gyro_y`, `gyro_z`
- `dataset_ts`
- `activity_gt`

### Definition of Done

- structured IMU data stored in InfluxDB
- no data loss under validated configurations: QoS 1 with `wait_for_publish=true`, or validated realtime replay runs
- duplicate timestamps handled via nanosecond offset
- full dataset subset reproducible with row count matching source under validated configurations
- transport reliability validated under different MQTT configurations
- data queryable by device, recording, and time
- replay order preserved
- throughput significantly improved through batching
- published count and stored count reconciled
- pipeline deterministic and reproducible

### Scope Boundaries (Important)

Phase 2 intentionally does **not** include:

- machine learning inference
- real hardware integration
- multi-sensor fusion
- real-time decision logic

This separation ensures that ingestion infrastructure is validated independently before introducing processing complexity.

### Phase 2 Engineering Discoveries

This phase produced the following key findings:

- timestamp collision causes silent overwrite in InfluxDB
- per-message writes cause severe throughput bottlenecks
- MQTT QoS and publish behavior directly affect data integrity
- fast replay exposes transport-layer limits
- batching is required for scalable ingestion

These findings represent core contributions of the infrastructure validation phase.

### Phase 2 Evaluation Extensions

Beyond functional validation, Phase 2 produced the following empirical findings:

- **Timestamp collision detection and resolution:** The Siddha dataset contains multiple rows per `(device, recording_id, dataset_ts)`. Without the nanosecond offset, InfluxDB silently overwrites duplicates. This was measured and resolved.
- **Replay mode comparison:** Fast mode reveals transport-layer limitations that realtime mode can mask through natural inter-message delay.
- **MQTT QoS impact on data integrity:** QoS 0 under high throughput caused major data loss in validation runs. QoS 1 with `wait_for_publish=true` achieved full consistency in the validated runs.

### Phase 2 Conclusion

The ingestion pipeline is now:

- **Functionally correct** under validated configurations
- **Reproducible** through deterministic replay and controlled configuration
- **Robust under controlled conditions** across multiple MQTT and replay combinations

Remaining consideration:

- high-throughput reliability still depends on MQTT configuration, especially QoS and publish flow control

The system is ready for Phase 3.

### Thesis Rationale

This phase proves that the project is not just a demo with fake messages. It validates the infrastructure with real structured sensor data and exposes the engineering issues that appear only under realistic load:

- schema mismatches
- write throughput bottlenecks
- blocking publish behavior
- timestamp collisions
- replay strategy tradeoffs

By solving these, the project becomes a validated ingestion infrastructure rather than a prototype.

---

## Phase 3 — HAR Processing Microservice (Next)

### Goal

Introduce a second microservice that consumes structured raw IMU data and performs human activity recognition using a provided ONNX model.

### Important Principle

The HAR model is already provided.

This phase is **not** about training a new model. It is about integrating an existing ML component into the distributed architecture in a clean and measurable way.

### Required Inputs

- `L2MU_plain_leaky.onnx`
- `labels.txt`
- `inference_engine.py`

### Planned Deliverables

- `har_service` Docker container
- reads sliding windows from InfluxDB
- converts rows into model input dictionaries:

```python
accelerometer = {"x": [...], "y": [...], "z": [...]}
gyroscope = {"x": [...], "y": [...], "z": [...]}
```

- runs ONNX inference
- writes predicted labels back into InfluxDB
- exposes prediction results through the broader API layer if needed

### HAR Data Access Strategy

HAR service will retrieve data using database queries, not MQTT streams.

| Option | Pros | Cons |
| --- | --- | --- |
| MQTT streaming | low latency | hard to debug and replay |
| DB polling | reproducible, stable | slightly higher latency |

Selected:

- DB polling

Reason:

- deterministic replay
- easier evaluation
- better alignment with dataset-based experiments

### Planned Processing Loop

```text
InfluxDB (raw sensor data)
          ↓
      har-service
          ↓
InfluxDB (predictions)
```

### Target Metrics (Phase 3)

- HAR inference latency per window in milliseconds
- end-to-end latency from `dataset_ts` to prediction
- throughput in windows per second
- CPU usage under load

### Security Considerations

- ONNX model loaded locally inside the container
- no direct MQTT exposure to HAR service
- database access controlled via token

### Definition of Done

- ONNX model runs inside Docker
- sliding window queries implemented
- model input conversion validated
- predictions stored in a separate measurement or table
- target metrics measured
- HAR remains fully decoupled from `ingest-service`

### Thesis Rationale

This phase demonstrates the core thesis loop:

**Storage -> Processing -> Storage**

It proves that the architecture supports AI integration without coupling ML logic into the ingestion service.

---

## Phase 4 — Real Edge Gateways (Deferred Until After HAR)

This phase introduces real producers only after the infrastructure and processing pipeline are stable.

The Siddha simulator remains part of the system even after real sensors are introduced, as it provides a deterministic baseline for testing and evaluation.

### Phase 4A — Sensor Gateway

#### Goal

Integrate real sensor producers alongside the simulator.

#### Deliverables

- `sensor_gateway` microservice
- reads from real hardware such as BLE or UART
- publishes to `tennis/sensor/<id>/events`

#### Definition of Done

- real sensor data stored in InfluxDB
- timestamp synchronization strategy documented
- gateway behaves as a proper producer in the same architecture

### Phase 4B — Vision Gateway

#### Goal

Add computer vision-based event producers.

#### Deliverables

- `vision_gateway` microservice
- reads RTSP, USB, or video source
- performs YOLO-based ball detection
- publishes to `tennis/camera/<id>/ball`

#### Definition of Done

- ball detections stored in the database
- frame processing latency measured
- publish rate stable under test

### Thesis Rationale

Edge gateways are intentionally deferred until after the infrastructure is validated, so experimental AI and hardware do not get mixed into an unstable core pipeline.

---

## Phase 5 — Domain Semantics / Rules Layer (Future)

### Goal

Convert low-level telemetry and predictions into tennis-level semantic events.

### Potential Deliverables

- `rules-engine` microservice
- multi-stream correlation
- detection of tennis semantics such as:
  - bounce
  - valid serve or fault
  - out event
  - alert generation

### Thesis Rationale

This phase studies distributed time-window alignment and semantic event derivation across multiple streams.

---

## Phase 6 — Observability and Evaluation (Validated / Ongoing)

This phase is partly continuous and partly final-thesis evaluation.

### Core Metrics to Measure

- end-to-end latency from publish to storage
- ingestion throughput at various replay speeds
- HAR inference latency
- broker restart recovery
- database reconnection behavior
- CPU usage of processing services
- replay mode comparison: `realtime` vs `fast`
- container isolation behavior
- data consistency: published count vs stored count
- MQTT QoS impact on delivery reliability
- timestamp collision rate in dataset

### Evaluation Methodology

Experiments will be conducted under controlled configurations:

- replay mode: fast vs realtime
- MQTT QoS level
- batch size
- processing load

Each experiment will measure:

- correctness: row count match
- latency
- throughput
- resource usage

This ensures that results are reproducible and comparable.

### Why This Phase Matters

The thesis contribution depends not only on architecture existing, but on it being measurable and reproducible.

---

## Architectural Maturity Transition

The project evolves across phases as follows:

| Stage | Description |
| --- | --- |
| Phase 0-1 | Prototype infrastructure |
| Phase 2 | Validated ingestion system |
| Phase 3 | Processing-enabled system |
| Phase 4+ | Real-world deployment |

After Phase 2, the system is no longer just a prototype but a validated distributed ingestion infrastructure.

---

## Summary of Current Status

| Phase | Status |
| --- | --- |
| Phase 0 — MQTT Infrastructure | Completed |
| Phase 1 — Ingest + Persistence | Completed |
| Phase 2 — Dataset Validation | Completed |
| Phase 3 — HAR Microservice | Next |
| Phase 4 — Real Edge Gateways | Deferred |
| Phase 5 — Domain Semantics | Future |
| Phase 6 — Observability / Evaluation | Validated / Ongoing |

---

## Final Note

The system has already crossed an important threshold:

It is no longer just an MQTT prototype. It is now a **validated distributed ingestion infrastructure**.

That means the focus can now shift from debugging ingestion basics to integrating and evaluating processing services in a controlled way.
