```mermaid
flowchart LR
    SD[Siddha Parquet Dataset] --> SS[siddha-sensor-sim]
    SS -->|tennis/sensor/&lt;device&gt;/events| EMQX[EMQX]
    EMQX --> ING[ingest-service]
    ING -->|imu_raw_full_rows| DB[(InfluxDB)]
    DB --> HAR[har-service<br/>DB polling mode]
    HAR -->|har_predictions_7_activity| DB