# Smart Tennis Field - System Architecture (Post-Phase 2)

## 1. Current Phase Context

**Current Phase:** Phase 2 - Dataset Validation (Completed)

### Implemented

- MQTT infrastructure (EMQX)
- Ingest microservice (FastAPI)
- Structured time-series storage (InfluxDB 3)
- Siddha dataset simulator using real data
- Batch ingestion pipeline
- Explicit duplicate-sample identity handling

### Active Services

- `emqx` (MQTT broker)
- `ingest-service` (FastAPI + MQTT consumer)
- `influxdb3` (time-series database)
- `influxdb3-explorer` (query and inspection UI)
- `siddha-sensor-sim` (dataset replay)

### Data Flow

![Smart Tennis Field data flow](smart_tennis_field_data_flow.svg)

---

## 2. Architectural Overview

The system follows a distributed, event-driven microservice architecture designed for reproducibility and measurable performance.

Core pipeline:

```text
Data -> Broker -> Storage -> Processing -> Storage -> API
```

### Why this architecture?

- **Decoupling:** producers, ingestion, and processing are independent
- **Reproducibility:** the full system runs via Docker Compose
- **Scalability:** new consumers such as HAR or vision services can be added without changing ingestion
- **Observability:** each stage can be measured independently

---

## 3. Component Breakdown

### 3.1 EMQX (MQTT Broker)

**Role:** event transport layer

- routes all sensor messages
- supports wildcard topic subscriptions
- decouples publishers from consumers

**Topics**

```text
tennis/sensor/<device>/events
tennis/camera/<id>/ball
```

**Design reasoning**

MQTT is preferred over HTTP polling because it provides low-latency, decoupled communication that fits an IoT architecture.

### 3.2 siddha-sensor-sim (Dataset Simulator)

**Role:** simulated sensor producer using the Siddha dataset

- reads Parquet data
- publishes IMU samples as MQTT events
- supports `realtime` and `fast` replay
- preserves deterministic ordering

The simulator is used instead of direct database loading so that real data still passes through the broker and ingest pipeline.

### 3.3 ingest-service (FastAPI Microservice)

**Role:** bridge between MQTT and database

Responsibilities:

- subscribe to MQTT topics using wildcard patterns
- normalize incoming messages into a consistent event envelope
- store recent events in memory for debugging
- route payloads into:
  - generic event storage (`events`)
  - structured IMU storage (`imu_raw`)
- enqueue line protocol writes into a shared write queue
- flush writes via a background batch writer thread

#### Batch Writer Design

**Problem:** one HTTP request per message is too slow

**Solution:**

- queue incoming writes
- flush in batches from a background thread

Batching improves throughput while keeping MQTT consumption and persistence decoupled.

### 3.4 InfluxDB 3 Core

**Role:** time-series storage layer

Stores structured IMU data in measurement:

```text
imu_raw
```

### InfluxDB Schema (`imu_raw`)

Measurement: `imu_raw`

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

- derived directly from `dataset_ts`

Important:

InfluxDB identifies a point using:

```text
measurement + tags + time
```

Since `dataset_ts` can be duplicated, `sample_idx` is required to distinguish samples.

This allows multiple points with identical timestamps to coexist without collision.

> `activity_gt` is treated as metadata stored as a field. It is not part of the point identity.

### 3.5 Dual Persistence Model (Event vs Signal)

The system maintains two parallel storage paths:

| Layer | Measurement | Purpose |
| --- | --- | --- |
| Event layer | `events` | Generic logging, debugging, full payload trace |
| Signal layer | `imu_raw` | Structured IMU data for ML processing |

This separation ensures:

- observability through event logs
- ML readiness through structured numeric storage
- decoupling of debugging concerns from processing concerns

---

## 4. Critical Design Decisions

### 4.1 Structured vs JSON Storage

| Option | Pros | Cons |
| --- | --- | --- |
| JSON-only | simple | unusable for ML |
| Structured IMU | ML-ready, queryable | more complex |

Structured storage was selected because later HAR processing requires direct numeric access to sensor channels.

### 4.2 Data Identity Model

The Siddha dataset contains multiple samples sharing the same:

- device
- recording_id
- dataset timestamp (`dataset_ts`)

Therefore, the tuple:

```text
(device, recording_id, dataset_ts)
```

is not sufficient to uniquely identify a data point.

To address this, the system introduces an additional dimension:

- `sample_idx`

This index is assigned during dataset loading using a deterministic grouping and ranking strategy.

Final identity:

```text
(device, recording_id, dataset_ts, sample_idx)
```

This ensures:

- no data loss
- explicit representation of duplicate samples
- deterministic and reproducible replay

### 4.3 Timestamp Semantics

Three time-related values exist in the system:

| Type | Meaning | Source |
| --- | --- | --- |
| `dataset_ts` | Original signal time in the Siddha recording | Dataset |
| `ts` | Wall-clock publish time | Simulator at send time |
| `time` | InfluxDB storage timestamp derived from `dataset_ts` | Ingest pipeline |

Key distinction:

- `dataset_ts` is semantic sensor time
- `ts` is transport-time metadata for tracing and latency analysis
- `time` is the database storage timestamp

These values serve different purposes and are not interchangeable.

### 4.4 Duplicate Handling in Pipeline

Duplicate timestamps are resolved at the earliest stage, inside the dataset loader:

1. the dataset is sorted deterministically
2. rows are grouped by:
   - `device`
   - `recording_id`
   - `timestamp`
3. `sample_idx` is assigned using cumulative count

This value is propagated through:

- MQTT payload
- ingest service
- InfluxDB storage

This design avoids collision at the storage level and preserves all samples.

### 4.5 Design Decision: Explicit vs Implicit Uniqueness

Two approaches were considered:

1. timestamp modification through nanosecond offsets
2. explicit indexing through `sample_idx`

The second approach was selected because:

- it preserves the semantic meaning of time
- it avoids hidden transformations
- it improves observability and debugging
- it ensures deterministic behavior
- it aligns with time-series modeling best practices

### 4.6 Microservice Separation

| Option | Pros | Cons |
| --- | --- | --- |
| Monolith | simple | not scalable |
| Microservices | scalable, clean separation | more setup |

Microservices were chosen because they make thesis evaluation clearer and keep ingestion independent from later processing stages.

### 4.7 Separation of Identity and Delivery Guarantees

The system explicitly separates:

| Concern | Mechanism | Purpose |
| --- | --- | --- |
| Semantic time | `dataset_ts` | Preserve original recording timeline |
| Sample identity | `sample_idx` | Distinguish duplicate samples |
| Storage time | InfluxDB `time` | Support ordered storage |
| Transport reliability | MQTT QoS + `wait_for_publish` | Control delivery guarantees |

This separation makes it possible to reason independently about replay fidelity, storage correctness, and transport reliability.

---

## 5. Data Integrity And Reliability Considerations

The system distinguishes between two independent concerns that affect correctness.

### 5.1 Data Identity (Storage Layer)

- raw IMU samples may share the same `dataset_ts` within one `(device, recording_id)` group
- InfluxDB identifies points using `measurement + tags + time`
- `sample_idx` is required so duplicate samples remain distinct
- identity is established before data reaches the database

### 5.2 Data Delivery (Transport Layer)

- under high-throughput replay, MQTT QoS 0 with non-blocking publish can lead to data loss
- EMQX may drop messages when client queues overflow
- reliable ingestion requires:
  - QoS 1
  - `wait_for_publish=true`

### 5.3 Validated Configurations

| Case | Replay Mode | QoS | Wait for Publish | Result |
| --- | --- | --- | --- | --- |
| A | `fast` | 0 | `false` | high data loss |
| B | `fast` | 1 | `true` | correct ingestion |
| C | `realtime` | 0 | `false` | correct ingestion |
| D | `realtime` | 1 | `true` | correct ingestion |

### 5.4 Failure Modes Identified

| Failure | Cause | Resolution |
| --- | --- | --- |
| Silent data overwrite | duplicate samples with shared timestamp identity | explicit `sample_idx` |
| Data loss in fast replay | QoS 0 + async publish | QoS 1 + `wait_for_publish` |
| Throughput bottleneck | per-message HTTP writes | batch writer |
| Broker overload | ingest slower than publish | batching + QoS tuning |

These findings were critical in transforming the system from a prototype into a validated ingestion pipeline.

---

## 6. Current Limitations

- HAR processing is not implemented yet
- real hardware sensors are not integrated yet
- no custom visualization dashboard exists yet
- observability currently depends on API endpoints and InfluxDB Explorer

These limitations are intentional because the infrastructure was validated first.

### 6.1 How to Verify the Architecture

To validate system behavior:

1. check ingestion with `GET /stats`
2. inspect schema with `GET /events/schema`
3. inspect data in InfluxDB Explorer at `http://localhost:8888`
4. validate ordering with `/imu?order_by=dataset_ts`
5. compare published versus stored rows under different QoS settings

### 6.2 Security Considerations

- InfluxDB tokens are stored in `.env` and never hardcoded
- API inputs are validated before SQL execution
- internal services communicate via Docker service names
- only necessary ports are exposed during development

---

## 7. Next Step - Phase 3

### HAR Service (Planned)

Responsibilities:

- query sliding windows from InfluxDB
- run ONNX inference
- write predictions back

Planned architecture:

```text
InfluxDB (raw)
      |
      v
HAR Service
      |
      v
InfluxDB (predictions)
```

---

## 8. Summary

The system is now:

- fully Dockerized
- event-driven
- structurally decoupled
- validated with a real dataset
- protected against silent overwrite through explicit sample identity
- validated for transport reliability through MQTT experiments
- ready for ML processing integration

This architecture provides a clean and thesis-defensible foundation for Phase 3.
