# Smart Tennis Field — Implementation Journal

## Purpose of this document

This document records the implementation journey of the Smart Tennis Field thesis project from Phase 0 to the end of Phase 2. It explains what was built, why each step was necessary, how the system evolved, and which technical issues were encountered and solved along the way.

The goal of this file is not only to document the final architecture, but also to preserve the engineering reasoning behind the decisions, the debugging process, and the lessons learned. This makes the project easier to defend academically and easier to maintain technically.

---

# 1. Project Context

The thesis focuses on designing a Docker-based distributed infrastructure for collecting, storing, and later processing multi-sensor data in a Smart Tennis Field scenario. The core contribution is not only message transport or storage in isolation, but the construction of a complete pipeline that can support future intelligent services.

The central system loop is:

**Data → Broker → Storage → Processing → Storage → API**

This means the work had to be approached incrementally. Before adding machine learning or advanced logic, the system first had to prove that it could reliably move data between services, persist it, and expose it in a measurable and reproducible way.

---

# 2. High-Level Development Strategy

The implementation was intentionally split into phases so that each layer could be validated before adding the next one.

* **Phase 0** focused on MQTT transport.
* **Phase 1** focused on ingestion and persistence.
* **Phase 2** focused on validating the infrastructure with a real dataset instead of synthetic messages.
* **Phase 3** will focus on integrating an existing HAR(Human Activity Recognition) model as a separate microservice.

This sequence matters. If transport is unstable, storage cannot be trusted. If storage is not structured correctly, processing becomes fragile. Therefore, every step was designed to reduce ambiguity and increase reproducibility.

---

# 3. Phase 0 — MQTT Infrastructure

## 3.1 Objective

The objective of Phase 0 was to validate the most basic distributed behavior of the system: a producer publishing an event, a broker routing it, and a consumer receiving it correctly.

The goal was not sophistication. The goal was to make sure the system had a reliable event backbone before introducing databases or AI logic.

## 3.2 What was implemented

The following components were set up:

* EMQX broker in Docker
* A simple sensor publisher
* A subscriber validating message reception
* Initial topic naming conventions
* JSON message transport

The MQTT topic structure adopted during this phase was aligned with the domain and future scalability needs. Instead of using generic or flat topics, the project introduced hierarchical topics such as:

* `tennis/sensor/+/events`
* `tennis/camera/+/ball`

This choice made future wildcard subscription easier and kept the topic space organized.

## 3.3 Why this design was chosen

MQTT was selected because the project required a lightweight event-driven communication pattern suitable for IoT devices and distributed services. It is a natural fit for decoupled systems where producers and consumers should not depend directly on each other.

The use of a broker also allows later expansion to:

* multiple producers
* multiple independent consumers
* resilience experiments
* topic-based routing by modality or source

## 3.4 Problems encountered in Phase 0

### Problem 1 — understanding Docker networking versus localhost

A recurring conceptual issue early on was the difference between:

* `localhost` on the host machine
* `localhost` inside a container
* service-to-service communication through Docker Compose service names

This caused confusion when services could not connect to the broker even though ports seemed correct.

### Resolution

The project moved toward a cleaner rule:

* use service names inside Docker, such as `emqx`
* use host ports such as `localhost:2883` only from the host machine

This was an important early lesson because it directly affected later configuration for InfluxDB and the simulator as well.

### Problem 2 — port mapping confusion

The broker exposed MQTT on container port `1883`, while the host sometimes used port `2883`. This created confusion depending on whether the client was inside Docker or outside Docker.

### Resolution

The communication model was clarified and documented:

* inside Docker: connect to `emqx:1883`
* from the host machine: connect to `localhost:2883`

## 3.5 Outcome of Phase 0

Phase 0 proved that the system could support event-driven communication. That may sound simple, but academically it established the message backbone of the whole thesis.

Without this phase, later work on persistence and AI would be built on an unverified transport layer.

---

# 4. Phase 1 — Ingest Service and Time-Series Persistence

## 4.1 Objective

After validating MQTT transport, the next step was to make messages durable and queryable. The objective of Phase 1 was to build a dedicated ingest microservice that could:

* subscribe to MQTT topics
* normalize incoming events
* persist them in InfluxDB 3
* expose them through a REST API

## 4.2 What was implemented

A new microservice called `ingest-service` was created using FastAPI.

Its responsibilities included:

* starting an MQTT background worker
* subscribing to wildcard topics
* normalizing incoming events into a consistent envelope
* storing recent events in an in-memory debug buffer
* persisting events into InfluxDB 3
* exposing REST endpoints

The normalized event structure adopted was:

```json
{
  "ts": "...",
  "topic": "...",
  "source": "mqtt",
  "payload": {...}
}
```

This envelope was important because it separated:

* transport metadata
* reception timestamping
* original sensor payload

## 4.3 Why FastAPI was used

FastAPI was chosen because the ingest component needed to act as both:

* an always-on background subscriber
* an HTTP API surface for diagnostics and later consumption

FastAPI made that combination convenient while keeping the service lightweight.

## 4.4 Why InfluxDB 3 was used

InfluxDB 3 was selected as the persistence layer because the system needed a database optimized for time-series data. Sensor data is fundamentally temporal, and the project needed:

* timestamp-oriented storage
* efficient time-range queries
* schema suited for telemetry
* Docker-based reproducibility

Using a relational database would have been possible, but less aligned with the structure of the data and weaker from a time-series system design perspective.

## 4.5 InfluxDB integration details

The ingest service integrated with InfluxDB 3 through:

* `write_lp` for writes
* `query_sql` for reads

This allowed the system to both persist and inspect data programmatically.

Initially, messages were stored in a generic measurement using an event-style schema:

* tags: `stream`, `source_id`
* field: `payload` as JSON string

This was acceptable for Phase 1 because the goal was generic persistence rather than machine-learning-ready schema design.

## 4.6 REST endpoints added

The service exposed endpoints such as:

* `GET /health`
* `GET /events`
* `POST /publish`

These endpoints made the system easier to debug, inspect, and demonstrate.

## 4.7 Problems encountered in Phase 1

### Problem 1 — InfluxDB token handling

InfluxDB 3 uses token-based authentication. A repeated issue was that when the InfluxDB container or storage was recreated, tokens were no longer valid or had to be regenerated.

### Resolution

A repeatable workflow was adopted:

1. create an admin token inside the container
2. store it in `.env`
3. restart services that depend on it

This made the process reproducible instead of ad hoc.

### Problem 2 — inability to inspect the database easily

Compared to tools like pgAdmin, InfluxDB initially felt harder to inspect directly. This made early debugging slower because it was not obvious whether messages were really being stored.

### Resolution

The project relied on:

* the `GET /events` API route
* direct SQL queries against `/api/v3/query_sql`
* later, the idea of adding InfluxDB Explorer or similar UI support

### Problem 3 — SQL query safety

The `GET /events` route supported time filters, which introduced the risk of unsafe direct interpolation into SQL.

### Resolution

Timestamp validation was added using ISO-8601 parsing before constructing SQL conditions. This made the route safer and more robust.

## 4.8 Outcome of Phase 1

By the end of Phase 1, the project had evolved from a transport demo into a distributed ingestion system with durable storage and query capability.

This was the first major transformation of the project into something thesis-worthy.

---

# 5. Phase 2 — Dataset Validation Pipeline

## 5.1 Objective

The objective of Phase 2 was to validate the infrastructure using a **real sensor dataset** instead of synthetic MQTT messages.

The Siddha dataset was chosen for this validation because it contains structured IMU(Inertial Measurement Unit) data with:

* accelerometer axes
* gyroscope axes
* device information
* activity labels
* timestamps

This phase mattered because it proved that the system could handle real data, not only test messages.

## 5.2 Why a simulator was created

Instead of loading the dataset directly into the database, the project introduced a new service: `siddha-sensor-sim`.

The simulator behaves like a virtual sensor producer:

* reads rows from the dataset
* transforms them into MQTT payloads
* publishes them through EMQX

This design was chosen because it preserves the architectural contribution of the thesis:

**real data still flows through the broker and the ingest path**

That is academically stronger than bypassing the messaging layer.

## 5.3 What was implemented in the simulator

The simulator includes:

* Parquet loading
* required-column validation
* deterministic ordering by recording and timestamp
* MQTT topic construction
* JSON payload generation
* support for replay modes
* support for filters
* broker retry logic
* configurable loop behavior

The payload includes both:

* `dataset_ts` → timestamp inside the original dataset
* `ts` → wall-clock publish time

This separation was important because it preserves both:

* logical signal time
* system-level event creation time

## 5.4 Why Parquet was used

The Siddha dataset was available in multiple formats, including Parquet and binary structures.

Parquet was chosen because it is:

* easy to inspect in Python
* structured
* deterministic
* more transparent for debugging

For thesis work, transparency and reproducibility were more valuable at this stage than low-level binary parsing complexity.

## 5.5 Initial Phase 2 problems

### Problem 1 — empty-string filters silently removed all data

Environment variables for filters such as:

* `SIDDHA_DEFAULT_DEVICE_FILTER=`
* `SIDDHA_DEFAULT_ACTIVITY_FILTER=`
* `SIDDHA_DEFAULT_RECORDING_ID_FILTER=`

were parsed as empty strings, not `None`.

That caused the loader to apply filters like:

* `device == ""`

which matched nothing.

### Resolution

A validation step was added in the simulator config to normalize empty strings to `None` before applying filters.

This fixed the “0 samples published” issue.

### Problem 2 — broker readiness on startup

Even with Docker Compose dependencies, the simulator or ingest service could attempt to connect before EMQX was actually ready.

### Resolution

Retry logic was added to services that depend on MQTT. In addition, an EMQX healthcheck was added at the Compose level.

This improved startup robustness.

### Problem 3 — replay mode ambiguity

Looping forever was useful for long-running tests, but confusing for deterministic evaluation because the same dataset kept replaying and mixing with previous data.

### Resolution

Replay behavior was made configurable:

* one-pass mode for deterministic validation
* loop mode for long-running or resilience tests

This distinction became important later for clean experiments.

## 5.6 Structured IMU storage problem

Initially, even Siddha sensor samples were still being written only as JSON payloads inside the generic `events` measurement.

That was sufficient for generic storage, but not for future HAR processing.

HAR needs direct access to numeric channels such as:

* `acc_x`
* `acc_y`
* `acc_z`
* `gyro_x`
* `gyro_y`
* `gyro_z`

### Resolution

A dedicated structured IMU write path was added so Siddha samples could also be stored as a separate measurement.

The raw IMU measurement uses:

**Tags**

* `device`
* `recording_id`

**Fields**

* `acc_x`
* `acc_y`
* `acc_z`
* `gyro_x`
* `gyro_y`
* `gyro_z`
* `dataset_ts`
* `activity_gt`

This changed the project from a generic event logger into an ML-ready ingestion pipeline.

## 5.7 Major performance bottleneck discovered

Once structured storage worked, a serious performance problem appeared.

The simulator reported publishing tens of thousands of samples, but the database contained only a tiny fraction of them.

At first this looked like message loss, but deeper debugging revealed multiple bottlenecks.

### Problem 4 — one HTTP write per message

The original ingest implementation wrote one HTTP request to InfluxDB per incoming message.

This design was simple, but highly inefficient under real dataset load.

### Resolution — batch writer thread

The ingest service was redesigned to enqueue line protocol writes and flush them in batches from a background writer thread.

Batch size and flush interval became configurable.

This produced a large throughput improvement and reduced overhead dramatically.

This was one of the most important Phase 2 engineering upgrades.

### Problem 5 — MQTT publishing blocked too much

At some points the simulator was too slow because publishing behavior became effectively blocking.

### Resolution

MQTT publishing behavior was made configurable with QoS and optional wait-for-publish semantics, allowing the simulator to run non-blocking by default while still supporting more controlled experiments when needed.

### Problem 6 — Influx schema mismatch

A schema conflict occurred because `activity_gt` had been written inconsistently as a tag in one version and as a field in another.

### Resolution

The schema was unified so that the measurement definition remained consistent with existing data.

### Problem 7 — timestamp collision and point overwrite

Even after batching, a major discrepancy remained between published samples and stored rows.

The reason was not message loss. The reason was **timestamp collision**.

In InfluxDB, point identity depends on measurement + tags + timestamp. Many Siddha rows shared the same logical timestamp within the same measurement/tag combination, which caused later rows to overwrite earlier ones.

### Resolution

A small nanosecond offset was added for duplicate combinations of:

* `device`
* `recording_id`
* `dataset_ts`

This preserved every row while leaving `dataset_ts` intact as the logical signal timestamp.

This fix was essential. Without it, the raw measurement could never reflect the actual number of ingested samples.

### Problem 8 — invalid database naming

At one point InfluxDB returned HTTP 400 errors because the configured database name contained a dot, which was not valid.

### Resolution

The database name was changed to a valid underscore-based form and the service was restarted.

## 5.8 Final validated outcome of Phase 2

At the end of the debugging and stabilization process, the simulator completed a full pass and the raw measurement contained the expected number of rows.

This demonstrated:

* end-to-end ingestion works
* structured raw storage works
* row preservation works
* performance is acceptable with batching
* the pipeline is deterministic and reproducible

This is the point where the project stopped being “just infrastructure setup” and became a validated distributed ingestion system.

---

# 6. Key Lessons Learned from Phases 0–2

## 6.1 Simple architectures break under real data

What works with a handful of toy messages does not necessarily work with tens of thousands of real sensor samples. Phase 2 exposed issues that would never have appeared in a minimal demo.

## 6.2 Reproducibility requires more than Docker

Docker alone is not enough. Reproducibility also depends on:

* consistent schema
* stable configuration
* explicit tokens
* controlled replay behavior
* predictable timestamps

## 6.3 Generic JSON storage is not enough for processing

A raw payload log is useful for debugging, but not enough for ML consumption. Structured numeric storage is necessary once the system moves toward processing.

## 6.4 Throughput optimization must be justified

Batching was not added just because it is “faster.” It was added because the previous design fundamentally limited the system’s ability to validate real data ingestion under load.

## 6.5 Timestamp semantics matter

The distinction between:

* dataset time
* publish time
* database timestamp

turned out to be central. Without explicit handling of these time concepts, both analysis and debugging become unreliable.

---

# 7. Current Status After Phase 2

The project currently has a stable validated ingestion infrastructure with:

* Dockerized services
* MQTT transport
* structured time-series persistence
* real dataset validation
* measurable performance improvements

The next logical step is **Phase 3**, where a separate `har_service` will query sliding windows from the raw IMU measurement and run inference using the provided ONNX model and inference engine.

The key rule going forward is:

**processing must remain decoupled from ingestion**

That separation is one of the core architectural strengths of the thesis.

---

# 8. Conclusion

From Phase 0 to Phase 2, the project evolved from a simple MQTT transport experiment into a validated distributed infrastructure capable of ingesting, storing, and preparing real sensor data for downstream AI processing.

The most important outcome is not just that data moved through the system, but that the pipeline became:

* **structured**
* **measurable**
* **reproducible**
* **defensible as a thesis contribution**

This creates the correct foundation for Phase 3, where the focus will shift from ingestion reliability to decoupled HAR processing.
