# Smart Tennis Field — IoT + Real-Time HAR Pipeline

## 1. Project Overview

Smart Tennis Field is a Docker-based IoT thesis project for collecting, storing, processing, and visualizing sensor data.

The project started with a reproducible dataset replay pipeline and is now extended with a real MetaWear bracelet for live human activity recognition (HAR).

The core architectural loop is:

```text
Data source → MQTT Broker → Cleaning / Normalization → Storage → Processing → Storage → Visualization
```

The project is intentionally split into microservices so that ingestion, cleaning, storage, machine learning, and visualization can evolve independently.

---

## 2. Current Phase Status

| Phase | Status | Description |
|---|---:|---|
| Phase 0 | Completed | MQTT broker with EMQX validated |
| Phase 1 | Completed | ingest-service + InfluxDB storage |
| Phase 2 | Completed | Siddha dataset replay into MQTT and InfluxDB |
| Phase 3 | Completed | HAR ONNX service with DB-polling mode and prediction storage |
| Phase 4 | Completed | Real MetaWear watch pipeline with cleaner + live HAR mode |
| Phase 5 | Current | Grafana dashboards for live and historical visualization |
| Phase 6 | Planned | EEG and ECG dataset-based sensors, storage only, no ML |

---

## 3. Final Architecture

### 3.1 Phase 4 Real Watch Pipeline

```text
MetaWear Bracelet
        │
        │ BLE
        ▼
metawear_bridge
BLE → MQTT protocol adapter
        │
        ▼
EMQX topic: tennis/watch/raw
        │
        ▼
watch_cleaner_service
validate + normalize + pair ACC/GYRO
        │
        ▼
EMQX topic: tennis/watch/clean
        │                         │
        ▼                         ▼
ingest-service              har-service
stores clean IMU            MQTT stream mode
        │                         │
        ▼                         ▼
InfluxDB                    InfluxDB
watch_imu_clean             real_har_predictions
        │                         │
        └──────────── Grafana ────┘
```

### 3.2 Existing Dataset Evaluation Pipeline

```text
Siddha Parquet Dataset
        │
        ▼
siddha-sensor-sim
        │
        ▼
EMQX
        │
        ▼
ingest-service
        │
        ▼
InfluxDB: imu_raw_full_rows
        │
        ▼
har-service DB mode
        │
        ▼
InfluxDB: har_predictions_7_activity
```

The Siddha simulator is optional and should be started only when dataset replay is needed.

---

## 4. Why the Architecture Is Designed This Way

### 4.1 Why use a cleaner service?

The MetaWear bracelet sends raw accelerometer and gyroscope events. These raw events are not directly suitable for storage or HAR inference.

The cleaner service is responsible for:

- validating numeric values,
- rejecting impossible sensor readings,
- pairing accelerometer and gyroscope samples,
- normalizing timestamps,
- generating clean sample indexes,
- publishing a canonical clean IMU row.

This keeps sensor-specific logic out of the ingest-service and HAR service.

### 4.2 Why does HAR write predictions directly to InfluxDB?

The ingest-service owns sensor data ingestion. The HAR service owns prediction output.

Therefore the correct prediction path is:

```text
HAR service → InfluxDB
```

not:

```text
HAR service → MQTT → ingest-service → InfluxDB
```

This avoids making ingest-service responsible for every possible ML prediction schema.

### 4.3 Why store clean IMU and predictions separately?

Clean IMU rows are the model input. Prediction rows are the model output.

The prediction table should not duplicate full raw windows. Instead, predictions store metadata such as:

- device,
- recording_id,
- predicted_label,
- confidence,
- window_start_dataset_ts,
- window_end_dataset_ts,
- window_size,
- window_stride.

This keeps storage efficient and makes the system reproducible.

---

## 5. Repository Structure

```text
smart-tennis-field/
│
├── docker-compose.yml
├── .env.example
├── query_db.py
├── rows_number.py
├── rows_example.py
│
├── dataset/
│   └── data.parquet                  # optional Siddha dataset file
│
└── services/
    ├── ingest_service/
    │   ├── app/
    │   ├── Dockerfile
    │   └── requirements.txt
    │
    ├── siddha_sensor_sim/
    │   ├── app/
    │   ├── Dockerfile
    │   └── requirements.txt
    │
    ├── har_service/
    │   ├── app/
    │   ├── model/
    │   │   ├── L2MU_plain_leaky.onnx
    │   │   └── labels.txt
    │   ├── Dockerfile
    │   └── requirements.txt
    │
    ├── metawear_bridge/
    │   ├── app/
    │   │   ├── bridge.py
    │   │   ├── config.py
    │   │   ├── metawear_client.py
    │   │   └── mqtt_publisher.py
    │   ├── Dockerfile
    │   └── requirements.txt
    │
    └── watch_cleaner_service/
        ├── app/
        │   ├── main.py
        │   └── config.py
        ├── Dockerfile
        └── requirements.txt
```

---

## 6. Main Services

| Service | Purpose |
|---|---|
| `emqx` | MQTT broker |
| `influxdb3` | Time-series database |
| `influxdb3-explorer` | InfluxDB web UI |
| `ingest-service` | Stores clean canonical sensor data |
| `siddha-sensor-sim` | Optional dataset replay simulator |
| `metawear_bridge` | Local BLE → MQTT adapter for MetaWear bracelet |
| `watch-cleaner-service` | Converts raw watch events into clean IMU rows |
| `har-service` | Runs ONNX HAR inference and stores predictions |
| `grafana` | Dashboard visualization service |

---

## 7. Requirements

### 7.1 System Requirements

- Docker Desktop
- Docker Compose
- Python 3.11 or newer
- A working MetaWear bracelet for Phase 4
- Bluetooth available on the host machine
- InfluxDB token configured

### 7.2 Python Requirements for Local MetaWear Bridge

The MetaWear bridge is normally run outside Docker because Bluetooth access from Docker is harder, especially on Windows.

From the project root:

```bash
cd services/metawear_bridge
python -m venv .venv
.venv\Scripts\activate       # Windows PowerShell
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

---

## 8. Environment Setup

Create your local environment file:

```bash
cp .env.example .env
```

Then edit `.env` and set at least:

```env
INFLUX_TOKEN=YOUR_TOKEN_HERE
HAR_INFLUX_TOKEN=YOUR_TOKEN_HERE
METAWEAR_MAC_ADDRESS=YOUR_METAWEAR_MAC_ADDRESS
```

On Windows, the MetaWear bridge usually connects to EMQX through the host-mapped port:

```env
METAWEAR_MQTT_HOST=localhost
METAWEAR_MQTT_PORT=2883
```

Inside Docker services, MQTT uses the Docker service name:

```env
MQTT_HOST=emqx
MQTT_PORT=1883
```

---

## 9. How to Run Phase 4: Real Watch Pipeline

### Step 1 — Start backend services

From the project root:

```bash
docker compose up -d emqx influxdb3 influxdb3-explorer watch-cleaner-service ingest-service har-service
```

Check services:

```bash
docker compose ps
```

### Step 2 — Run MetaWear bridge locally

In a separate terminal:

```bash
cd services/metawear_bridge
python -m app.bridge
```

Expected output:

```text
Connecting to MetaWear...
Connected to XX:XX:XX:XX:XX:XX over BLE
Streaming RAW MetaWear data to MQTT topic: tennis/watch/raw
Raw publish rate per second: {'acc': 25, 'gyro': 25}
```

### Step 3 — Check cleaner logs

```bash
docker compose logs -f watch-cleaner-service
```

Expected:

```text
Subscribed to raw topic: tennis/watch/raw
Publishing clean rows to: tennis/watch/clean
```

### Step 4 — Check ingest-service health

```bash
curl http://localhost:8000/health
curl http://localhost:8000/stats
```

Important fields:

```text
queue_depth
failed_batch_count
retried_line_count
dropped_line_count
writer_thread_alive
```

### Step 5 — Check clean watch data in InfluxDB

Open InfluxDB Explorer:

```text
http://localhost:8888
```

Run:

```sql
SELECT *
FROM watch_imu_clean
WHERE device = 'watch'
ORDER BY time DESC
LIMIT 20;
```

Expected fields:

```text
device
recording_id
sample_idx
acc_x, acc_y, acc_z
gyro_x, gyro_y, gyro_z
dataset_ts
activity_gt
```

### Step 6 — Check HAR predictions

```bash
docker compose logs -f har-service
```

Expected:

```text
Live prediction | device=watch | recording_id=... | predicted=... | confidence=...
```

Then query:

```sql
SELECT *
FROM real_har_predictions
WHERE device = 'watch'
ORDER BY time DESC
LIMIT 20;
```

---

## Phase 4 Validation Summary

A live MetaWear validation test was executed using recording ID `phase4_live_validation_001`.

| Metric | Result |
|---|---:|
| Streaming duration | ~385 seconds |
| Clean IMU rows stored | 9,599 |
| HAR predictions stored | 463 |
| Approx. clean row rate | ~24.9 rows/sec |
| Approx. prediction interval | ~0.83 sec |
| Influx queue depth | 0 |
| Failed batches | 0 |
| Retried lines | 0 |
| Dropped lines | 0 |

The test validates the complete live path:

`MetaWear → BLE → MQTT raw → watch cleaner → MQTT clean → ingest-service → InfluxDB → HAR MQTT mode → prediction storage`.

Detailed report: `docs/Validation/phase4_validation_report.md`.

---

## 10. Optional: Run Siddha Dataset Replay

The Siddha simulator is optional and is controlled by the Compose profile `replay`.

To replay the Siddha dataset into InfluxDB, place your dataset at:

```text
dataset/data.parquet
```

Then run:

```bash
docker compose --profile replay up siddha-sensor-sim
```

This command starts only the simulator profile service. The simulator publishes dataset rows to MQTT, and ingest-service writes them to InfluxDB.

Recommended: start the backend first:

```bash
docker compose up -d emqx influxdb3 ingest-service
```

Then run replay:

```bash
docker compose --profile replay up siddha-sensor-sim
```

Check stored dataset rows:

```sql
SELECT COUNT(*) AS n
FROM imu_raw_full_rows;
```

Do not run Siddha replay and real MetaWear tests at the same time unless you intentionally want mixed workload testing.

---

## 11. HAR Modes

The HAR service supports two modes.

### 11.1 DB Polling Mode

Used for reproducible Phase 3 dataset evaluation.

```env
HAR_INPUT_MODE=db_polling
HAR_IMU_TABLE=imu_raw_full_rows
HAR_PREDICTION_TABLE=har_predictions_7_activity
HAR_FILTER_DEVICE=watch
HAR_ALLOWED_ACTIVITY_GT=F,G,O,P,Q,R,S
HAR_WINDOW_SIZE=40
HAR_WINDOW_STRIDE=20
```

Flow:

```text
InfluxDB imu_raw_full_rows → HAR → InfluxDB har_predictions_7_activity
```

### 11.2 MQTT Stream Mode

Used for Phase 4 live MetaWear prediction.

```env
HAR_INPUT_MODE=mqtt_stream
HAR_MQTT_TOPIC=tennis/watch/clean
HAR_PREDICTION_TABLE=real_har_predictions
HAR_FILTER_DEVICE=watch
HAR_ALLOWED_ACTIVITY_GT=
HAR_WINDOW_SIZE=40
HAR_WINDOW_STRIDE=20
```

Flow:

```text
MQTT tennis/watch/clean → HAR → InfluxDB real_har_predictions
```

At 25 Hz:

```text
window_size=40  → about 1.6 seconds at 25 Hz
window_stride=20 → about 0.8 seconds between predictions at 25 Hz
```

---

## 12. Environment Variables

The tables below show code-level defaults. The provided `.env.example` and your local `.env` override these at runtime.

### 12.1 MQTT / Ingest Variables

| Variable | Default | Meaning |
|---|---|---|
| `MQTT_HOST` | `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port inside Docker |
| `SUB_TOPICS` | `tennis/sensor/+/events,tennis/camera/+/ball` | Comma-separated topics ingest-service subscribes to |
| `PUB_TOPIC` | `tennis/sensor/1/events` | Optional topic used by `/publish` endpoint |
| `EVENT_BUFFER_MAX` | `100` | Max number of recent events kept in memory |

Recommended Phase 4 value:

```env
SUB_TOPICS=tennis/watch/clean,tennis/sensor/+/events
```

Camera topics are not required in the final scope.

---

### 12.2 InfluxDB Variables

| Variable | Default | Meaning |
|---|---|---|
| `INFLUX_ENABLED` | `0` | Enables InfluxDB writing |
| `INFLUX_HOST` | `http://localhost:8181` | InfluxDB URL |
| `INFLUX_TOKEN` | empty | InfluxDB token |
| `INFLUX_DATABASE` | `tennis` | InfluxDB database name |
| `INFLUX_TABLE` | `events` | Generic event table |
| `INFLUX_IMU_TABLE` | `imu_raw` | Dataset IMU table |
| `INFLUX_WATCH_IMU_TABLE` | `watch_imu_clean` | Real MetaWear clean IMU table |
| `INFLUX_BATCH_SIZE` | `500` | Number of lines per batch write |
| `INFLUX_FLUSH_INTERVAL_MS` | `200` | Batch flush interval |
| `INFLUX_MAX_QUEUE_SIZE` | `50000` | Max queued lines before dropping writes |
| `INFLUX_WRITE_GENERIC_EVENTS` | `1` | Whether to also write generic event envelopes |

You can rename tables by changing:

```env
INFLUX_IMU_TABLE=my_dataset_imu_table
INFLUX_WATCH_IMU_TABLE=my_watch_table
```

---

### 12.3 MetaWear Bridge Variables

| Variable | Default | Meaning |
|---|---|---|
| `METAWEAR_MAC_ADDRESS` | `YOUR_MAC_ADDRESS_HERE` | BLE MAC address of the bracelet |
| `METAWEAR_DEVICE_NAME` | `watch` | Device tag stored in messages |
| `METAWEAR_RECORDING_ID` | `real_metawear_session_001` | Session / recording identifier |
| `METAWEAR_SAMPLING_RATE_HZ` | `25` | Expected MetaWear sampling rate |
| `METAWEAR_MQTT_HOST` | `localhost` | MQTT host from local bridge |
| `METAWEAR_MQTT_PORT` | `2883` | Host-mapped MQTT port |
| `METAWEAR_MQTT_TOPIC` | `tennis/watch/raw` | Raw watch topic |

Example:

```env
METAWEAR_MAC_ADDRESS=C9:E5:38:6A:CC:E5
METAWEAR_RECORDING_ID=forehand_test_001
METAWEAR_SAMPLING_RATE_HZ=25
METAWEAR_MQTT_TOPIC=tennis/watch/raw
```

---

### 12.4 Data Cleaner Variables

| Variable | Default | Meaning |
|---|---|---|
| `CLEANER_MQTT_HOST` | `emqx` | MQTT host for cleaner service |
| `CLEANER_MQTT_PORT` | `1883` | MQTT port for cleaner service |
| `CLEANER_MQTT_CLIENT_ID` | `watch-cleaner-service` | MQTT client id |
| `CLEANER_RAW_TOPIC` | `tennis/watch/raw` | Raw watch input topic |
| `CLEANER_CLEAN_TOPIC` | `tennis/watch/clean` | Clean watch output topic |
| `CLEANER_MQTT_QOS` | `1` | MQTT QoS |
| `CLEANER_MAX_ABS_ACC` | `80` | Maximum allowed absolute acceleration value |
| `CLEANER_MAX_ABS_GYRO` | `2500` | Maximum allowed absolute gyroscope value |
| `CLEANER_MAX_PAIR_AGE_SECONDS` | `0.25` | Max allowed time gap between acc and gyro pair |
| `CLEANER_DEFAULT_ACTIVITY_GT` | `unknown` | Ground-truth label for real sensor rows |

Example:

```env
CLEANER_MAX_PAIR_AGE_SECONDS=0.25
CLEANER_DEFAULT_ACTIVITY_GT=unknown
```

---

### 12.5 Siddha Simulator Variables

| Variable | Default | Meaning |
|---|---|---|
| `SIDDHA_MQTT_BROKER_HOST` | `emqx` | MQTT host for simulator |
| `SIDDHA_MQTT_BROKER_PORT` | `1883` | MQTT port for simulator |
| `SIDDHA_MQTT_TOPIC_PREFIX` | `tennis/sensor` | Topic prefix for simulated sensor messages |
| `SIDDHA_DATASET_PATH` | `/app/dataset/data.parquet` | Dataset path inside container |
| `SIDDHA_REPLAY_MODE` | `realtime` or `fast` | Replay mode |
| `SIDDHA_REPLAY_SPEED` | `1.0` | Replay speed multiplier |
| `SIDDHA_DEFAULT_DEVICE_FILTER` | empty | Optional device filter, e.g. `watch` |
| `SIDDHA_DEFAULT_ACTIVITY_FILTER` | empty | Optional activity filter, e.g. `F` |
| `SIDDHA_DEFAULT_RECORDING_ID_FILTER` | empty | Optional recording filter |
| `SIDDHA_LOOP_FOREVER` | `false` or `true` | Replay repeatedly if true |
| `SIDDHA_MQTT_QOS` | `1` or `0` | MQTT QoS |
| `SIDDHA_MQTT_WAIT_FOR_PUBLISH` | `true` or `false` | Wait for publish confirmation |

Example: replay only watch activity `F`:

```env
SIDDHA_DEFAULT_DEVICE_FILTER=watch
SIDDHA_DEFAULT_ACTIVITY_FILTER=F
SIDDHA_REPLAY_MODE=fast
```

Then run:

```bash
docker compose --profile replay up siddha-sensor-sim
```

---

### 12.6 HAR Service Variables

| Variable | Default | Meaning |
|---|---|---|
| `HAR_INPUT_MODE` | `db_polling` | `db_polling` or `mqtt_stream` |
| `HAR_POLL_INTERVAL_SECONDS` | `5` | DB polling interval |
| `HAR_MQTT_HOST` | `emqx` | MQTT host for live mode |
| `HAR_MQTT_PORT` | `1883` | MQTT port for live mode |
| `HAR_MQTT_TOPIC` | `tennis/watch/clean` | Clean IMU topic for live mode |
| `HAR_MQTT_QOS` | `1` or `0` | MQTT QoS |
| `HAR_INFLUX_HOST` | `http://influxdb3:8181` | InfluxDB URL |
| `HAR_INFLUX_TOKEN` | empty | InfluxDB token for HAR writes/queries |
| `HAR_INFLUX_DATABASE` | `tennis` | InfluxDB database |
| `HAR_IMU_TABLE` | `imu_raw_full_rows` | IMU input table for DB mode |
| `HAR_PREDICTION_TABLE` | `har_predictions_7_activity` | Prediction output table |
| `HAR_MODEL_PATH` | `/app/model/L2MU_plain_leaky.onnx` | ONNX model path |
| `HAR_LABELS_PATH` | `/app/model/labels.txt` | Label file path |
| `HAR_MODEL_NAME` | `L2MU_plain_leaky` | Model name stored in prediction table |
| `HAR_INPUT_LAYOUT` | `gyro_then_accel` | Model input layout |
| `HAR_TEMPORAL_PREPROCESS` | `none` | Temporal preprocessing mode |
| `HAR_SCORE_AGGREGATION` | `sum` | Score aggregation strategy |
| `HAR_WINDOW_SIZE` | `40` | Sliding window size |
| `HAR_WINDOW_STRIDE` | `20` | Sliding window stride |
| `HAR_MAX_WINDOWS_PER_STREAM` | `10` | Max windows processed per stream in one DB-mode pass |
| `HAR_QUERY_LIMIT` | `5000` | Max DB rows fetched per query |
| `HAR_MQTT_PREDICTION_TOPIC` | `tennis/watch/predictions` | MQTT topic for live prediction republish |
| `HAR_PREDICTION_TOP_K` | `3` | Number of top predictions to keep internally/log |
| `HAR_DEBUG_INFERENCE` | `false` | Enables extra inference logs |
| `HAR_FILTER_DEVICE` | empty or `watch` or `phone` | Optional device filter |
| `HAR_FILTER_RECORDING_ID` | empty or `<recording_id>` | Optional recording filter |
| `HAR_ALLOWED_ACTIVITY_GT` | `F,G,O,P,Q,R,S` | Allowed labels for dataset mode; empty for live mode |

Recommended live Phase 4 configuration:

```env
HAR_INPUT_MODE=mqtt_stream
HAR_MQTT_TOPIC=tennis/watch/clean
HAR_PREDICTION_TABLE=real_har_predictions
HAR_FILTER_DEVICE=watch
HAR_ALLOWED_ACTIVITY_GT=
HAR_WINDOW_SIZE=40
HAR_WINDOW_STRIDE=20
```

Recommended Phase 3 dataset configuration:

```env
HAR_INPUT_MODE=db_polling
HAR_IMU_TABLE=imu_raw_full_rows
HAR_PREDICTION_TABLE=har_predictions_7_activity
HAR_FILTER_DEVICE=watch
HAR_ALLOWED_ACTIVITY_GT=F,G,O,P,Q,R,S
HAR_WINDOW_SIZE=40
HAR_WINDOW_STRIDE=20
```

---

### 12.7 Phase 5 — Grafana Visualization

Grafana is the next phase after the successful live MetaWear pipeline.

Required visualization path:

```text
InfluxDB → Grafana
```

Default URL:

```text
http://localhost:3000
```

Default login is usually:

```text
username: admin
password: admin
```

You can optionally set:

```env
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
```

The dashboard will visualize:

- live watch IMU signal from `watch_imu_clean`
- current/last predicted activity from `real_har_predictions`
- confidence over time
- prediction history
- session summary
- ingestion / prediction health indicators where possible

---

## 13. Useful Commands

### Start core infrastructure

```bash
docker compose up -d emqx influxdb3 influxdb3-explorer
```

### Start Phase 4 services

```bash
docker compose up -d watch-cleaner-service ingest-service har-service
```

### Stop all services

```bash
docker compose down
```

### Rebuild after code changes

```bash
docker compose build ingest-service watch-cleaner-service har-service
```

### Follow logs

```bash
docker compose logs -f ingest-service
docker compose logs -f watch-cleaner-service
docker compose logs -f har-service
```

### Run optional Siddha replay

```bash
docker compose --profile replay up siddha-sensor-sim
```

---

## 14. Useful InfluxDB Queries

### Check clean watch rows

```sql
SELECT *
FROM watch_imu_clean
WHERE device = 'watch'
ORDER BY time DESC
LIMIT 20;
```

### Count clean watch rows

```sql
SELECT COUNT(*) AS n
FROM watch_imu_clean
WHERE device = 'watch';
```

### Check live predictions

```sql
SELECT *
FROM real_har_predictions
WHERE device = 'watch'
ORDER BY time DESC
LIMIT 20;
```

### Check dataset rows

```sql
SELECT COUNT(*) AS n
FROM imu_raw_full_rows;
```

### Check dataset HAR predictions

```sql
SELECT *
FROM har_predictions_7_activity
ORDER BY time DESC
LIMIT 20;
```

---

## 15. Troubleshooting

### `watch_imu_clean` does not exist

InfluxDB creates tables only after the first successful write.

Check:

```bash
docker compose logs -f watch-cleaner-service
docker compose logs -f ingest-service
curl http://localhost:8000/stats
```

Common causes:

- MetaWear bridge is not running,
- cleaner is not receiving `tennis/watch/raw`,
- ingest-service is not subscribed to `tennis/watch/clean`,
- Influx token is missing,
- batch writer failed.

### HAR gives HTTP 400

Usually means HAR is querying a table that does not exist or a SQL query is invalid.

For live Phase 4, make sure:

```env
HAR_INPUT_MODE=mqtt_stream
```

For DB mode, make sure the table in `HAR_IMU_TABLE` exists.

### No predictions are written

Check:

```bash
docker compose logs -f har-service
```

Possible causes:

- not enough rows to fill a window,
- wrong `HAR_MQTT_TOPIC`,
- `HAR_ALLOWED_ACTIVITY_GT` is filtering live rows,
- model path is wrong,
- cleaner is dropping samples due to stale ACC/GYRO pairs.

For live mode, use:

```env
HAR_ALLOWED_ACTIVITY_GT=
```

### MetaWear cannot connect

Common causes:

- wrong MAC address,
- device still connected to phone,
- Bluetooth disabled,
- Windows Bluetooth discovery issue,
- bracelet not advertising.

Disconnect the bracelet from mobile apps before running the Python bridge.

### Data appears in wrong time range

Real watch rows should use wall-clock `ts` for InfluxDB time and relative `dataset_ts` / `sensor_ts` for model windows.

Do not send epoch milliseconds as `dataset_ts`.

Correct:

```text
sensor_ts = seconds since session start
```

Wrong:

```text
dataset_ts = 1710000000000
```

---

## 16. Updated Future Work

### Phase 5 — Grafana Visualization

Grafana will visualize:

```text
InfluxDB → Grafana
```

- live watch IMU signal from `watch_imu_clean`
- current/last predicted activity from `real_har_predictions`
- confidence over time
- prediction history
- session summary
- ingestion / prediction health indicators where possible

Grafana auto-refresh is sufficient for thesis visualization. Grafana Live can be considered only if a real push-based panel is required and implemented fully.

### Phase 6 — EEG and ECG Dataset Sensors

Planned flow:

```text
eeg_dataset_sim → eeg_cleaner → ingest-service → InfluxDB: eeg_clean
ecg_dataset_sim → ecg_cleaner → ingest-service → InfluxDB: ecg_clean
```

No ML is implemented for EEG/ECG in this thesis phase. Their purpose is to prove multi-source extensibility.

---

## 17. Thesis Summary

This project demonstrates a reproducible IoT microservice architecture for wearable sensor ingestion and activity recognition.

The final design separates:

```text
protocol adaptation → cleaning → ingestion → storage → inference → visualization
```

This separation improves:

- reliability,
- observability,
- reproducibility,
- extensibility,
- thesis defensibility.

The system supports both:

- reproducible dataset evaluation through DB polling,
- live real-sensor inference through MQTT stream processing.
