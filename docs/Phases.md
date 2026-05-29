# Phases — Smart Tennis Field Roadmap

This roadmap reflects the completed Phase 5 visualization layer and the completed Phase 6 EEG/ECG extension.

The project validates transport, persistence, dataset replay, HAR inference, live watch integration, Grafana visualization, and multi-source extensibility.

---

## Phase Overview

| Phase | Status | Goal |
|---|---|---|
| Phase 0 — MQTT Infrastructure | Completed | Validate broker-based event transport |
| Phase 1 — Ingest + Persistence | Completed | Store MQTT data in InfluxDB |
| Phase 2 — Dataset Validation | Completed | Replay Siddha dataset through the full pipeline |
| Phase 3 — HAR Microservice | Completed | Run ONNX HAR inference and store predictions |
| Phase 4 — Real Watch Pipeline | Completed | Integrate MetaWear watch with cleaner + real-time HAR |
| Phase 5 — Grafana Visualization | Completed | Visualize live IMU data and HAR predictions from InfluxDB |
| Phase 6 — EEG/ECG Dataset Sources | Completed | Add two heterogeneous dataset-based sensors, storage and visualization only, no ML |

Camera-based features are removed from future phases because no camera hardware is available and camera tracking is not part of the final thesis contribution.

---

## Phase 0 — MQTT Infrastructure

**Status:** Completed

### Goal

Validate the event backbone using MQTT and Docker.

### Implemented

- EMQX broker.
- Publisher/subscriber validation.
- Docker Compose networking.
- MQTT host/port distinction:
  - inside Docker: `emqx:1883`
  - from host: `localhost:2883`

### Thesis Reasoning

Before storing or processing sensor data, the transport layer had to be proven reliable and reproducible.

---

## Phase 1 — Ingest + Persistence

**Status:** Completed

### Goal

Persist MQTT messages in InfluxDB through an ingest microservice.

### Implemented

- FastAPI ingest-service.
- MQTT background subscriber.
- InfluxDB 3 write integration.
- Event envelope normalization.
- Batch writer with queue.
- Health/stat endpoints.

### Important Design Choice

The ingest-service is the gateway for sensor storage, not a universal writer for every type of system output.

---

## Phase 2 — Dataset Validation

**Status:** Completed

### Goal

Validate the full infrastructure with real dataset rows rather than simple fake messages.

### Implemented

- Siddha Parquet loading.
- Deterministic replay.
- MQTT publishing.
- Structured IMU writes.
- Batch performance validation.
- Metrics:
  - `queue_depth`
  - `failed_batch_count`
  - `retried_line_count`
  - `dropped_line_count`

### Data Flow

```text
Siddha Dataset
→ siddha-sensor-sim
→ EMQX
→ ingest-service
→ InfluxDB: imu_raw_full_rows
```

### Thesis Reasoning

The system had to prove that it can ingest large, structured sensor data reproducibly before adding ML.

---

## Phase 3 — HAR Microservice

**Status:** Completed

### Goal

Add processing after storage using an ONNX activity recognition model.

### Implemented

- HAR service.
- InfluxDB polling.
- Stream grouping by device and recording.
- Deterministic ordering.
- Sliding windows.
- ONNX inference.
- Prediction writing.

### Data Flow

```text
InfluxDB: imu_raw_full_rows
→ har-service
→ InfluxDB: har_predictions_7_activity
```

### Validated Runtime

| Parameter | Value |
|---|---|
| Device | `watch` |
| Input layout | `gyro_then_accel` |
| Temporal preprocessing | `none` |
| Score aggregation | `sum` |
| Supported activities | `F,G,O,P,Q,R,S` |

### Important Limitation

The model supports only seven Siddha activities:

```text
F, G, O, P, Q, R, S
```

It is not a full 18-activity classifier.

---

# Phase 4 — Real Watch Pipeline

**Status:** Completed

## Goal

Integrate the MetaWear bracelet as a real hardware sensor source and run real-time HAR inference.

## Target Data Flow

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
```

## Validation Result

Phase 4 was validated with recording ID `phase4_live_validation_001`.

- MetaWear connected successfully over BLE.
- Raw ACC/GYRO data was published at approximately 26 Hz.
- Watch cleaner produced 9,599 clean IMU rows.
- HAR MQTT mode produced 463 live predictions.
- Ingest writer finished with queue depth 0.
- Failed batches, retries, and dropped lines were all 0.

## New Components

### `metawear_bridge`

Protocol adapter:

```text
BLE → MQTT
```

Publishes raw events to:

```text
tennis/watch/raw
```

### `watch_cleaner_service`

Sensor-specific cleaning layer.

Responsibilities:

- validate values,
- normalize timestamps,
- ensure complete IMU rows,
- publish clean rows.

Publishes to:

```text
tennis/watch/clean
```

### HAR MQTT Mode

HAR uses:

```env
HAR_INPUT_MODE=mqtt_stream
```

for real-time watch inference.

The existing Phase 3 mode remains:

```env
HAR_INPUT_MODE=db_polling
```

for reproducible dataset evaluation.

## Phase 4 Done When

- MetaWear data reaches `tennis/watch/raw`.
- Cleaner publishes valid rows to `tennis/watch/clean`.
- Ingest stores clean rows in `watch_imu_clean`.
- HAR consumes clean rows in MQTT mode.
- Predictions are written to `real_har_predictions`.
- Delay and throughput can be observed.

All completion criteria were satisfied during the Phase 4 validation test.

---

# Phase 5 — Grafana Visualization

**Status:** Completed

## Goal

Visualize stored sensor data and predictions.

## Required Path

```text
InfluxDB → Grafana
```

Dashboards:

- live watch IMU signal from `watch_imu_clean`
- current/last predicted activity from `real_har_predictions`
- prediction confidence over time
- historical prediction timeline
- session summary
- ingestion / prediction health indicators where possible

## Optional Enhancement

Grafana Live / MQTT visualization was considered but not implemented. The InfluxDB-backed dashboard refreshes at 1 second, which is sufficient for the validated live pipeline.

## Done When

- Grafana connects to InfluxDB.
- Dashboard panels show real watch IMU rows from `watch_imu_clean`.
- Dashboard panels show HAR predictions from `real_har_predictions`.
- Dashboard refresh is configured for 1 second.
- MQTT/Grafana Live is not required for the final Phase 5 design.

---

# Phase 6 — EEG/ECG Dataset Sources

**Status:** Completed

## Goal

Demonstrate multi-source extensibility using two additional sensor data sources.

These are dataset-based sources, not physical hardware integrations.

## Scope

Implemented:

```text
eeg_dataset_sim
→ EMQX: tennis/eeg/raw
→ eeg_cleaner_service
→ EMQX: tennis/eeg/clean
→ ingest-service
→ InfluxDB: eeg_clean
→ Grafana

ecg_dataset_sim
→ EMQX: tennis/ecg/raw
→ ecg_cleaner_service
→ EMQX: tennis/ecg/clean
→ ingest-service
→ InfluxDB: ecg_clean
→ Grafana
```

## Important Limitation

No ML is implemented for EEG or ECG in this thesis.

This is intentional.

The goal is to show that the architecture supports heterogeneous sensor sources. Sensor-specific ML for EEG/ECG is future work.

## Thesis Reasoning

This phase demonstrates extensibility without expanding the scope into multiple ML research problems.
