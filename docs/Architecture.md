# 🏗 Smart Tennis Field — System Architecture (Post-Phase 2)

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
InfluxDB 3 (imu_raw)
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
* Ensures decoupling between producers and consumers

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

* Subscribe to MQTT topics
* Parse and validate payloads
* Convert to line protocol
* Batch-write to InfluxDB

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

* device
* recording_id

**Fields:**

* acc_x, acc_y, acc_z
* gyro_x, gyro_y, gyro_z
* dataset_ts
* activity_gt

**Timestamp:**

* ingestion time (with nanosecond offsets)

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

Three timestamps exist:

| Type             | Meaning              |
| ---------------- | -------------------- |
| dataset_ts       | original signal time |
| ts               | publish time         |
| Influx timestamp | ingestion time       |

**Problem:** duplicate timestamps → overwrite

**Solution:** nanosecond offsets

---

### 4.3 Microservice Separation

| Option        | Pros            | Cons         |
| ------------- | --------------- | ------------ |
| Monolith      | simple          | not scalable |
| Microservices | scalable, clean | more setup   |

✅ Microservices chosen for thesis clarity

---

## 5. Current Limitations

* HAR processing not implemented yet
* No real hardware sensors
* No visualization layer yet

These are intentional to ensure infrastructure is validated first.

---

## 6. Next Step — Phase 3

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

## 7. Summary

The system is now:

* Fully Dockerized
* Event-driven
* Structurally decoupled
* Validated with real dataset
* Ready for ML processing integration

This architecture provides a solid, thesis-defensible foundation for Phase 3.
