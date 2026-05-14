# Data Contracts — Siddha, MetaWear, EEG, and ECG

## Purpose

This document defines the payload and storage contracts used by the Smart Tennis Field system.

The system uses different sources:

- Siddha dataset replay,
- MetaWear watch hardware,
- future EEG dataset source,
- future ECG dataset source.

The goal is to keep every stage explicit:

```text
source format → cleaner / normalizer → canonical clean format → storage / processing
```

---

# 1. Siddha Dataset Contract

## 1.1 Source

The Siddha simulator reads a Parquet dataset.

Required source columns:

| Column | Meaning |
|---|---|
| `device` | source device, usually `phone` or `watch` |
| `activity` | ground-truth activity code |
| `id` | raw recording identifier |
| `timestamp` | logical time inside recording |
| `acc_x`, `acc_y`, `acc_z` | acceleration axes |
| `gyro_x`, `gyro_y`, `gyro_z` | gyroscope axes |

## 1.2 MQTT Topic

```text
tennis/sensor/<device>/events
```

Example:

```text
tennis/sensor/watch/events
```

## 1.3 Normalized Siddha Payload

```json
{
  "device": "watch",
  "recording_id": "F_0",
  "dataset_ts": 12.35,
  "sample_idx": 42,
  "acc_x": 0.1,
  "acc_y": -0.2,
  "acc_z": 9.7,
  "gyro_x": 0.01,
  "gyro_y": -0.02,
  "gyro_z": 0.03,
  "activity_gt": "F"
}
```

## 1.4 Storage Table

```text
imu_raw_full_rows
```

## 1.5 Identity Model

For Siddha IMU rows:

```text
measurement/table + device + recording_id + time
```

where:

```text
recording_id = <activity>_<id>
time = dataset_ts mapped to Influx time
```

`sample_idx` is stored as a field for ordering/debugging, not as the primary identity component.

---

# 2. MetaWear Raw Contract

## 2.1 Source

The MetaWear bracelet streams accelerometer and gyroscope data over BLE.

The bracelet does not publish MQTT directly.

Actual source path:

```text
MetaWear → BLE → metawear_bridge → MQTT
```

## 2.2 Raw MQTT Topic

```text
tennis/watch/raw
```

## 2.3 Raw Payload

The raw payload is hardware-oriented and should not be consumed directly by ingest-service or HAR.

Example:

```json
{
  "source": "metawear",
  "device": "watch",
  "recording_id": "real_metawear_session_001",
  "sensor": "acc",
  "sensor_ts": 1.24,
  "metawear_epoch_ms": 1715678901234,
  "sample_idx": 42,
  "x": 0.12,
  "y": -0.81,
  "z": 0.55,
  "sampling_rate_hz": 25,
  "ts": "2026-05-14T10:15:30Z"
}
```

or:

```json
{
  "source": "metawear",
  "device": "watch",
  "recording_id": "real_metawear_session_001",
  "sensor": "gyro",
  "sensor_ts": 1.24,
  "metawear_epoch_ms": 1715678901234,
  "sample_idx": 42,
  "x": 1.2,
  "y": -0.4,
  "z": 0.8,
  "sampling_rate_hz": 25,
  "ts": "2026-05-14T10:15:30Z"
}
```

---

# 3. MetaWear Clean Contract

## 3.1 Clean MQTT Topic

```text
tennis/watch/clean
```

## 3.2 Cleaner Responsibilities

The watch cleaner must:

- verify required fields exist,
- validate numeric values,
- pair accelerometer and gyroscope data when needed,
- normalize time to seconds since session start,
- add `source = "metawear"`,
- add or preserve `sample_idx`,
- publish complete IMU rows only.

## 3.3 Clean Payload

```json
{
  "source": "metawear",
  "device": "watch",
  "recording_id": "real_metawear_session_001",
  "sensor_ts": 12.48,
  "dataset_ts": 12.48,
  "sample_idx": 312,
  "acc_x": 0.12,
  "acc_y": -0.81,
  "acc_z": 0.55,
  "gyro_x": 1.2,
  "gyro_y": -0.4,
  "gyro_z": 0.8,
  "activity_gt": "unknown",
  "sampling_rate_hz": 25,
  "quality": "ok",
  "ts": "2026-05-14T10:15:31Z"
}
```

`dataset_ts` is preserved for compatibility with existing code. For real sensor documentation, its meaning is:

```text
seconds elapsed since the current recording/session started
```

## 3.4 Storage Table

```text
watch_imu_clean
```

## 3.5 Model Input

The HAR service in MQTT mode consumes this clean topic and builds sliding windows in memory.

---

# 4. HAR Prediction Contract

## 4.1 Storage Table

```text
real_har_predictions
```

## 4.2 Prediction Producer

Predictions are produced and written by:

```text
har-service
```

They should not be routed through ingest-service.

## 4.3 Prediction Row Fields

A prediction row should include:

| Field | Meaning |
|---|---|
| `device` | device used for inference |
| `recording_id` | session identifier |
| `predicted_label` | predicted activity label |
| `confidence` | model confidence |
| `window_start_dataset_ts` | start of input window |
| `window_end_dataset_ts` | end of input window |
| `window_size` | number of samples |
| `window_stride` | stride used |
| `input_layout` | model input layout |
| `model_name` | model identifier if available |

The prediction row should reference the input window, not duplicate all input samples.

---

# 5. EEG Future Contract

## 5.1 Phase

Planned for Phase 6.

## 5.2 Scope

Dataset-based source only.

No EEG ML in the current thesis.

## 5.3 Planned Flow

```text
eeg_dataset_sim
→ eeg_cleaner
→ ingest-service
→ InfluxDB: eeg_clean
```

## 5.4 Example Clean Payload

```json
{
  "source": "eeg_dataset",
  "device": "eeg",
  "recording_id": "eeg_session_001",
  "sensor_ts": 1.24,
  "sample_idx": 128,
  "channel_1": 0.12,
  "channel_2": 0.18,
  "channel_3": -0.05,
  "sampling_rate_hz": 128,
  "quality": "ok"
}
```

Actual fields depend on the selected EEG dataset.

---

# 6. ECG Future Contract

## 6.1 Phase

Planned for Phase 6.

## 6.2 Scope

Dataset-based source only.

No ECG ML in the current thesis.

## 6.3 Planned Flow

```text
ecg_dataset_sim
→ ecg_cleaner
→ ingest-service
→ InfluxDB: ecg_clean
```

## 6.4 Example Clean Payload

```json
{
  "source": "ecg_dataset",
  "device": "ecg",
  "recording_id": "ecg_session_001",
  "sensor_ts": 1.24,
  "sample_idx": 360,
  "ecg_mv": 0.82,
  "sampling_rate_hz": 360,
  "quality": "ok"
}
```

Actual fields depend on the selected ECG dataset.

---

# 7. Storage Rule

The project stores:

```text
clean sensor data
prediction data
```

It does not permanently store every raw hardware callback unless needed for debugging.

Recommended tables:

| Source | Table |
|---|---|
| Siddha IMU | `imu_raw_full_rows` |
| MetaWear clean IMU | `watch_imu_clean` |
| HAR predictions | `real_har_predictions` |
| EEG dataset | `eeg_clean` |
| ECG dataset | `ecg_clean` |
