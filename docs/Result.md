# HAR Model Evaluation — Results

## 1. Phase 3 Evaluation Setup

Phase 3 evaluated the ONNX HAR model on stored Siddha watch data.

| Parameter | Value |
|---|---|
| Model | `L2MU_plain_leaky.onnx` |
| Device filter | `watch` |
| Supported labels | `F, G, O, P, Q, R, S` |
| Input layout | `gyro_then_accel` |
| Temporal preprocessing | `none` |
| Score aggregation | `sum` |
| Storage input table | `imu_raw_full_rows` |
| Prediction output table | `har_predictions_7_activity` |

The model does not support all 18 Siddha activities. It supports only seven classes.

---

## 2. Validated 7-Activity Result

The validated evaluation on the seven supported activities produced:

```text
119 / 140 correct = 85.0% overall accuracy
```

Supported activities:

| Code | Activity |
|---|---|
| F | Typing |
| G | Brushing Teeth |
| O | Playing Catch / Tennis-related catch |
| P | Basketball Dribbling |
| Q | Writing |
| R | Clapping |
| S | Folding Clothes |

---

## 3. Important Interpretation

The Phase 3 result proves:

- the pipeline can fetch ordered IMU rows from InfluxDB,
- sliding windows can be built deterministically,
- the ONNX model can run inside the HAR service,
- predictions can be written back to InfluxDB,
- the selected preprocessing configuration is valid for this model.

It does not prove:

- full 18-activity classification,
- reliable prediction for phone data,
- medically or professionally validated activity recognition,
- guaranteed accuracy on real MetaWear motion.

---

## 4. Phase 4 Live Pipeline Validation

Phase 4 validated the real MetaWear live pipeline. It was not primarily an accuracy test; it validated acquisition, cleaning, ingestion, HAR inference, and prediction storage.

Validated pipeline:

```text
MetaWear → bridge → cleaner → ingest + HAR → prediction storage
```

| Metric | Result |
|---|---:|
| Streaming duration | ~385 seconds |
| Clean IMU rows stored | 9,599 |
| HAR predictions stored | 463 |
| Approx. clean row rate | ~24.9 rows/sec |
| Approx. prediction interval | ~0.83 sec |
| Ingest queue depth | 0 |
| Failed batches | 0 |
| Retried lines | 0 |
| Dropped lines | 0 |

---

## 5. Phase 4 Prediction Output

Real watch predictions are stored in:

```text
real_har_predictions
```

The prediction row references the input window by:

```text
recording_id
window_start_dataset_ts
window_end_dataset_ts
```

It does not duplicate all raw input samples.

---

## 6. Visualization Interpretation

Grafana is used to visualize:

- real watch IMU signal history,
- current/last predicted activity,
- prediction confidence over time,
- prediction history by session,
- later EEG/ECG signals.

Grafana auto-refresh from InfluxDB is the required implementation.

Grafana Live / MQTT visualization was considered but not used in the final Phase 5 design because InfluxDB-backed Grafana panels refresh at 1 second and remain tied to persistent stored data.

---

## 7. Phase 5 Visualization Result

Phase 5 completed the visualization layer.

Implemented visualization path:

```text
InfluxDB → Grafana
```

The Grafana dashboard shows:

- live watch IMU signals from `watch_imu_clean`,
- current/last predicted activity from `real_har_predictions`,
- prediction confidence,
- confidence over time,
- prediction history,
- stored clean IMU row count,
- stored prediction count.

The dashboard uses a 1-second refresh interval. This was sufficient for the live HAR pipeline, where predictions are produced approximately every 0.8 seconds.

The final Phase 5 design does not require MQTT/Grafana Live.
