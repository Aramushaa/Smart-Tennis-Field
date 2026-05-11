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

## 4. Phase 4 Evaluation Plan

Phase 4 is not mainly about accuracy.

Phase 4 validates the real-time pipeline:

```text
MetaWear → bridge → cleaner → ingest + HAR → prediction storage
```

Evaluation metrics should include:

| Metric | Why it matters |
|---|---|
| clean rows per second | verifies acquisition and cleaner throughput |
| dropped clean samples | verifies cleaner reliability |
| ingest queue depth | verifies storage can keep up |
| HAR prediction latency | verifies real-time behavior |
| predictions per second | verifies processing throughput |
| confidence over time | supports visualization |
| end-to-end delay | proves demo responsiveness |

---

## 5. Phase 4 Prediction Output

Real watch predictions are stored in:

```text
real_har_predictions
```

The prediction row references the input window by:

```text
recording_id
window_start_ts
window_end_ts
```

It does not duplicate all raw input samples.

---

## 6. Visualization Interpretation

Grafana will be used to visualize:

- real watch IMU signal history,
- current/last predicted activity,
- prediction confidence over time,
- prediction history by session,
- later EEG/ECG signals.

Grafana auto-refresh from InfluxDB is the required implementation.

Grafana Live is an optional enhancement only if verified and implemented.
