# Phase 5 Validation Report — Grafana Visualization

## Goal

Validate that Grafana can visualize the live Smart Tennis Field pipeline using InfluxDB as the source of truth.

## Implemented Flow

MetaWear → BLE → metawear_bridge → EMQX → watch_cleaner_service → ingest-service → InfluxDB → HAR service → InfluxDB → Grafana

## Data Sources

- `watch_imu_clean`
- `real_har_predictions`

## Dashboard Panels

| Panel | Source table | Purpose |
|---|---|---|
| Current Predicted Activity | real_har_predictions | Show latest HAR output |
| Current Confidence | real_har_predictions | Show prediction reliability |
| Prediction Timeline | real_har_predictions | Show prediction changes over time |
| Live Accelerometer | watch_imu_clean | Show real watch movement |
| Live Gyroscope | watch_imu_clean | Show wrist rotation |
| Prediction History | real_har_predictions | Debug/audit prediction rows |
| Stored Clean IMU Rows | watch_imu_clean | Validate ingestion |
| Stored Predictions | real_har_predictions | Validate HAR output storage |

## Refresh Configuration

Grafana minimum refresh interval was configured to 1 second:

```env
GF_DASHBOARDS_MIN_REFRESH_INTERVAL=1s
```

## Validation Result

- Dashboard opened successfully at http://localhost:3000
- InfluxDB datasource connected
- Live IMU panels displayed rows from `watch_imu_clean`
- Prediction panels displayed rows from `real_har_predictions`
- Dashboard refresh set to 1 second
- MQTT optional visualization was not used because InfluxDB refresh was sufficient for thesis-scale live visualization

## Conclusion

Phase 5 validates the visualization layer. InfluxDB remains the persistent and reproducible source of truth, while Grafana provides live monitoring and historical inspection.
