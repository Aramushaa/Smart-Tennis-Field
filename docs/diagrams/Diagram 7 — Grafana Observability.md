# Diagram 7 — Grafana Observability

```mermaid
flowchart LR
    DB[(InfluxDB 3)] --> G[Grafana]

    subgraph Dashboard_1["Dashboard 1 — Live Watch + HAR Monitoring"]
    end

    subgraph Dashboard_2["Dashboard 2 — EEG/ECG Fake-Sensor Monitoring"]
    end

    G --> Dashboard_1
    G --> Dashboard_2