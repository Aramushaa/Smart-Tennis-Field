```mermaid
flowchart LR
    MW[MetaWear Bracelet] -->|BLE| MB[metawear_bridge]
    MB -->|tennis/watch/raw| EMQX[EMQX]
    EMQX --> WC[watch-cleaner-service]
    WC -->|tennis/watch/clean| EMQX

    EMQX --> ING[ingest-service]
    ING -->|watch_imu_clean| DB[(InfluxDB)]

    EMQX --> HAR[har-service<br/>MQTT mode]
    HAR -->|real_har_predictions| DB

    DB --> G[Grafana]