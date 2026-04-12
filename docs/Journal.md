# Smart Tennis Field — Implementation Journal

This document records the implementation journey from Phase 0 to the end of Phase 2: what was built, what broke, and how the system evolved.

For the final-state technical reference, see [Architecture.md](Architecture.md). For the roadmap, see [Phases.md](Phases.md).

---

## 1. Project Context

The thesis focuses on building a Docker-based distributed infrastructure for collecting, storing, and processing multi-sensor data. The central loop is:

**Data → Broker → Storage → Processing → Storage → API**

Before adding ML or advanced logic, the system first had to prove reliable data transport, correct persistence, and reproducible replay.

---

## 2. Phase 0 — MQTT Infrastructure

### What Was Built

- EMQX broker in Docker
- Simple publisher → subscriber validation
- Topic structure: `tennis/sensor/+/events`, `tennis/camera/+/ball`

### Problems Encountered

**Docker networking confusion.** Services could not connect to the broker because `localhost` inside a container is not the same as `localhost` on the host. The project adopted a consistent rule: use service names inside Docker (`emqx`), use mapped ports from the host (`localhost:2883`).

**Port mapping confusion.** MQTT runs on container port `1883` but host port `2883`. Clarified and documented.

### Outcome

Established a reliable event backbone. Simple but necessary — later work on persistence and AI would be built on an unverified transport layer without it.

---

## 3. Phase 1 — Ingest Service and Persistence

### What Was Built

- FastAPI `ingest-service` with background MQTT worker
- Event normalization envelope
- In-memory debug buffer
- InfluxDB 3 persistence with generic event schema
- REST endpoints: `GET /health`, `GET /events`, `POST /publish`
- InfluxDB 3 Explorer added for schema visibility

### Problems Encountered

**InfluxDB token lifecycle.** When the InfluxDB container was recreated, tokens became invalid. Adopted a repeatable workflow: create token → store in `.env` → restart services.

**Database inspection friction.** InfluxDB was harder to inspect than tools like pgAdmin. Initially relied on API queries; later added Explorer UI.

**SQL query safety.** The `GET /events` route supported time filters via direct string interpolation. Added ISO-8601 timestamp validation before constructing SQL conditions.

### Outcome

The project evolved from a transport demo into a distributed ingestion system with durable storage and query capability.

---

## 4. Phase 2 — Dataset Validation

Phase 2 was the most engineering-intensive phase. It changed the system from a generic event logger into an ML-ready ingestion infrastructure.

### Simulator Design

Instead of loading the Siddha dataset directly into the database, a new service (`siddha-sensor-sim`) was introduced as a virtual sensor producer. This preserves the architectural contribution: real data still flows through the broker and ingest pipeline.

### Structured Storage Transition

Initially, Siddha samples were written only as JSON payloads in the generic `events` measurement. This was insufficient for future HAR processing, which needs direct numeric access to sensor channels. A dedicated `imu_raw` measurement was added with structured tags and fields. This was the transition from "log messages durably" to "preserve signals in a form suitable for computation."

### Debugging Path

#### Filter bug

Empty-string env vars (`SIDDHA_DEFAULT_DEVICE_FILTER=`) were parsed as `""` instead of `None`, causing filters like `device == ""` which matched nothing. Fixed by normalizing empty strings to `None` in the simulator config.

#### Startup readiness

Services attempted MQTT connections before EMQX was ready, even with Docker Compose dependencies. Added retry logic and an EMQX healthcheck at the Compose level.

#### Throughput bottleneck

The simulator published tens of thousands of samples, but the database contained only a fraction. Initially assumed to be a pure transport problem. Deeper investigation revealed two independent issues:

1. **Transport-layer delivery loss:** MQTT QoS 0 under high throughput drops messages
2. **Storage-layer identity errors:** duplicate samples silently overwriting each other

The ingest service was refactored to decouple MQTT reception from persistence by introducing a queue-based batch writer.

#### Schema mismatch

`activity_gt` had been written inconsistently as a tag in one version and a field in another, causing InfluxDB schema conflicts. Unified as a string field.

#### Timestamp collision investigation

A dataset subset of ~64,000 rows resulted in only ~5,000 stored rows. Multiple samples shared identical `(device, recording_id, dataset_ts)`, and since InfluxDB uses `measurement + tags + time` as identity, they were overwriting each other.

**Initial attempt (rejected):** Nanosecond offsets on the storage timestamp. Prevented overwrites but introduced artificial time distortion and made debugging harder.

**Final solution:** Explicit `sample_idx` assigned per duplicate group during dataset loading. Propagated through MQTT → ingest → InfluxDB tags. Validated with ~2M rows: all rows stored, no collisions, consistent queries.

The full identity model is documented in [Architecture.md — Data Identity Model](Architecture.md#5-data-identity-model).

#### Fast replay data loss

Running `fast` mode with QoS 0 and non-blocking publish caused significant row loss. Made QoS and `wait_for_publish` configurable. Recommended data-critical configuration: QoS 1 + `wait_for_publish=true`.

#### Database naming error

InfluxDB returned HTTP 400 because the database name contained a dot. Changed to underscore-based naming.

### False Leads

Some early hypotheses were incomplete or wrong:

- Assuming low row counts were caused only by MQTT loss (it was also a data identity problem)
- Assuming all published samples were uniquely identifiable without explicit indexing
- Assuming generic JSON storage was sufficient for future processing

These false leads forced a clearer separation between transport reliability, data identity, and processing readiness.

### Validated Final State

The validated replay pass produced the expected stored row count, confirming that row preservation, batching, and replay controls work together correctly.

---

## 5. Key Lessons Learned

### Simple architectures break under real data

What works with toy messages does not necessarily work with large volumes of real sensor samples. Phase 2 exposed issues that would never appear in a minimal demo.

### Reproducibility requires more than Docker

It also depends on consistent schema, stable configuration, explicit tokens, controlled replay behavior, and explicit data identity handling.

### Generic JSON storage is not enough for processing

A raw payload log is useful for debugging but not for ML consumption. Structured numeric storage is necessary once the system moves toward processing.

### Throughput optimization must be justified

Batching was not added because it is faster. It was added because per-message writes fundamentally limited the system's ability to validate real data ingestion under load.

### Transport reliability is separate from storage correctness

Data loss can occur at two independent layers: storage (silent overwrites from incorrect identity modeling) and transport (QoS 0 message drops). Both must be addressed independently.

---

## 6. Conclusion

From Phase 0 to Phase 2, the project evolved from a simple MQTT transport experiment into a validated distributed infrastructure capable of ingesting, storing, and preparing real sensor data for downstream AI processing.

The most important outcome is not just that data moved through the system, but that the pipeline became structured, measurable, reproducible, and explicitly modeled in terms of data identity.

This creates the foundation for Phase 3, where the focus shifts from ingestion reliability to decoupled HAR processing.
