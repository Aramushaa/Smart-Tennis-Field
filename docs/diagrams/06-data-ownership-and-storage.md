```mermaid
flowchart TB
    ING[ingest-service<br/>owns clean sensor storage]
    HAR[har-service<br/>owns prediction storage]
    DB[(InfluxDB)]

    ING --> IMU[imu_raw_full_rows<br/>Siddha IMU]
    ING --> WATCH[watch_imu_clean<br/>Real watch IMU]
    ING --> EEG[eeg_clean<br/>EEG fake sensor]
    ING --> ECG[ecg_clean<br/>ECG fake sensor]

    HAR --> HP[har_predictions_7_activity<br/>Dataset predictions]
    HAR --> RP[real_har_predictions<br/>Live watch predictions]

    IMU --> DB
    WATCH --> DB
    EEG --> DB
    ECG --> DB
    HP --> DB
    RP --> DB