```mermaid
flowchart LR
    OD[OpenNeuro ds006848] --> EEGSIM[eeg-dataset-sim]
    OD --> ECGSIM[ecg-dataset-sim]

    EEGSIM -->|tennis/eeg/raw| EMQX[EMQX]
    ECGSIM -->|tennis/ecg/raw| EMQX

    EMQX --> EEGC[eeg-cleaner-service]
    EMQX --> ECGC[ecg-cleaner-service]

    EEGC -->|tennis/eeg/clean| EMQX
    ECGC -->|tennis/ecg/clean| EMQX

    EMQX --> ING[ingest-service]
    ING -->|eeg_clean| DB[(InfluxDB)]
    ING -->|ecg_clean| DB

    DB --> G[Grafana]