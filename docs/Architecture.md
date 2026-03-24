# 🏗 Smart Tennis Field — System Architecture

This document describes the structural layout, component boundaries, data paths, and technology choices within the Smart Tennis Field system.

## 1. High-Level Concept

The objective is to ingest high-frequency telemetry data from various endpoints (sensor simulators, vision systems, IoT devices), transport it reliably, persist it as time-series data, and eventually process it for Activity Recognition natively in the cloud/edge. 

### Core Flow
1. **Producer**: Sensor data is generated (e.g., from `siddha-sensor-sim` reading a `.parquet` file).
2. **Broker**: Data is pushed via the MQTT protocol to a central broker (`EMQX`).
3. **Ingest Service**: A FastAPI listener subscribes to wildcard topics, unpacks the dataset payload, adds backend reception timestamps, and formats it as Line Protocol.
4. **Time-Series DB**: the `ingest-service` persists the event directly into `InfluxDB v3`.
5. **Consumption**: Users or microservices (like a future `har-service`) query this data over REST from the API.

## 2. Components Overview

### **EMQX (Message Broker)**
- **Role**: High-availability MQTT broker to handle sensor telemetry.
- **Port**: 1883 for clients, 18083 for Management Dashboard.
- **Responsibility**: Sub-second reliable message fan-out and pub/sub routing.

### **InfluxDB 3 Core (Time Series Database)**
- **Role**: Specialized DB optimized for high-volume time-stamped sensor data.
- **Port**: 8181
- **Storage**: Highly compressed columnar format via Parquet underlying storage format.
- **Data Model**: Follows Line Protocol (`measurement,tag1=val field="json_string" timestamp`).

### **Ingest Service (REST API & MQTT Subscriber)**
- **Role**: Bridging microservice.
- **Technology**: Python (FastAPI, paho-mqtt).
- **Behavior**:
  - Connects to EMQX on startup via background thread.
  - Subscribes to `tennis/sensor/+/events` and `tennis/camera/+/ball`.
  - Catches messages and injects them to InfluxDB.
  - Exposes `GET /events` with safe ISO-8601 query translation, acting as the front-door for querying stored telemetry without exposing the raw InfluxDB to the client.

### **Siddha Sensor Simulator**
- **Role**: Mocks a physical hardware device using the actual Siddha dataset. 
- **Technology**: Python (Pandas, Parquet, MQTT).
- **Behavior**:
  - Parses `data.parquet` and iterates via dataset chunks securely.
  - Computes `time.sleep()` dynamically to natively replicate 1x (real-time) playback speeds or config-based speedups.
  - Handles continuous loop replays so testing streams don't abruptly end.

## 3. Data Schema and Contracts

### MQTT Topic Layout

We utilize hierarchical MQTT routing:
```
tennis/sensor/<device_id>/events
tennis/camera/<camera_id>/ball
```
*Note: Wildcarding (`tennis/sensor/+/events`) effectively enables the ingest service to consume all active devices concurrently.*

### Payload Structure

All payloads use JSON and adhere to a schema matching `DatasetContract.md`. Example:

```json
{
  "device": "phone",
  "recording_id": "48",
  "activity_gt": "A",
  "dataset_ts": 0.05,
  "acc_x": -0.029474,
  "acc_y": -0.186824,
  "acc_z": -0.06387,
  "gyro_x": -0.571848,
  "gyro_y": 3.644636,
  "gyro_z": -9.897467,
  "ts": "2026-03-23T10:00:00Z"
}
```

*Important Metric:* The difference between `dataset_ts` (recording time) and `ts` (wall-clock publish time) and database insertion time allows calculating **end-to-end ingest latency.**
