# Smart Tennis Field — Implementation Journal

## Purpose of This Document

This document records the implementation journey of the Smart Tennis Field thesis project from Phase 0 to the end of Phase 2.

It explains:

- what was built
- why each step was necessary
- how the system evolved
- what broke
- why it broke
- what was changed to stabilize it

The goal is not only to document the final system, but also to preserve the engineering reasoning, debugging path, and lessons learned along the way.

---

## Scope and Status

This journal records the implemented and validated evolution of the system from Phase 0 through Phase 2.

It is not a speculative roadmap document. Planned work beyond Phase 2 is mentioned only to explain architectural direction, not to claim implementation.

---

## 1. Project Context

The thesis focuses on designing a Docker-based distributed infrastructure for collecting, storing, and later processing multi-sensor data in a Smart Tennis Field scenario.

The core contribution is not only message transport or storage in isolation, but the construction of a complete pipeline that can support future intelligent services.

The central system loop is:

**Data -> Broker -> Storage -> Processing -> Storage -> API**

This meant the work had to be approached incrementally. Before adding machine learning or advanced logic, the system first had to prove that it could:

- reliably move data between services
- persist data without silent corruption
- expose data in a measurable and reproducible way

---

## 2. High-Level Development Strategy

The implementation was intentionally split into phases so that each layer could be validated before adding the next one.

- **Phase 0** focused on MQTT transport
- **Phase 1** focused on ingestion and persistence
- **Phase 2** focused on validating the infrastructure with a real dataset instead of synthetic messages
- **Phase 3** will focus on integrating an existing HAR model as a separate microservice

This sequence matters.

If transport is unstable, storage cannot be trusted. If storage is not structured correctly, processing becomes fragile. Every step was designed to reduce ambiguity and increase reproducibility.

---

## 3. Phase 0 — MQTT Infrastructure

### 3.1 Objective

The objective of Phase 0 was to validate the most basic distributed behavior of the system: a producer publishes an event, a broker routes it, and a consumer receives it correctly.

The goal was not sophistication. The goal was to establish a reliable event backbone before introducing databases or AI logic.

### 3.2 What Was Implemented

The following components were set up:

- EMQX broker in Docker
- simple sensor publisher
- subscriber validating message reception
- initial topic naming conventions
- JSON message transport

The MQTT topic structure adopted during this phase used hierarchical topics such as:

- `tennis/sensor/+/events`
- `tennis/camera/+/ball`

This choice made wildcard subscription easier and kept the topic space organized.

### 3.3 Why This Design Was Chosen

MQTT was selected because the project required a lightweight event-driven communication pattern suitable for IoT devices and distributed services.

The use of a broker allows later expansion to:

- multiple producers
- multiple independent consumers
- resilience experiments
- topic-based routing by modality or source

### 3.4 Problems Encountered in Phase 0

#### Problem 1 — Docker networking versus `localhost`

A recurring conceptual issue early on was the difference between:

- `localhost` on the host machine
- `localhost` inside a container
- service-to-service communication through Docker Compose service names

This caused confusion when services could not connect to the broker even though ports looked correct.

#### Resolution

The project moved toward a consistent rule:

- use service names inside Docker, such as `emqx`
- use host ports such as `localhost:2883` only from the host machine

This became important later for InfluxDB and the simulator as well.

#### Problem 2 — Port mapping confusion

The broker exposed MQTT on container port `1883`, while the host used port `2883`. This created confusion depending on whether the client was inside Docker or outside Docker.

#### Resolution

The communication model was clarified and documented:

- inside Docker: connect to `emqx:1883`
- from the host machine: connect to `localhost:2883`

### 3.5 Outcome of Phase 0

Phase 0 proved that the system could support event-driven communication.

That may sound simple, but academically it established the message backbone for the rest of the thesis. Without this phase, later work on persistence and AI would be built on an unverified transport layer.

---

## 4. Phase 1 — Ingest Service and Time-Series Persistence

### 4.1 Objective

After validating MQTT transport, the next step was to make messages durable and queryable.

The objective of Phase 1 was to build a dedicated ingest microservice that could:

- subscribe to MQTT topics
- normalize incoming events
- persist them in InfluxDB 3
- expose them through a REST API

### 4.2 What Was Implemented

A new microservice called `ingest-service` was created using FastAPI.

Its responsibilities included:

- starting an MQTT background worker
- subscribing to wildcard topics
- normalizing incoming events into a consistent envelope
- storing recent events in an in-memory debug buffer
- persisting events into InfluxDB 3
- exposing REST endpoints

The normalized event structure adopted was:

```json
{
  "ts": "...",
  "topic": "...",
  "source": "mqtt",
  "payload": {}
}
```

This envelope separated:

- transport metadata
- reception and publish timing
- original sensor payload

### 4.3 Why FastAPI Was Used

FastAPI was chosen because the ingest component needed to act as both:

- an always-on background subscriber
- an HTTP API surface for diagnostics and later consumption

FastAPI made that combination convenient while keeping the service lightweight.

### 4.4 Why InfluxDB 3 Was Used

InfluxDB 3 was selected as the persistence layer because the system needed a database optimized for time-series data.

Sensor data is fundamentally temporal, and the project needed:

- timestamp-oriented storage
- efficient time-range queries
- schema suited for telemetry
- Docker-based reproducibility

Using a relational database would have been possible, but less aligned with the structure of the data and weaker from a time-series system design perspective.

### 4.5 Initial Persistence Model

Initially, messages were stored in a generic measurement using an event-style schema:

- tags: `stream`, `source_id`
- field: `payload` as JSON string

This was acceptable for Phase 1 because the goal was durable generic event logging, not yet ML-ready structured storage.

### 4.6 REST Endpoints Added

The service exposed endpoints such as:

- `GET /health`
- `GET /events`
- `POST /publish`

These endpoints made the system easier to debug, inspect, and demonstrate.

### 4.7 Problems Encountered in Phase 1

#### Problem 1 — InfluxDB token handling

InfluxDB 3 uses token-based authentication. A repeated issue was that when the InfluxDB container or storage was recreated, tokens were no longer valid or had to be regenerated.

#### Resolution

A repeatable workflow was adopted:

1. create an admin token inside the container
2. store it in `.env`
3. restart dependent services

This made the process reproducible instead of ad hoc.

#### Problem 2 — Database inspection friction

Compared to tools like pgAdmin, InfluxDB initially felt harder to inspect directly. This slowed early debugging because it was not obvious whether messages were actually being stored.

#### Resolution

The project initially relied on API queries and direct SQL calls for inspection. Later, InfluxDB 3 Explorer was added as a separate UI container to improve schema visibility and manual debugging.

#### Problem 3 — SQL query safety

The `GET /events` route supported time filters, which introduced the risk of unsafe direct interpolation into SQL.

#### Resolution

Timestamp validation was added using ISO-8601 parsing before constructing SQL conditions. This made the route safer and more robust.

### 4.8 Outcome of Phase 1

By the end of Phase 1, the project had evolved from a transport demo into a distributed ingestion system with durable storage and query capability.

This was the first major transformation of the project into something thesis-worthy.

---

## 5. Architectural Shift Introduced in Phase 2

Phase 2 changed the role of the system in a fundamental way.

Before Phase 2, the project behaved mainly as a generic event ingestion system.

After Phase 2, it became a structured, ML-ready ingestion infrastructure with two distinct persistence layers:

- generic event storage (`events`) for tracing and debugging
- structured IMU storage (`imu_raw`) for analytics and future HAR processing

This was more than a schema adjustment. It changed the system model from “log messages durably” to “preserve signals in a form suitable for later computation.”

---

## 6. Phase 2 — Dataset Validation Pipeline

### 6.1 Objective

The objective of Phase 2 was to validate the infrastructure using a **real sensor dataset** instead of synthetic MQTT messages.

The Siddha dataset was chosen because it contains structured IMU data with:

- accelerometer axes
- gyroscope axes
- device information
- activity labels
- timestamps

This phase mattered because it tested the system under realistic data volume and revealed failure modes that do not appear with toy messages.

### 6.2 Simulator Design and Rationale

Instead of loading the dataset directly into the database, the project introduced a new service: `siddha-sensor-sim`.

The simulator behaves like a virtual sensor producer:

- reads rows from the dataset
- transforms them into MQTT payloads
- publishes them through EMQX

This design was chosen because it preserves the architectural contribution of the thesis:

**real data still flows through the broker and the ingest path**

That is academically stronger than bypassing the messaging layer.

### 6.3 Why Parquet Was Used

The Siddha dataset was available in multiple forms, including Parquet and lower-level binary structures.

Parquet was chosen because it offers a strong balance between transparency and structure.

Compared with lower-level binary formats, it is easier to inspect, validate, filter, and replay in Python. This was especially valuable during Phase 2, where correctness and reproducibility were more important than low-level parsing performance.

### 6.4 Structured Storage Transition

Initially, Siddha sensor samples were still being written only as JSON payloads inside the generic `events` measurement.

That was sufficient for generic storage, but not for future HAR processing.

HAR requires direct access to numeric channels such as:

- `acc_x`
- `acc_y`
- `acc_z`
- `gyro_x`
- `gyro_y`
- `gyro_z`

#### Resolution

A dedicated structured IMU write path was added so Siddha samples could also be stored in a separate measurement.

The raw IMU measurement uses:

Tags:

- `device`
- `recording_id`

Fields:

- `acc_x`
- `acc_y`
- `acc_z`
- `gyro_x`
- `gyro_y`
- `gyro_z`
- `dataset_ts`
- `activity_gt`

This was the point where the project changed from a generic event logger into an ML-ready ingestion pipeline.

### 6.5 Debugging Path

#### 6.5.1 Filter bug

Environment variables such as:

- `SIDDHA_DEFAULT_DEVICE_FILTER=`
- `SIDDHA_DEFAULT_ACTIVITY_FILTER=`
- `SIDDHA_DEFAULT_RECORDING_ID_FILTER=`

were initially parsed as empty strings instead of `None`.

That caused the loader to apply filters like:

- `device == ""`

which matched nothing.

##### Resolution

A validation step was added in the simulator config to normalize empty strings to `None` before applying filters.

#### 6.5.2 Startup readiness

Even with Docker Compose dependencies, the simulator or ingest service could attempt to connect before EMQX was actually ready.

##### Resolution

Retry logic was added to services that depend on MQTT, and an EMQX healthcheck was added at the Compose level.

#### 6.5.3 Replay ambiguity

Looping forever was useful for long-running tests, but confusing for deterministic evaluation because the same dataset kept replaying and mixing with previous data.

##### Resolution

Replay behavior was made configurable:

- one-pass mode for deterministic validation
- loop mode for long-running or resilience tests

#### 6.5.4 Throughput bottleneck

Once structured storage worked, a serious performance problem appeared. The simulator reported publishing tens of thousands of samples, but the database contained only a small fraction of them.

At first, the discrepancy appeared to be a pure transport problem. Deeper investigation showed that two independent issues were involved: transport-layer delivery loss and storage-layer timestamp overwrite.

##### Resolution

Ingest service was refactored to decouple MQTT reception from persistence by introducing a queue-based batch writer.

Incoming line protocol writes are enqueued and flushed from a dedicated background writer thread.

This reduced HTTP overhead and removed the main throughput bottleneck of per-message writes.

#### 6.5.5 Schema mismatch

A schema conflict occurred because `activity_gt` had been written inconsistently as a tag in one version and as a field in another.

##### Resolution

The schema was unified so that `activity_gt` remained a string field in the structured IMU measurement.

#### 6.5.6 Timestamp collision

Even after batching, a major discrepancy remained between published samples and stored rows.

The reason was not message loss. The reason was **timestamp collision**.

In InfluxDB, point identity depends on measurement, tags, and timestamp. Many Siddha rows shared the same logical timestamp within the same measurement and tag combination, which caused later rows to overwrite earlier ones.

##### Resolution

A small nanosecond offset was added for duplicate combinations of:

- `device`
- `recording_id`
- `dataset_ts`

This preserved every row while leaving `dataset_ts` intact as the logical signal timestamp.

#### 6.5.7 Fast replay data loss

When running the simulator in `fast` mode with MQTT QoS 0 and non-blocking publish, significantly fewer rows appeared in InfluxDB than were published by the simulator.

##### Resolution

MQTT QoS and `wait_for_publish` were made configurable in the simulator, and the recommended data-critical configuration became:

- QoS 1
- `wait_for_publish=true`

Combined with the batch writer, this produced reliable ingestion for validated runs.

#### 6.5.8 Database naming error

At one point InfluxDB returned HTTP 400 errors because the configured database name contained a dot, which was not valid.

##### Resolution

The database name was changed to a valid underscore-based form and the service was restarted.

### 6.6 False Leads During Investigation

Some early hypotheses turned out to be incomplete or wrong, including:

- assuming low row counts were caused only by MQTT loss
- assuming all published samples were uniquely identifiable in InfluxDB
- assuming generic payload logging was sufficient for future HAR processing

These false leads were useful because they forced a clearer separation between:

- transport reliability
- storage correctness
- processing-readiness

### 6.7 Key Conceptual Clarification: Time

A key conceptual clarification during Phase 2 was that the system contains three different time concepts:

- `dataset_ts`: logical signal time from the Siddha recording
- `ts`: wall-clock publish time in MQTT payloads
- InfluxDB `time`: generated storage timestamp used for point identity

A major part of the debugging process was realizing that these timestamps serve different purposes and cannot be treated as interchangeable.

### 6.8 Final Validated State

At the end of stabilization, the validated replay pass produced the expected stored row count for the tested dataset configuration, confirming that row preservation, batching, and replay controls were working together correctly.

This demonstrated:

- end-to-end ingestion works
- structured raw storage works
- row preservation works without silent overwrites
- performance is acceptable with batching
- the pipeline is deterministic and reproducible
- transport reliability is validated under controlled MQTT configurations

### 6.9 Why Phase 2 Became Thesis-Significant

Phase 2 was not only a validation step. It exposed several distributed-systems issues that are academically meaningful:

- correctness can fail silently at the storage layer
- throughput bottlenecks can masquerade as transport problems
- replay fidelity and delivery reliability are not the same thing
- structured storage is necessary once the system moves toward processing

This phase therefore transformed the project from an infrastructure prototype into a validated experimental system.

---

## 7. Key Lessons Learned from Phases 0–2

### 7.1 Simple architectures break under real data

What works with a handful of toy messages does not necessarily work with tens of thousands of real sensor samples. Phase 2 exposed issues that would never have appeared in a minimal demo.

### 7.2 Reproducibility requires more than Docker

Docker alone is not enough. Reproducibility also depends on:

- consistent schema
- stable configuration
- explicit tokens
- controlled replay behavior
- predictable timestamp handling

### 7.3 Generic JSON storage is not enough for processing

A raw payload log is useful for debugging, but not enough for ML consumption. Structured numeric storage is necessary once the system moves toward processing.

### 7.4 Throughput optimization must be justified

Batching was not added just because it is faster. It was added because the previous design fundamentally limited the system’s ability to validate real data ingestion under load.

### 7.5 Timestamp semantics matter

The distinction between:

- dataset time (`dataset_ts`)
- publish time (`ts`)
- database timestamp (`time`)

turned out to be central. Without explicit handling of these time concepts, both analysis and debugging become unreliable.

### 7.6 Transport reliability is separate from storage correctness

Data loss can occur at two independent layers:

- **storage layer:** timestamp collisions cause silent overwrites regardless of how reliably messages are delivered
- **transport layer:** MQTT QoS 0 under high throughput causes message drops regardless of how correctly storage handles timestamps

Both must be addressed independently. This is a strong thesis finding because it demonstrates that distributed system correctness requires reasoning about each layer separately.

---

## 8. Current Status After Phase 2

The project currently has a stable validated ingestion infrastructure with:

- Dockerized services
- MQTT transport
- structured time-series persistence
- real dataset validation
- measurable performance improvements
- Explorer-based observability

The next logical step is **Phase 3**, where a separate `har_service` will query sliding windows from the raw IMU measurement and run inference using the provided ONNX model and inference engine.

The key rule going forward is:

**processing must remain decoupled from ingestion**

That separation is one of the core architectural strengths of the thesis.

---

## 9. Conclusion

From Phase 0 to Phase 2, the project evolved from a simple MQTT transport experiment into a validated distributed infrastructure capable of ingesting, storing, and preparing real sensor data for downstream AI processing.

The most important outcome is not just that data moved through the system, but that the pipeline became:

- structured
- measurable
- reproducible
- defensible as a thesis contribution

This creates the correct foundation for Phase 3, where the focus will shift from ingestion reliability to decoupled HAR processing.
