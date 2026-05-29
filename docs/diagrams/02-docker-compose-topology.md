```mermaid
flowchart TB
    subgraph Host_Machine
        MB[metawear_bridge<br/>runs locally for BLE]
    end

    subgraph Docker_Compose
        EMQX[emqx<br/>MQTT broker]
        DB[influxdb3]
        EXP[influxdb3-explorer]
        ING[ingest-service]
        HAR[har-service]
        WC[watch-cleaner-service]
        G[grafana]

        subgraph Replay_Profile
            SS[siddha-sensor-sim]
        end

        subgraph Phase6_Profile
            EES[eeg-dataset-sim]
            EEC[eeg-cleaner-service]
            ECS[ecg-dataset-sim]
            ECC[ecg-cleaner-service]
        end
    end

    MB -->|localhost:2883| EMQX
    SS --> EMQX
    EES --> EMQX
    ECS --> EMQX

    EMQX --> WC
    WC --> EMQX
    EMQX --> EEC
    EEC --> EMQX
    EMQX --> ECC
    ECC --> EMQX

    EMQX --> ING
    EMQX --> HAR
    ING --> DB
    HAR --> DB
    DB --> G
    DB --> EXP