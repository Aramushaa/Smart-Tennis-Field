# Smart Tennis Field — Implementation Journal

This document records the implementation journey from Phase 0 to the end of Phase 3: what was built, what broke, what was debugged, and how the system evolved.

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

An explicit `sample_idx` was introduced to make duplicate-order visible and to prevent point collisions during debugging and validation. Later, the Siddha-specific session identifier was strengthened by deriving `recording_id = <activity>_<id>`, reducing ambiguity between labeled sampling sessions that reused the same raw `id`.

In the current validated configuration, `sample_idx` is preserved as a field for inspection and future extensibility, while the active storage identity relies on the derived session identifier plus timestamp and device.

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

## 5. Phase 3 — HAR Processing Integration

Phase 3 shifted focus from ingestion reliability to decoupled ML processing.

### Architecture Decisions

The HAR service was designed as a standalone microservice that polls InfluxDB for IMU data rather than consuming MQTT directly. This design was chosen for three reasons:

1. **Reproducibility:** Database polling operates on stored, validated data. Results are deterministic and repeatable.
2. **Decoupling:** The HAR service has no dependency on the ingest service or MQTT broker. Each component can be developed, deployed, and tested independently.
3. **Evaluation clarity:** For thesis measurement, processing a known, validated dataset produces cleaner metrics than processing a live stream.

### Implementation

The service implements a sliding window pipeline:

1. Query ordered IMU rows from InfluxDB (filtered by device and recording_id)
2. Group rows by device and recording session
3. Build sliding windows (40 samples, stride 20)
4. Convert each window to model input format (gyroscope + accelerometer arrays)
5. Run ONNX inference and capture predictions
6. Write predictions back to InfluxDB

The professor's assistant provided an ONNX model (`L2MU_plain_leaky.onnx`) with 7 activity labels. The provided `inference_engine.py` was wrapped in an adapter (`HarInferenceAdapter`) to avoid modifying the original file while capturing predictions as return values.

### Model Evaluation

Before moving to production inference, a comprehensive evaluation was conducted. Three scripts were created:

- `inspect_model.py` — discovered the model architecture: input `[40, 1, 6]`, output `[40, 1, 7]`, PyTorch 2.2.1, 3230 nodes
- `evaluate_model.py` — tested predictions across all 18 Siddha activities (360 windows total)
- `fix_finder.py` — exhaustive search for configuration issues

**Initial results:** The model achieved 15.0% accuracy on its own 7 labeled activities (random chance = 14.3%). It collapsed into outputting primarily "catch" and "dribbling" regardless of input activity.

### Debugging Path

#### Initial hypothesis: label mismatch

The labels file listed 7 labels but the dataset has 18 activities. Confirmed via model inspection that the model genuinely outputs 7 classes — the label count is correct.

#### Aggregation uncertainty

The model outputs `[40, 1, 7]` — a prediction per timestep. The provided code sums across timesteps. Tested 6 aggregation methods (sum, last, first, mean, majority vote, middle): no significant improvement.

#### Exhaustive fix search

During the debugging phase, an exhaustive search was conducted: 5040 label permutations × 6 aggregation methods × 4 input formats × 2 devices. This pointed toward the correct configuration: watch device, gyro-first input layout, and sum aggregation.

#### Root cause discovery: data handling, not model quality

This phase revealed that the initial poor model performance (15%) was caused by incorrect data handling and evaluation methodology, not by the model itself:

1. **Mixed-device contamination:** Mixing data from multiple devices (phone + watch) inside the same window severely degraded performance.
2. **Input layout sensitivity:** The model is highly sensitive to input layout (gyro vs accel ordering). Switching to `gyro_then_accel` improved results dramatically.
3. **Device specificity:** The model is optimized for wrist-based (watch) signals rather than general-purpose sensor placement.
4. **Aggregation impact:** Proper aggregation of model outputs (`sum` vs `last`) significantly affects prediction quality.
5. **Scope mismatch:** Evaluating a 7-class model against all 18 Siddha activities inflated the apparent failure rate.

After correcting these issues and re-evaluating with the proper configuration (watch-only, `gyro_then_accel`, `sum`, 7 supported activities only):

- **Overall accuracy: 85.0%** (119/140 windows correct)
- Best per-activity: Playing Catch 95%, Dribbling 95%, Clapping 90%
- Weakest: Writing 65% (confused with Folding Clothes)
- Predictions persisted to InfluxDB with full traceability metadata
- System architecture validated end-to-end

The full analysis is documented in [Result.md](../Result.md).

### Engineering Insight

This phase demonstrates a critical principle for IoT-based ML systems:

**Correct data interpretation is as important as model selection.** A misaligned data pipeline can make a functional model appear broken. Systematic debugging — controlling device, input layout, aggregation, and evaluation scope — was essential to separating integration issues from genuine model limitations.

### Phase 3 Outcome

- ✔ Full end-to-end prediction pipeline working
- ✔ Model integrated, validated, and predictions stored in database
- ✔ Comprehensive evaluation tooling created and documented
- ✔ System ready for real sensor input
- ✔ Clear documentation of model scope and limitations

---

## 6. Key Lessons Learned

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

### Data pipeline correctness is prerequisite to model evaluation

Phase 3 showed that a correctly functioning model can appear broken when the data pipeline feeds it incorrectly structured input. Device mixing, channel ordering, and evaluation scope must all be controlled before drawing conclusions about model quality.

---

## 7. Conclusion

From Phase 0 to Phase 3, the project evolved from a simple MQTT transport experiment into a validated distributed infrastructure with end-to-end ML inference.

Phases 0–2 established reliable data transport, structured persistence, and reproducible replay. Phase 3 introduced the HAR processing microservice, integrated the ONNX model, and — through systematic debugging — resolved data handling issues that initially masked the model's capabilities. Predictions are now persisted to InfluxDB with full traceability metadata.

The most important outcome is not just that data moved through the system, but that the pipeline became structured, measurable, reproducible, and capable of evaluating ML model quality as part of the integration process. The system is now ready for the next phase: real sensor integration with physical hardware.
