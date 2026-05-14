# Smart Tennis Field — System Architecture

## Current System Context

The project is currently in **Phase 5 — Grafana Visualization**.

Completed phases:

| Phase | Status | Main result |
|---|---|---|
| Phase 0 | Completed | EMQX MQTT broker validated |
| Phase 1 | Completed | FastAPI ingest-service + InfluxDB persistence |
| Phase 2 | Completed | Siddha dataset replay pipeline validated |
| Phase 3 | Completed | HAR microservice with ONNX inference and prediction storage |
| Phase 4 | Completed | Real MetaWear watch pipeline with cleaner + live HAR mode |
| Phase 5 | Current | Grafana dashboards for live and historical visualization |
| Phase 6 | Planned | EEG and ECG dataset-based sensors, storage only, no ML |

The current implemented Phase 3 pipeline is:

```text
Siddha Dataset
→ siddha-sensor-sim
→ EMQX
→ ingest-service
→ InfluxDB: imu_raw_full_rows
→ har-service in DB mode
→ InfluxDB: har_predictions_7_activity
```

The validated Phase 4 pipeline is:

```text
MetaWear Bracelet
→ BLE
→ metawear_bridge
→ EMQX: tennis/watch/raw
→ watch_cleaner_service
→ EMQX: tennis/watch/clean
→ ingest-service
→ InfluxDB: watch_imu_clean

tennis/watch/clean
→ har-service in MQTT mode
→ InfluxDB: real_har_predictions
→ Grafana visualization
```

---

## 1. Architecture Principle

The system follows this thesis-level principle:

```text
Data Source → Protocol Adapter → Broker → Cleaner → Storage / Processing → Visualization
```

The more general system loop remains:

```text
Data → Broker → Storage → Processing → Storage → Visualization
```

However, Phase 4 refines the architecture by inserting a dedicated cleaner between raw sensor acquisition and downstream services.

This separation is important because raw hardware streams are not always safe, complete, or aligned with model expectations.

---

## 2. Main Components

### 2.1 EMQX — MQTT Broker

EMQX is the event transport layer.

Responsibilities:

- Route raw and clean sensor events.
- Decouple producers from consumers.
- Support MQTT wildcard subscriptions.
- Allow multiple consumers to read the same clean topic.

Phase 4 topics:

```text
tennis/watch/raw
tennis/watch/clean
```

Existing Siddha topic:

```text
tennis/sensor/<device>/events
```

Camera topics are removed from the future architecture because camera hardware is not part of the final thesis implementation.

---

### 2.2 siddha-sensor-sim — Dataset Replay Producer

The Siddha simulator remains implemented and valid for reproducible dataset validation.

Flow:

```text
Siddha Parquet Dataset
→ siddha-sensor-sim
→ EMQX
→ ingest-service
→ InfluxDB: imu_raw_full_rows
```

This component is not deleted because it supports:

- reproducible evaluation,
- controlled replay speed,
- known activity labels,
- comparison with real sensor mode.

---

### 2.3 metawear_bridge — BLE to MQTT Protocol Adapter

The MetaWear bracelet does not publish MQTT by itself.

The actual flow is:

```text
MetaWear Bracelet → BLE → metawear_bridge → MQTT
```

The `metawear_bridge` is a protocol adapter.

Responsibilities:

- Connect to the bracelet over BLE.
- Receive accelerometer and gyroscope callbacks.
- Publish raw MetaWear events to MQTT.
- Avoid direct database writes.
- Avoid ML inference.

It publishes raw events to:

```text
tennis/watch/raw
```

The bridge should not contain storage logic or HAR logic. This keeps hardware acquisition separate from processing and persistence.

---

### 2.4 watch_cleaner_service — Sensor-Specific Cleaner

The cleaner is introduced in Phase 4.

Responsibilities:

- Subscribe to raw watch events.
- Validate required values.
- Pair accelerometer and gyroscope samples when needed.
- Normalize timestamps.
- Enforce a consistent sampling assumption.
- Drop incomplete or physically implausible samples.
- Publish canonical clean IMU rows.

Input topic:

```text
tennis/watch/raw
```

Output topic:

```text
tennis/watch/clean
```

The cleaner exists so that ingest-service and HAR do not need to know MetaWear-specific details.

This is the key architectural improvement in Phase 4.

---

### 2.5 ingest-service — Sensor Storage Gateway

The ingest-service remains the storage gateway for clean sensor data.

Responsibilities:

- Subscribe to clean sensor topics.
- Validate storage-safe payloads.
- Write clean sensor readings to InfluxDB.
- Use batching and retry logic.
- Expose health and stats endpoints.

For Phase 4, it stores clean watch rows in:

```text
watch_imu_clean
```

For Phase 2/3 dataset replay, it still stores Siddha rows in:

```text
imu_raw_full_rows
```

Important boundary:

```text
ingest-service stores sensor data.
HAR service stores prediction data.
```

Prediction outputs should not be routed through ingest-service because predictions are produced and owned by the ML service.

---

### 2.6 har-service — Human Activity Recognition Service

The HAR service has two modes.

#### DB Mode — Reproducible Evaluation

Used for Phase 3 and dataset validation.

```text
InfluxDB: imu_raw_full_rows
→ har-service
→ InfluxDB: har_predictions_7_activity
```

This mode is deterministic and easier to reproduce.

#### MQTT Mode — Real-Time Watch Inference

Used for Phase 4 real sensor mode.

```text
EMQX: tennis/watch/clean
→ har-service
→ InfluxDB: real_har_predictions
```

In MQTT mode, HAR keeps an in-memory sliding window buffer and runs ONNX inference when enough clean samples are available.

The service writes predictions directly to InfluxDB because it owns the prediction result.

---

### 2.7 InfluxDB 3 — Time-Series Storage

InfluxDB stores clean sensor inputs and prediction outputs.

Recommended tables:

| Table | Purpose |
|---|---|
| `events` | Generic event log/debug storage |
| `imu_raw_full_rows` | Siddha dataset IMU rows |
| `watch_imu_clean` | Clean real MetaWear watch IMU rows |
| `har_predictions_7_activity` | Phase 3 dataset HAR predictions |
| `real_har_predictions` | Phase 4 real watch predictions |
| `eeg_clean` | Future EEG dataset rows |
| `ecg_clean` | Future ECG dataset rows |

Clean sensor rows and prediction rows are separated deliberately.

Prediction rows should reference the input time window. They should not duplicate the full raw window.

---

### 2.8 Grafana — Visualization Layer

Grafana is the next phase after Phase 4 validation.

Required visualization path:

```text
InfluxDB → Grafana
```

This supports:

- historical prediction timelines,
- confidence over time,
- IMU signal visualization,
- session summaries,
- near-real-time dashboards with auto-refresh.

Optional advanced visualization path:

```text
HAR service → Grafana Live
```

Grafana Live may provide lower latency, but it should be treated as an optional enhancement unless fully verified and implemented.

The required thesis-safe approach is Grafana reading from InfluxDB.

---

## 3. Correct Prediction Path

The correct prediction write path is:

```text
HAR service → InfluxDB: real_har_predictions
```

Not:

```text
HAR service → MQTT → ingest-service → InfluxDB
```

Reason:

- ingest-service owns sensor ingestion;
- HAR service owns prediction generation;
- prediction schemas differ from sensor schemas;
- routing predictions through ingest would make ingest responsible for ML output formats.

This avoids turning the ingest-service into a tightly coupled central monolith.

---

## 4. Why Store Clean IMU and Predictions Separately?

The clean IMU table stores the model input:

```text
watch_imu_clean
```

The prediction table stores model output:

```text
real_har_predictions
```

A prediction row should contain metadata such as:

```text
device
recording_id
predicted_label
confidence
window_start_dataset_ts
window_end_dataset_ts
window_size
window_stride
```

It should not store the full raw input window again.

This design supports:

- reproducibility,
- debugging,
- future model comparison,
- data quality analysis,
- historical visualization.

---

## 5. Edge Computing Position

This project is not a full edge-computing system.

The MetaWear bracelet is a sensor. The laptop or Docker host performs cleaning, storage, and inference.

A true edge deployment would be:

```text
MetaWear → Raspberry Pi gateway → local inference → central storage
```

That is a valid future direction, but it is outside the current thesis scope.

The current choice is centralized local processing because it is:

- more reproducible,
- easier to observe,
- easier to evaluate,
- more suitable for Docker-based thesis validation.

---

## 6. Final Phase 4 Architecture

```text
MetaWear Bracelet (BLE)
        │
        ▼
metawear_bridge
        │
        ▼
EMQX: tennis/watch/raw
        │
        ▼
watch_cleaner_service
        │
        ▼
EMQX: tennis/watch/clean
        │
        ├──────────────────────────┐
        ▼                          ▼
ingest-service              har-service (MQTT mode)
        │                          │
        ▼                          ▼
InfluxDB: watch_imu_clean   InfluxDB: real_har_predictions
                                      │
                                      ▼
                                  Grafana
```

Dataset evaluation remains:

```text
Siddha Dataset
→ siddha-sensor-sim
→ EMQX
→ ingest-service
→ InfluxDB: imu_raw_full_rows
→ har-service (DB mode)
→ InfluxDB: har_predictions_7_activity
```
