# Phases — Smart Tennis Field Roadmap

Each phase depends on the previous one: transport must be validated before persistence, persistence before processing.

| Phase | Status |
| --- | --- |
| Phase 0 — MQTT Infrastructure | Completed |
| Phase 1 — Ingest + Persistence | Completed |
| Phase 2 — Dataset Validation | Completed |
| Phase 3 — HAR Microservice | Completed |
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

## Phase 3 — HAR Microservice (Completed)

### Goal

Integrate a Human Activity Recognition (HAR) microservice that processes stored IMU data and generates activity predictions.

### Architecture Extension

```text
Data → Broker → Storage → Processing → Storage
```

Specifically:

```text
Dataset → MQTT → Ingest → InfluxDB (raw)
                              ↓
                         HAR Service
                              ↓
                   InfluxDB (predictions)
```

### Implementation Details

#### 1. HAR Microservice

- Separate service (`har-service`) in its own Docker container
- Polls IMU data from InfluxDB (DB polling, not MQTT streaming)
- Groups data by `(device, recording_id)`
- Builds sliding windows from ordered rows
- Runs ONNX inference via adapter pattern
- Writes predictions back to InfluxDB

#### 2. Windowing

- Window size: configurable via `HAR_WINDOW_SIZE` (validated: 40)
- Stride: configurable via `HAR_WINDOW_STRIDE` (validated: 20)
- Deterministic ordering via SQL: `ORDER BY time ASC, sample_idx ASC`
- Rows filtered by device and recording in the `WHERE` clause before windowing

#### 3. Model Integration

- ONNX model: `L2MU_plain_leaky.onnx` (PyTorch 2.2.1, ONNX opset 17, 3230 nodes)
- Input shape: `[40, 1, 6]` — 40 timesteps × 1 batch × 6 features
- Output shape: `[40, 1, 7]` — per-timestep prediction, 7 classes
- Input layout: `gyro_then_accel` (gyroscope channels before accelerometer)
- Temporal preprocessing: `none`
- Score aggregation: `sum` across timesteps
- Adapter pattern wraps the professor's `inference_engine.py` without modifying the original file

#### 4. Activity Filtering

The service filters by `allowed_activity_gt` (default: `F,G,O,P,Q,R,S`) to restrict processing to only the 7 activities the model was trained on. This prevents meaningless predictions on unsupported activity classes.

#### 5. Critical Fixes

The following issues were identified and resolved during integration:

| Issue | Impact |
| --- | --- |
| Mixed-device windows (phone + watch) | Severely degraded performance |
| Incorrect input layout interpretation | Model expected gyro-first, pipeline sent accel-first |
| Inconsistent evaluation methodology | Initial evaluation mixed all 18 activities against a 7-class model |
| Model–dataset mismatch assumptions | Assumed model covered all Siddha activities |

**Fixed by:**

- Grouping by `(device, recording_id)` to prevent cross-device contamination
- Restricting processing to `device=watch` via `HAR_FILTER_DEVICE`
- Validating preprocessing strategies via systematic sweep (see [Result.md](../Result.md))
- Filtering to the 7 supported activity codes via `HAR_ALLOWED_ACTIVITY_GT`

#### 6. Model Scope

> **Important:** The supplied model has strict operational boundaries.

The model is:

- ✔ 7-class classifier
- ✔ Optimized for wrist (watch) input
- ❌ Not designed for the full 18-activity Siddha dataset
- ❌ Not validated for phone input

Supported activities:

| Code | Activity | Label |
| --- | --- | --- |
| F | Typing | typing |
| G | Brushing Teeth | teeth |
| O | Playing Catch (Tennis) | catch |
| P | Dribbling (Basketball) | dribbling |
| Q | Writing | writing |
| R | Clapping | clapping |
| S | Folding Clothes | folding |

#### 7. Prediction Storage

Predictions are written to InfluxDB using line protocol. The measurement name is configurable via `HAR_PREDICTION_TABLE`.

**Schema:**

Tags:

- `device`
- `recording_id`
- `model_name`
- `input_layout`
- `score_aggregation`

Fields:

- `predicted_label` (string)
- `activity_gt` (string)
- `confidence` (float)
- `window_start_dataset_ts` (float)
- `window_end_dataset_ts` (float)
- `window_size` (integer)
- `window_stride` (integer)

Timestamp: derived from `window_end_dataset_ts` (nanosecond epoch).

#### 8. Duplicate Prediction Prevention

The service tracks `last_written_window_end_ts` per `(device, recording_id)` stream to avoid re-writing predictions for windows that have already been processed. Streams where the maximum `dataset_ts` hasn't changed since the last cycle are skipped entirely.

#### 9. Final Validated Configuration

| Parameter | Value |
| --- | --- |
| `HAR_FILTER_DEVICE` | `watch` |
| `HAR_INPUT_LAYOUT` | `gyro_then_accel` |
| `HAR_TEMPORAL_PREPROCESS` | `none` |
| `HAR_SCORE_AGGREGATION` | `sum` |
| `HAR_WINDOW_SIZE` | `40` |
| `HAR_WINDOW_STRIDE` | `20` |
| `HAR_ALLOWED_ACTIVITY_GT` | `F,G,O,P,Q,R,S` |
| `HAR_MAX_WINDOWS_PER_STREAM` | `0` (unlimited) |

### Performance Result

Validated accuracy: **85.0%** (119/140 windows correct) on the 7 supported activities, using watch-only data with `gyro_then_accel` layout and `sum` aggregation.

Per-activity breakdown:

| Activity | Accuracy |
| --- | --- |
| Playing Catch (Tennis) | 95.0% |
| Dribbling (Basketball) | 95.0% |
| Clapping | 90.0% |
| Brushing Teeth | 85.0% |
| Folding Clothes | 85.0% |
| Typing | 80.0% |
| Writing | 65.0% |

Full analysis: [Result.md](../Result.md)

### Phase 3 Outcome

- ✔ Full end-to-end pipeline working
- ✔ Model integrated and validated at 85% accuracy
- ✔ Predictions stored in database
- ✔ Comprehensive evaluation tooling created (`inspect_model.py`, `evaluate_model.py`, `fix_finder.py`)
- ✔ System ready for real sensor input

### Limitations

- Model supports only 7 of 18 Siddha activities
- Validated only on watch-like (wrist) data
- Phone-based inference is unreliable
- Writing activity has lowest accuracy (65%) — confused with Folding Clothes


### Status

**Phase 3: COMPLETED**

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
- HAR inference latency per window
- End-to-end latency from `dataset_ts` to prediction
- Broker restart recovery
- Data consistency (published vs stored count)
- MQTT QoS impact on delivery
- Replay mode comparison (`realtime` vs `fast`)

### Methodology

Experiments use controlled configurations (replay mode, QoS, batch size) and measure correctness, latency, throughput, and resource usage for reproducible and comparable results.
