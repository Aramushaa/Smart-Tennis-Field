# Smart Tennis Field — System Architecture (Post-Phase 2)

## 1. Current Phase Context

**Current Phase:** Phase 2 — Dataset Validation (Completed)

### Implemented

* MQTT infrastructure (EMQX)
* Ingest microservice (FastAPI)
* Structured time-series storage (InfluxDB 3)
* Siddha dataset simulator (real data)
* Batch ingestion pipeline
* Timestamp collision resolution

### Active Services

* emqx (MQTT broker)
* ingest-service (FastAPI + MQTT consumer)
* influxdb3 (time-series DB)
* influxdb3-explorer (query and inspection UI)
* siddha-sensor-sim (dataset replay)

### Data Flow

```
Siddha Dataset (Parquet)
        ↓
siddha-sensor-sim
        ↓
EMQX (MQTT Broker)
        ↓
ingest-service
        ↓
InfluxDB 3 (imu_raw)  ←──── Explorer UI (query + inspection)
```

---

## 2. Architectural Overview

The system follows a **distributed, event-driven microservice architecture** designed for reproducibility and measurable performance.

Core pipeline:

```
Data → Broker → Storage → Processing → Storage → API
```

### Why this architecture?

* **Decoupling:** producers, ingestion, and processing are independent
* **Reproducibility:** full system runs via Docker Compose
* **Scalability:** new consumers (HAR, vision) can be added without changing ingestion
* **Observability:** each stage can be measured independently

---

## 3. Component Breakdown

### 3.1 EMQX (MQTT Broker)

**Role:** Event transport layer

* Handles all sensor message routing
* Supports wildcard topic subscriptions
* Ensures temporal and logical decoupling between producers and consumers:
  * producers do not depend on consumers being available
  * consumers can be added or removed without affecting publishers

**Topics:**

```
tennis/sensor/<device>/events
tennis/camera/<id>/ball
```

**Design reasoning:**

MQTT is preferred over HTTP polling because:

| Option       | Pros                             | Cons                      |
| ------------ | -------------------------------- | ------------------------- |
| MQTT         | low latency, decoupled, scalable | requires broker           |
| HTTP polling | simple                           | inefficient, high latency |

✅ MQTT chosen for real-time IoT system design

---

### 3.2 siddha-sensor-sim (Dataset Simulator)

**Role:** Simulated sensor producer using real dataset

* Reads Parquet dataset
* Publishes IMU samples as MQTT events
* Supports replay modes (realtime / fast)
* Deterministic ordering

**Why simulator instead of direct DB load?**

| Option          | Pros                | Cons                         |
| --------------- | ------------------- | ---------------------------- |
| Direct DB load  | fast                | bypasses system architecture |
| MQTT simulation | realistic, testable | slower                       |

✅ MQTT simulation chosen for thesis validity

---

### 3.3 ingest-service (FastAPI Microservice)

**Role:** Bridge between MQTT and database

Responsibilities:

* Subscribe to MQTT topics using wildcard patterns
* Normalize incoming messages into a consistent event envelope
* Store recent events in an in-memory buffer for debugging
* Route payloads into:
  * generic event storage (`events`)
  * structured IMU storage (`imu_raw`) when fields are present
* Enqueue line protocol writes into a shared write queue
* Flush writes via a background batch writer thread

---

#### Batch Writer Design

**Problem:** 1 HTTP request per message → extremely slow

**Solution:**

* Queue incoming messages
* Flush in batches via background thread

**Why batching matters:**

| Approach          | Pros            | Cons         |
| ----------------- | --------------- | ------------ |
| per-message write | simple          | very slow    |
| batch write       | high throughput | more complex |

✅ Batch writer chosen for scalability + measurable performance

---

### 3.4 InfluxDB 3 Core

**Role:** Time-series storage layer

Stores structured IMU data in measurement:

```
imu_raw
```

#### Schema

**Tags:**

* `device`
* `recording_id`

**Fields:**

* `acc_x`, `acc_y`, `acc_z` — accelerometer axes (float)
* `gyro_x`, `gyro_y`, `gyro_z` — gyroscope axes (float)
* `dataset_ts` — original signal time from the Siddha recording (float)
* `activity_gt` — ground-truth activity label (string)

> ⚠️ `activity_gt` is treated as **metadata (field)**, not as part of the point identity. It does not participate in deduplication or overwrite logic.

**Timestamp:**

* Derived from:
  * a fixed base epoch (`2024-01-01T00:00:00Z`)
  * `dataset_ts` converted to nanoseconds
  * a per-key nanosecond collision offset
* Precision: nanoseconds

### 3.5 Dual Persistence Model (Event vs Signal)

The system maintains two parallel storage paths:

| Layer | Measurement | Purpose |
| --- | --- | --- |
| Event layer | `events` | Generic logging, debugging, full payload trace |
| Signal layer | `imu_raw` | Structured IMU data for ML processing |

This separation ensures:

* observability through event logs
* ML-readiness through structured numeric storage
* decoupling of debugging concerns from processing concerns

---

## 4. Critical Design Decisions

### 4.1 Structured vs JSON Storage

| Option         | Pros                | Cons            |
| -------------- | ------------------- | --------------- |
| JSON-only      | simple              | unusable for ML |
| Structured IMU | ML-ready, queryable | more complex    |

✅ Structured storage chosen

---

### 4.2 Timestamp Strategy

Three timestamps exist in the system:

| Type             | Meaning                          | Source                    |
| ---------------- | -------------------------------- | ------------------------- |
| `dataset_ts`     | Original signal time in recording | Siddha dataset |
| `ts`             | Wall-clock publish time | Simulator at send time |
| Influx timestamp | Storage identity timestamp | Generated from fixed base epoch + `dataset_ts` + collision offset |

**Key distinction:**

* `dataset_ts` represents **semantic sensor time** — it is used for ordering, ML windowing, and signal analysis
* The InfluxDB timestamp is synthetic but deterministic: fixed base epoch + `dataset_ts` + nanosecond collision offset
* `ts` is the wall-clock publish time for distributed-system tracing and latency measurement

**Problem:** The Siddha dataset contains multiple samples that share the same `(device, recording_id, dataset_ts)`. Since InfluxDB identifies points using `measurement + tags + timestamp`, these duplicates silently overwrite each other.

**Solution:** A per-key nanosecond offset is applied via `_next_imu_timestamp_ns()`. Each duplicate at the same base timestamp receives +1ns, +2ns, etc. This preserves all rows without affecting chronological ordering.

---

### 4.3 Microservice Separation

| Option        | Pros            | Cons         |
| ------------- | --------------- | ------------ |
| Monolith      | simple          | not scalable |
| Microservices | scalable, clean | more setup   |

✅ Microservices chosen for thesis clarity

### 4.4 Design Decision: Decoupling Semantics from Storage

The system explicitly separates three independent concerns:

| Concern                | Mechanism                             | Purpose                              |
| ---------------------- | ------------------------------------- | ------------------------------------ |
| Semantic time          | `dataset_ts` field                     | Preserves original recording timeline |
| Storage identity       | InfluxDB timestamp (ns with offset)    | Ensures unique point identity         |
| Transport reliability  | MQTT QoS + `wait_for_publish`          | Controls delivery guarantees          |

This separation ensures:

* correct ML processing (uses `dataset_ts`, not storage timestamp)
* no data overwrite (unique InfluxDB timestamps)
* reproducible ingestion (controlled MQTT behavior)

---

## 5. Data Integrity & Reliability Considerations

The system distinguishes between two independent concerns that both affect data correctness:

### 5.1 Data Identity (Storage Layer)

* Raw IMU samples from the Siddha dataset may share the same `dataset_ts` within a single `(device, recording_id)` group
* InfluxDB identifies points using: `measurement + tags + timestamp`
* To prevent overwriting, a nanosecond offset is applied to duplicate timestamps
* This is handled by `_next_imu_timestamp_ns()` in the ingest service

### 5.2 Data Delivery (Transport Layer)

* Under high-throughput replay (`fast` mode), MQTT QoS 0 with non-blocking publish can lead to significant data loss
* The EMQX broker drops messages when its per-client queue overflows
* Reliable ingestion requires:
  * **QoS 1** — broker-acknowledged delivery
  * **Blocking publish** (`wait_for_publish=true`) — simulator waits for delivery confirmation
* These settings are configurable per experiment via `.env`

### 5.3 Validated Configurations

| Case | Replay Mode | QoS | Wait for Publish | Result           |
| ---- | ----------- | --- | ---------------- | ---------------- |
| A    | `fast`      | 0   | `false`          | ❌ ~88% data loss |
| B    | `fast`      | 1   | `true`           | ✅ 100% correct   |
| C    | `realtime`  | 0   | `false`          | ✅ 100% correct   |
| D    | `realtime`  | 1   | `true`           | ✅ 100% correct   |

### 5.4 Failure Modes Identified

During validation, the following failure modes were observed:

| Failure | Cause | Resolution |
| --- | --- | --- |
| Silent data overwrite | duplicate timestamps | nanosecond offset |
| Data loss in fast replay | QoS 0 + async publish | QoS 1 + `wait_for_publish` |
| Throughput bottleneck | per-message HTTP writes | batch writer |
| Broker overload | ingest slower than publish | batching + QoS tuning |

These findings were critical in transforming the system from a prototype into a validated ingestion pipeline.

---

## 6. Current Limitations

* HAR processing not implemented yet
* No real hardware sensors
* No custom visualization or dashboard yet (Grafana or frontend)
* Basic observability is available through the InfluxDB 3 Explorer UI

These are intentional to ensure infrastructure is validated first.

### 6.1 How to Verify the Architecture

To validate the system behavior:

1. Check ingestion:
   * `GET /stats` to verify IMU row count
2. Check schema:
   * `GET /events/schema`
3. Inspect data:
   * InfluxDB Explorer at `http://localhost:8888`
4. Validate ordering:
   * query `/imu?order_by=dataset_ts`
5. Validate reliability:
   * compare published versus stored rows under different QoS settings

### 6.2 Security Considerations

* InfluxDB tokens are stored in `.env` and never hardcoded
* API inputs such as timestamps are validated before SQL execution
* Internal services communicate via Docker network service names
* Only necessary ports are exposed for development

---

## 7. Next Step — Phase 3

### HAR Service (Planned)

Responsibilities:

* Query sliding windows from InfluxDB
* Run ONNX model
* Write predictions back

New architecture:

```
InfluxDB (raw)
      ↓
HAR Service
      ↓
InfluxDB (predictions)
```

---

## 8. Summary

The system is now:

* Fully Dockerized
* Event-driven
* Structurally decoupled
* Validated with real dataset
* Data integrity verified (timestamp collisions resolved)
* Transport reliability validated (MQTT QoS impact measured)
* Ready for ML processing integration

This architecture provides a solid, thesis-defensible foundation for Phase 3.
