# Smart Tennis Field — IoT Sensor Pipeline + Live HAR

Smart Tennis Field is a Docker-based IoT thesis project for collecting, cleaning, storing, processing, and visualizing wearable and dataset-based sensor streams. It validates a microservice architecture for MetaWear watch ingestion, ONNX human activity recognition (HAR), Siddha dataset replay, EEG/ECG dataset fake sensors, InfluxDB storage, and Grafana visualization.

```text
Data Source -> Adapter/Simulator -> MQTT Broker -> Cleaner -> Storage / Processing -> Visualization
```

## Phase Status

| Phase | Status | Result |
|---|---|---|
| Phase 0 | Completed | EMQX MQTT broker validated |
| Phase 1 | Completed | Ingest-service and InfluxDB storage |
| Phase 2 | Completed | Siddha dataset replay stored in InfluxDB |
| Phase 3 | Completed | ONNX HAR service with DB polling mode |
| Phase 4 | Completed | Real MetaWear watch pipeline and live HAR |
| Phase 5 | Completed | Grafana dashboard from InfluxDB |
| Phase 6 | Completed | EEG/ECG dataset fake sensors and storage |

## Main Data Flows

### Real Watch + HAR

```text
MetaWear Bracelet
-> BLE
-> metawear_bridge
-> EMQX: tennis/watch/raw
-> watch-cleaner-service
-> EMQX: tennis/watch/clean
-> ingest-service
-> InfluxDB: watch_imu_clean
-> Grafana

tennis/watch/clean
-> har-service
-> InfluxDB: real_har_predictions
-> Grafana
```

### Siddha Dataset Replay

```text
Siddha Parquet Dataset
-> siddha-sensor-sim
-> EMQX
-> ingest-service
-> InfluxDB: imu_raw_full_rows
-> har-service DB mode
-> InfluxDB: har_predictions_7_activity
```

### EEG/ECG Fake Sensors

```text
OpenNeuro ds006848
-> eeg-dataset-sim / ecg-dataset-sim
-> EMQX raw topics
-> eeg-cleaner-service / ecg-cleaner-service
-> EMQX clean topics
-> ingest-service
-> InfluxDB: eeg_clean / ecg_clean
-> Grafana
```

## Services

| Service | Purpose |
|---|---|
| `emqx` | MQTT broker |
| `influxdb3` | Time-series database |
| `influxdb3-explorer` | InfluxDB web UI |
| `ingest-service` | Stores clean sensor data |
| `siddha-sensor-sim` | Replays Siddha IMU dataset |
| `metawear_bridge` | Local BLE-to-MQTT adapter for MetaWear |
| `watch-cleaner-service` | Cleans and pairs watch ACC/GYRO rows |
| `har-service` | Runs ONNX HAR inference |
| `grafana` | Visualizes stored sensor and prediction data |
| `eeg-dataset-sim` | Replays EEG samples from OpenNeuro |
| `eeg-cleaner-service` | Validates and normalizes EEG rows |
| `ecg-dataset-sim` | Replays ECG samples from OpenNeuro |
| `ecg-cleaner-service` | Validates and normalizes ECG rows |

## Requirements

- Docker Desktop and Docker Compose.
- Python 3.11 or newer.
- InfluxDB token.
- MetaWear bracelet for the live watch pipeline.
- OpenNeuro ds006848 dataset subset for Phase 6.

## Environment Setup

Create your local environment file:

```bash
cp .env.example .env
```

Set at least:

```env
INFLUX_TOKEN=YOUR_TOKEN_HERE
HAR_INFLUX_TOKEN=YOUR_TOKEN_HERE
METAWEAR_MAC_ADDRESS=YOUR_METAWEAR_MAC_ADDRESS

# Local MetaWear bridge on Windows
METAWEAR_MQTT_HOST=localhost
METAWEAR_MQTT_PORT=2883

# Docker services
MQTT_HOST=emqx
MQTT_PORT=1883

# Phase 6 defaults
EEG_MAX_SECONDS=600
ECG_MAX_SECONDS=600
EEG_DOWNSAMPLE_HZ=100
ECG_DOWNSAMPLE_HZ=100
INFLUX_EEG_TABLE=eeg_clean
INFLUX_ECG_TABLE=ecg_clean
```

## Quick Start

```bash
docker compose up -d emqx influxdb3 influxdb3-explorer ingest-service grafana
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/stats
```

## Run Live Watch + HAR

Start backend services:

```bash
docker compose up -d emqx influxdb3 influxdb3-explorer ingest-service watch-cleaner-service har-service grafana
```

Run the MetaWear bridge locally:

```bash
cd services/metawear_bridge
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.bridge
```

Check logs:

```bash
docker compose logs -f watch-cleaner-service
docker compose logs -f ingest-service
docker compose logs -f har-service
```

## Run Siddha Replay

Place the Siddha dataset at `dataset/data.parquet`, then run:

```bash
docker compose up -d emqx influxdb3 ingest-service
docker compose --profile replay up siddha-sensor-sim
```

Check stored rows:

```sql
SELECT COUNT(*) AS n FROM imu_raw_full_rows;
```

## Run EEG/ECG Phase 6

Place the OpenNeuro dataset at `dataset/openneuro_ds006848/`.

```bash
python3 reset_phase6_tables.py
docker compose --profile phase6 build
docker compose --profile phase6 up -d eeg-cleaner-service ecg-cleaner-service
docker compose --profile phase6 up -d eeg-dataset-sim
docker compose --profile phase6 up -d ecg-dataset-sim
```

Check logs:

```bash
docker compose logs -f eeg-dataset-sim
docker compose logs -f ecg-dataset-sim
docker compose logs -f eeg-cleaner-service
docker compose logs -f ecg-cleaner-service
docker compose logs -f ingest-service
```

Expected default Phase 6 validation with 600 seconds at 100 Hz:

| Table | Expected rows |
|---|---:|
| `eeg_clean` | about 60,000 |
| `ecg_clean` | about 60,000 |

```sql
SELECT COUNT(*) AS n FROM eeg_clean;
SELECT COUNT(*) AS n FROM ecg_clean;
```

## Dashboards

| Tool | URL | Login |
|---|---|---|
| Grafana | `http://localhost:3000` | `admin` / `admin` |
| InfluxDB Explorer | `http://localhost:8888` | token from `.env` |

Provisioned dashboard:

```text
Smart Tennis Field - Live Dashboard
```

## Architecture Diagrams

Detailed diagrams are available in [`docs/diagrams`](docs/diagrams):

- System overview
- Docker Compose topology
- Real watch pipeline
- Siddha dataset pipeline
- EEG/ECG fake-sensor pipeline
- Data ownership and storage

```md
## Architecture Diagrams

Detailed diagrams are available in [`docs/diagrams`](docs/diagrams):

| Diagram | Purpose |
|---|---|
| [`01-system-overview`](docs/diagrams/01-system-overview.md) | Full project architecture |
| [`02-docker-compose-topology`](docs/diagrams/02-docker-compose-topology.md) | Docker services and profiles |
| [`03-watch-pipeline`](docs/diagrams/03-watch-pipeline.md) | Real MetaWear watch pipeline |
| [`04-siddha-dataset-pipeline`](docs/diagrams/04-siddha-dataset-pipeline.md) | Siddha replay and HAR DB mode |
| [`05-eeg-ecg-fake-sensor-pipeline`](docs/diagrams/05-eeg-ecg-fake-sensor-pipeline.md) | Phase 6 fake-sensor extension |
| [`06-data-ownership-and-storage`](docs/diagrams/06-data-ownership-and-storage.md) | Table ownership and storage separation |
| [`07-grafana-observability`](docs/diagrams/07-grafana-observability.md) | Two Grafana dashboards |

## Documentation

- [Architecture](docs/Architecture.md)
- [Dataset contract](docs/DatasetContract.md)
- [Phases](docs/Phases.md)
- [Results](docs/Result.md)
- [Phase 4 validation](docs/Validation/phase4_validation_report.md)
- [Phase 5 Grafana validation](docs/Validation/phase5_grafana_validation_report.md)

## Scope Notes

- EEG/ECG ML is not implemented.
- The HAR model is not tennis-specific.
- Clean sensor data and predictions are stored separately.
- Grafana uses InfluxDB as the source of truth.
- This project is validated for thesis-scale live testing, not production deployment.
