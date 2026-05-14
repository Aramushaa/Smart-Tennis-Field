# Smart Tennis Field — Implementation Journal

This document records the implementation journey and the reasoning behind architecture changes.

For final-state technical reference, see [Architecture.md](Architecture.md).  
For the roadmap, see [Phases.md](Phases.md).  
For payload/schema details, see [DatasetContract.md](DatasetContract.md).

---

## 1. Project Context

The thesis builds a Docker-based distributed infrastructure for collecting, storing, and processing multi-sensor data.

The system evolved from:

```text
Data → Broker → Storage
```

to:

```text
Data → Broker → Storage → Processing → Storage
```

and now, after Phase 4 validation:

```text
Real Sensor → Protocol Adapter → Broker → Cleaner → Storage + Processing → Visualization
```

---

# 2. Phase 0 — MQTT Infrastructure

## What Was Built

- EMQX broker in Docker.
- Publisher/subscriber tests.
- Docker networking conventions.
- Topic-based event routing.

## Key Lesson

`localhost` inside a container is not the host machine. Docker services communicate using service names such as `emqx`.

---

# 3. Phase 1 — Ingest Service and Persistence

## What Was Built

- FastAPI ingest-service.
- MQTT subscriber worker.
- InfluxDB 3 integration.
- Generic event logging.
- Structured IMU writing.
- Health and stats endpoints.

## Key Lesson

Ingestion must be observable. The system added stats such as queue depth, failure counters, retry counters, and dropped-line counters.

---

# 4. Phase 2 — Siddha Dataset Validation

## What Was Built

- Siddha Parquet dataset reader.
- Dataset simulator.
- MQTT replay.
- Structured IMU storage.
- Deterministic recording identifiers.

## Key Lesson

Dataset replay is necessary for reproducibility. A real-time system cannot be defended only with live demos.

---

# 5. Phase 3 — HAR Microservice

## What Was Built

- HAR microservice.
- InfluxDB polling mode.
- Ordered stream fetching.
- Sliding windows.
- ONNX inference.
- Prediction storage.

## Important Fixes

- Mixed-device windows were prevented.
- Correct input layout was confirmed: `gyro_then_accel`.
- Correct score aggregation was confirmed: `sum`.
- Model scope was limited to seven supported activities.

## Result

The Phase 3 pipeline is complete and reproducible.

---

# 6. Phase 4 Architecture Update

## Why Phase 4 Changed

The initial idea was to connect the real watch data directly into the existing ingestion and HAR path.

After review, this was refined because raw hardware streams need sensor-specific adaptation before storage and inference.

The new Phase 4 architecture adds:

```text
metawear_bridge
watch_cleaner_service
HAR MQTT mode
watch_imu_clean table
real_har_predictions table
```

## Updated Phase 4 Flow

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

## Engineering Reasoning

The architecture separates responsibilities:

| Component | Responsibility |
|---|---|
| `metawear_bridge` | BLE acquisition and MQTT publishing |
| `watch_cleaner_service` | validation and canonicalization |
| `ingest-service` | storage of clean sensor data |
| `har-service` | activity prediction |
| `InfluxDB` | historical storage |
| `Grafana` | visualization |

## Thesis Reasoning

This design supports:

- reproducibility,
- observability,
- extensibility,
- measurable latency,
- clear service ownership.

---

# 7. Prediction Storage Decision

A key decision was made:

```text
HAR writes predictions directly to InfluxDB.
```

Predictions are not routed through ingest-service.

Reason:

```text
ingest-service owns sensor ingestion.
har-service owns prediction output.
```

Routing ML predictions through ingest-service would make ingest responsible for multiple ML schemas, which would reduce modularity.

---

# 8. Raw vs Clean Data Decision

The system should permanently store clean sensor data, not necessarily every raw hardware callback.

Recommended storage:

```text
watch_imu_clean
real_har_predictions
```

Optional debug storage:

```text
watch_imu_raw_debug
```

Clean IMU is stored because it is the actual model input and is needed for debugging, replay, and future model comparison.

Prediction rows store only the result and window metadata, not the full raw window.

---

# 9. Camera Scope Decision

Camera-based features are removed from future phases.

Reason:

- no camera hardware is available,
- the final thesis contribution is wearable sensor ingestion and HAR,
- keeping camera topics in the future architecture would create unnecessary scope confusion.

Legacy camera experiments may remain documented as early exploration, but not as final scope.

---

# 10. Phase 5 Plan — Grafana Visualization

Grafana is the next phase after Phase 4 validation.

Required path:

```text
InfluxDB → Grafana
```

Primary dashboard scope:

- live watch IMU signal from `watch_imu_clean`
- current/last predicted activity from `real_har_predictions`
- confidence over time
- prediction history
- session summary
- ingestion / prediction health indicators where possible

Optional path:

```text
HAR → Grafana Live
```

Grafana Live should be implemented only if it is verified and does not distract from the thesis core.

---

# 11. Phase 6 Plan — EEG/ECG Dataset Sources

Phase 6 will add two additional dataset-based sensor sources:

```text
EEG dataset
ECG dataset
```

These sources will show that the architecture can support heterogeneous data.

No EEG/ECG ML is planned for this thesis.

Future work may include dedicated EEG/ECG models.

---

# 12. Phase 4 Validation Result

Recording ID: `phase4_live_validation_001`  
Test duration: ~385 seconds  
Raw publish rate: ~26 ACC/sec + ~26 GYRO/sec  
Clean rows stored: 9,599  
Expected rows: ~9,625  
Row difference: -26 rows / 0.27%  
HAR predictions stored: 463  
Approx prediction interval: 0.83 seconds  
Queue depth: 0  
Failed batches: 0  
Retries: 0  
Dropped lines: 0  
Writer thread alive: true

Result: Phase 4 completed successfully.

Phase 5 will visualize the validated live pipeline in Grafana using InfluxDB as the source of truth.
