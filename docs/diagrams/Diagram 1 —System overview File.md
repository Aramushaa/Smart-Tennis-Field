flowchart LR
    subgraph Sources
        MW[MetaWear Bracelet]
        SD[Siddha Dataset]
        OE[OpenNeuro EEG/ECG Dataset]
    end

    subgraph Adapters_and_Simulators
        MB[metawear_bridge]
        SS[siddha-sensor-sim]
        EES[eeg-dataset-sim]
        ECS[ecg-dataset-sim]
    end

    subgraph Broker
        EMQX[EMQX MQTT Broker]
    end

    subgraph Cleaning
        WC[watch-cleaner-service]
        EEC[eeg-cleaner-service]
        ECC[ecg-cleaner-service]
    end

    subgraph Storage_and_Processing
        ING[ingest-service]
        HAR[har-service]
        DB[(InfluxDB 3)]
    end

    subgraph Visualization
        G[Grafana]
        UI[InfluxDB Explorer]
    end

    MW --> MB --> EMQX
    SD --> SS --> EMQX
    OE --> EES --> EMQX
    OE --> ECS --> EMQX

    EMQX --> WC --> EMQX
    EMQX --> EEC --> EMQX
    EMQX --> ECC --> EMQX

    EMQX --> ING --> DB
    EMQX --> HAR --> DB
    DB --> G
    DB --> UI