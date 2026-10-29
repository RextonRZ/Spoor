# Spoor — Product Requirements Document (v3: Validated Multi-View 3D + Confirmed Credits)

> **Project name: Spoor**. An evidence-grounded, multi-agent spatial intelligence system that turns existing CCTV recordings and optional sensor events into a queryable history of physical objects and observed movements. Investigators can reconstruct an incident inside a calibrated 3D environment, trace every claim back to original footage, and see where the evidence ends.
>
> **One line:** *"Give physical spaces a searchable memory — and every answer a source."*
>
> **Hackathon:** Meta Global AI Developer Hackathon 2026 · **Theme:** Push the Frontier · **Primary concept:** physical-event reconstruction, not automated crime accusation.

---

## 0. How to read this document (for the coding agent)

This is a **build-ready product specification**, modeled after the structure and philosophy of the provided Penjaga PRD. It defines product intent, contracts, model responsibilities, safeguards, evaluation, and the experience that should actually work. It is not a claim that the product has already been built. **Think, research, measure, and improve the design.**

### 0.1 Three instruction levels

| Level | Marker | Meaning |
|---|---|---|
| **Invariant** | 🔒 | Protects evidence integrity, privacy, truthfulness, safety, rights, and hackathon eligibility. Do not weaken without explicit approval. |
| **Default** | 🧭 | Preferred implementation; change if tests or current official documentation justify a better solution. |
| **Open** | 🎨 | Explore viable implementations and document the final choice. |

Unmarked requirements are 🧭 defaults.

### 0.2 Intent over rigid implementation

**Product intent:** Help an authorized human establish *what was observed, when, where, and with what uncertainty* from fragmented video, rather than drawing unsupported conclusions. Preserve this intent even if an implementation differs from suggestions here.

### 0.3 Cook dynamically

1. Verify official current documentation and licenses before implementation.
2. Prototype risky assumptions early, especially object tracking, camera mapping, Meta video inputs, and clip costs.
3. Benchmark a simple baseline before adding agents or advanced memory.
4. Adopt a better approach when supported by evidence; record trade-offs in `docs/DECISIONS.md`.
5. Never simulate AI detections and present them as genuine inference results.

### 0.4 Third-party technology rule 🔒

- Consult **current official docs/model cards** before coding any Meta API calls or third-party integrations; pin tested versions.
- Confirm input modalities, API endpoint, content size/length limits, rate limits, output parsing, retention terms, and version identifiers in code.
- Maintain `docs/DEPENDENCIES.md` with name, pin, official reference, license, and date checked.
- Keep API secrets off the client and out of public repositories; user media must not be submitted to third-party providers without authorization.
- Favor reproducible, measured approaches over claims of novelty or unverified benchmarks.

### 0.5 Quality over feature count 🔒

No required feature may depend on hardcoded demo outcomes. A carefully validated single-room investigation is better than a polished fake multi-building product. Do not manufacture certainty, fingerprints, hidden faces, or a person's criminal intent.

---

## 1. Context

### 1.1 Hackathon and track

- **Event:** Meta Global AI Developer Hackathon 2026, hosted with Cerebral Valley.
- **Theme:** **Push the Frontier** — demonstrate a new or meaningfully improved machine capability for understanding the physical world.
- **Entry:** Indie Developer track if participating as an individual/student; verify actual enrollment/team configuration before submission.
- **Submission:** public repository, working product, and a **3-minute video** clearly showing work created during the hackathon.
- **New-work rule 🔒:** Build and document qualifying contributions during the event. Existing libraries, permitted components or old projects must not be represented as newly created; startups may extend existing products if the new work is explicitly identified. Preserve source and creation history.
- **Bonus relevance:** Best Agentic Use-Case is potentially relevant; Best Build on Meta Open Weight Models only if an eligible model actually runs through qualifying inference infrastructure. No award is guaranteed.

### 1.2 Judging alignment

The written participant guide says the four rubric categories are **equally weighted (25% each)**, while the later kickoff slide supplied by the team shows **Impact 30%, Meta AI Tooling 25%, Technical Depth 20%, Demo 25%**. This conflict must be confirmed in the organizers' Discord; **never quietly present one as authoritative**.

| Criterion | How Spoor will provide evidence |
|---|---|
| Impact | Reduce time spent reviewing authorized CCTV in a concrete missing-object investigation; compare with manual search. |
| Creative use of Meta AI | Combine Muse Spark 1.3 for targeted multimodal reasoning and SAM 3.1 for grounded object masks/tracks; let agents request additional evidence. |
| Technical depth | Event-sourced memory, camera calibration, uncertainty, provenance, cross-camera association abstention, orchestration, recovery and evaluations. |
| Demo | A staged incident becomes an interactive 3D replay; user clicks any claim to inspect source frames and sees unknown intervals marked honestly. |

### 1.3 Positioning and differentiation

**Not:** another AI CCTV alert dashboard, face recognition engine, theft predictor, video summarizer, or beautiful 3D animation disconnected from footage.

**Is:** a tool that reasons over an evolving *evidence graph*: observed object positions, relationships, timestamps, possible cross-camera links, unresolved questions, and the provenance of each conclusion. The memorable capability is **investigate → request evidence → revise hypothesis → verify → replay in space**.

Differentiation from existing video analytics/agent monitoring products is a **hypothesis to test**, not a market-exclusivity claim. Compare against a plain video-language-model Q&A baseline and a deterministic change-detection baseline before describing performance benefits.

---

## 2. Problem

When a laptop, tool, parcel, or other valuable item goes missing from a physical environment, staff often need to:

1. Identify which cameras cover the relevant area.
2. Scrub many hours of recording with incompatible camera layouts and timestamps.
3. Track objects across occlusion, movement, and changes of camera view.
4. Reconstruct approximate routes from fragmented observations.
5. Distinguish footage that directly supports a conclusion from assumptions made between clips.
6. Record a defensible case timeline and share relevant excerpts for human review.

CCTV is **passive video**, not a unified representation of the physical world. Many vision models can describe frames, but a fluent description can still be temporally wrong, spatially inconsistent, or entirely unsupported by actual imagery.

**Opening product question:** *"Where was the missing item last **verified**, and what evidence would establish where it went next?"*

---

## 3. Product vision

### 3.1 What Spoor does

The user provides authorized video clips from one or more cameras and a floor plan or manually defined room layout. The system:

1. Ingests recordings while preserving original files, metadata and cryptographic hashes.
2. Establishes a synchronized timeline and camera coverage map.
3. Detects/tracks requested objects and people as **anonymous visual tracks**, with observations linked to frames.
4. Resolves valid floor-contact observations onto a measured floor plane and shows them in a 3D digital twin; **optionally** reconstructs true `(x,y,z)` positions where synchronized overlapping, calibrated camera views independently support triangulation.
5. Maintains a versioned **spatiotemporal evidence graph** — items, tracks, zones, observed interactions and gaps.
6. Lets the investigator ask evidence-focused questions in natural language.
7. Orchestrates specialists to search, reconstruct, test and verify possible event histories.
8. Returns a replayable evidence timeline, annotated source clips, observed trajectories and explicitly unverified connections.
9. Accepts authorized additional cameras or sensor logs to revise findings with a full audit trail.
10. Produces an exportable **investigation-support packet** with source references, hashes, methodology and limitations — **not** a certified forensic or legal conclusion.

### 3.2 Architectural truth 🔒

> **Muse Spark interprets. SAM 3.1 sees object regions. The geometry engine maps. The memory stores observations. The verification agent challenges. The human decides.**

- **Models are not sensors:** LLM text is not ground-truth location data.
- **Segmentation is not identification:** A track ID within one video does not identify a real person and does not automatically persist across cameras.
- **A 3D animation is not evidence:** It must be generated from explicit spatial measurements/estimates tied to source observations.
- **Multiple agents are not automatically more reliable:** Each agent has an accountable role, structured contract, tool budget, and verifiable output.

### 3.3 What the system is NOT 🔒

- Not autonomous criminality detection, predictive policing, or automated suspect identification.
- No facial recognition against external databases, reconstructed hidden faces, inferred fingerprints, gait-based identity matching, emotion/protected-attribute inference, or accusations of theft.
- No "this person definitely took it" without reliable evidence; observed contact/motion is not intent or guilt.
- Not a replacement for trained investigators, chain-of-custody procedures, or forensic certification.
- Not a fully automatic 3D reconstruction of arbitrary locations from one uncalibrated CCTV clip.
- Not an always-on public surveillance tool or public-space tracking platform.

---

## 4. Users and access boundaries

| Persona | Task | Requirement |
|---|---|---|
| **Primary: authorized site investigator / asset custodian** | Find last visible location, reconstruct observed object movement | Interactive timeline, trusted source links, obvious uncertainty |
| **Secondary: warehouse / lab manager** | Understand an operational incident and recover misplaced equipment | Fast case intake, clear evidence summary, minimal setup |
| **Technical installer / site admin** | Import site plan and camera layout, calibrate viewpoints | Simple calibration UI, coverage checks, schema validation |
| **Reviewer / supervisor** | Independently audit AI conclusions | Original footage, confidence/limitations, version history and export |
| **Potential customer (future)** | Integrate existing camera systems | Hardware-independent software, retention and security controls |

**Roles:** `site_admin`, `investigator`, `reviewer` with enforced least privilege. Keep users from other sites/tenants isolated. Staged fictional demo identities only.

---

## 5. Scope

### 5.1 Demonstration site 🔒

- One **small storeroom/workshop/office** that the team controls and can safely record.
- Two fixed cameras covering partly overlapping or connected areas (one camera is acceptable for the first verified baseline).
- A floor layout with measured landmarks, shelves, desk, doorway, and camera positions.
- A prebuilt 3D environment in Blender/GLB or programmatically in Three.js; disclose when geometry is representative.
- Distinctive, consented demonstration objects: e.g. laptop case, red tool pouch, blue equipment case, labelled parcel.
- Up to three **consenting actors** wearing ordinary clothing; represent them through ephemeral track IDs rather than names/biometrics.

### 5.2 Canonical use case: the missing equipment case

1. The equipment case is visible on Shelf A.
2. Someone moves it to a desk, possibly blocking the camera temporarily.
3. A later view shows the case near a doorway.
4. Another camera may capture it, or the recording may leave a gap.
5. The investigator asks where it was last seen and whether evidence establishes that it left the room.
6. The system returns observable transitions, possible connections marked as hypotheses, clip citations and a spatial replay.
7. A later clip or optional door event can narrow uncertainty, and the agent revises the investigation **without deleting earlier evidence**.

**Crucial:** A scripted scenario provides **test ground truth**, not pre-scripted system outputs. The inference pipeline must be blind to scene labels and expected answer.

### 5.3 Required features

| ID | Feature | What must happen |
|---|---|---|
| F01 | Video ingest and provenance | Upload/validate recordings, compute hashes, preserve originals, detect bad timestamps |
| F02 | Site/camera configuration | Place cameras, define coverage/landmarks and calibrate a 2D floor plane |
| F03 | Perception | Request object segmentation/tracking from SAM 3.1; normalize boxes/masks with timestamps |
| F04 | Evidence memory | Store observed objects, positions, interactions, source clip offsets and confidence |
| F05 | Multi-agent inquiry | Lead, Evidence, Hypothesis and Verification roles cooperate through typed tools |
| F06 | 3D investigation | Show observed object/person traces and linked CCTV frames, with unknown segments visually distinct |
| F07 | Contradiction and uncertainty | Detect competing or impossible explanations; ask for more evidence or abstain |
| F08 | Audit/report | Export findings with source hashes, linked timestamps, edits, model versions and limitations |
| F09 | Evaluation | Run real tracking, event, spatial and evidence-grounding benchmarks against baselines |
| F10 | Privacy and access | Authorized footage only, access controls, deletion, optional redaction and bounded retention |

### 5.4 Optional enhancements, contingent on evidence

- Door-contact/load-cell/RFID **sensor ingestion** as a supplementary observation source.
- Multi-camera matching based on geometry, timestamps and visible object features **with abstention**, not biometric identity.
- Local **Muse Glimmer** for private simple summaries or metadata processing; compare outputs/cost/privacy with hosted inference.
- Muse Wonder as complex investigation escalation if a measured benefit justifies its additional cost.
- Voice Transcribe when recordings legitimately contain task-related speech and audio consent exists.
- Detection of potential camera outages, timestamp drift or blind spots for coverage quality.
- Privacy-preserving redacted replay; redaction must never alter originals or be mistaken for genuine source footage.

### 5.5 Explicitly out of scope

- Real-time surveillance across dozens of uncalibrated IP cameras.
- Identity recognition across strangers, suspect ranking, arrest/automatic enforcement, automated accusations.
- Predicting fingerprints, exact hidden object positions, or unseen movement from incomplete footage.
- Courtroom-ready forensic certification or guarantees of evidentiary admissibility.
- Automatic sensor installation, access-control changes, police contact, or retention of third-party imagery without permission.
- Training large bespoke video foundation models.

---

## 6. Product principles

1. **Evidence before narrative.** If there's no supporting frame/log, don't say it happened.
2. **Observed vs inferred vs unknown.** Every state and displayed path declares which category it belongs to.
3. **The source is one click away.** Every important claim links to footage/metadata that supports it.
4. **No invented spatial precision.** Use measured calibration, error bars/areas and provenance.
5. **Investigate actively.** Ask the next discriminating question rather than produce a single overconfident summary.
6. **Person-tracks are anonymous and temporary.** Track objects and events, not people's identities or intentions.
7. **Humans retain authority.** AI suggests and reviews; humans approve reports and consequential actions.
8. **Work with existing footage.** New camera hardware is optional.
9. **Reproducible and auditable.** Deterministic scene data, source hashes, model versions, case revision IDs.
10. **A striking 3D UX must never outrun the evidence.** Beauty serves understanding.

---

## 7. Privacy, safety, and trust 🔒

### 7.1 Data rights

- 🔒 Only accept footage for which the uploader confirms authorization and applicable notices/consent are in place. Record source rights, purpose, upload time and retention period.
- 🔒 Demonstration footage uses consenting actors at a controlled location, not scraped public CCTV or sensitive real investigations.
- 🔒 Use a clearly stated retention policy for raw video, derived embeddings, masks, logs, summaries and exports. Support deletion of all case-associated data, with documented audit-log exceptions where lawful.
- 🔒 Sensitive videos must use a provider processing mode consistent with data rights. Meta's **Standard** Muse Spark models are preferred over Contributor mode for sensitive input; verify current terms rather than treating "not used for training" as a full privacy guarantee.

### 7.2 Identity and accusation safeguards

- 🔒 Ephemeral per-clip IDs `track_camA_...` may describe trajectories but must not be interpreted as named identity.
- 🔒 No face search, hidden-face reconstruction, fingerprints from CCTV, or identifying a person across unrelated feeds using biometrics.
- 🔒 Clothing attributes may be documented only as visibly observable and uncertain descriptions; never claimed as proof of identity.
- 🔒 No score of who is "most suspicious"; hypotheses concern **object movement and observable events**.
- 🔒 No automated referral to law enforcement or adverse decisions affecting individuals.

### 7.3 Evidence integrity

- 🔒 Save original bytes unchanged and compute a SHA-256 content hash at ingest. Derivatives carry parent reference, processing method, time, software/model version and hash.
- 🔒 Distinguish **original**, **annotated derivative**, **estimated geometry**, and **generated illustrative asset** on every UI surface and export.
- 🔒 Each agent output must cite source observation IDs; a verification layer blocks unsourced factual assertions.
- 🔒 No AI image generation in evidentiary reconstruction. Muse Image must not "restore" detail, faces or fingerprints that the camera never recorded.

### 7.4 Security

- Authenticated users, per-site RBAC, short-lived media URLs, private object storage, encryption in transit/at rest, upload validation, rate limits, audit logs.
- Never let untrusted video captions, filenames, subtitles or imported logs issue agent commands; treat them as *data* (prompt-injection defense).
- Do not expose exact private location/camera feed endpoints or credentials to public demo viewers.
- Mask/blur faces and unrelated people in demonstration derivatives if not expressly consented; keep originals restricted.

---

## 8. Data reality: staged but never scripted 🔒

### 8.1 Hard data boundaries

```
[Staged Ground-Truth Controller] ---- labels ----> [Evaluation Store ONLY]
         |
         +-- recorded footage --> [Ingest] --> [Perception / Agents] --> [Evidence Graph] --> [3D / Report]

[Ground-truth labels] -X-> [Perception, Agent prompts, User-facing results]
```

- 🔒 Record genuine clips; stage events only to create known outcomes. **Never inject the correct answer into the analysis prompts.**
- 🔒 Make a seeded evaluation collection with cases: clear removal, temporary occlusion, returned item, visually similar items, camera gap, clock drift, misleading clothing, non-event.
- 🔒 Store every annotation with reviewer, time interval, frame ID, coordinates and annotation confidence.
- 🔒 If you synthesize sensor events, label them as **simulated sensor logs** at source and in the demo. If real IoT devices are connected, label those measurements separately.
- 🔒 Do not show pre-rendered AI traces as if they were dynamically computed; the output must be driven from processed observations.

### 8.2 Sources of evidence

| Source | What it proves | What it cannot establish alone |
|---|---|---|
| CCTV clip | Visible scene states and interactions at recorded times | Hidden motion, identity, intent, original timestamp accuracy |
| SAM track | Pixel-region associations within submitted frames | Same person's identity across separate cameras, physical world location |
| Floor-plan calibration | Approximate projection of image positions to a plane | Exact depth/elevation or unobserved routes |
| Door-contact sensor | Door open/closed state at time | Who used door, what was carried |
| RFID reader | Tagged item read by a reader, subject to device reliability | All intermediate physical movements |
| Load-cell sensor | Weight changed on instrumented surface | Which object/person caused the change without corroboration |
| Human annotation | A reviewer's interpretation | Independent physical ground truth without supporting data |

### 8.3 Camera clock and provenance

- Preserve original PTS/DTS when available, ingestion timestamp, claimed camera time, and clock-offset estimate.
- Estimate clock offsets from observable shared events or operator calibration; never silently assume synchronous feeds.
- Each synchronized timestamp includes an uncertainty interval. If camera clocks cannot be reconciled, show independent timelines and warn.

---

## 9. Overall system architecture

### 9.1 Information flow 🧭

```
          AUTHORIZED CCTV UPLOADS                OPTIONAL IOT LOGS
                     |                                |
         [Media ingest + SHA256]         [Timestamp normalization]
                     |                                |
         [Clip inventory + camera calibration + coverage]
                     |
   +-----------------+-------------------------------+
   |                 |                               |
[SAM 3.1 masks] [Muse Spark clip interpretation] [CV/geometry tools]
   |                 |                               |
   +-----------------+-------------------------------+
                     |
       [Versioned SPATIOTEMPORAL EVIDENCE GRAPH]
            (observations, tracks, states, edges,
           source references, unknowns, hypotheses)
                     |
                [LEAD AGENT]
               /     |      \
       [Evidence] [Hypothesis] [Verifier]
               \     |      /
              [Typed tools + structured outputs]
                     |
       [Verified case state + uncertainty + audit]
                     |
      +--------------+-------------------------+
      |              |                         |
  [3D replay]   [Evidence viewer]        [Report export]
```

### 9.2 Modules

| Module | Responsibility |
|---|---|
| M0 | Canonical schemas, IDs, validation and provenance contracts |
| M1 | Media ingest, hash, normalization and secure storage |
| M2 | Camera setup, measured floor plan, 3D scene and spatial calibration; optional validated multi-view triangulation |
| M3 | Meta perception adapter: SAM 3.1 segmentation/tracks |
| M4 | Meta reasoning adapter: Muse Spark and optional Wonder |
| M5 | Temporal graph / event-sourced spatial memory |
| M6 | Multi-agent investigation orchestrator |
| M7 | Independent evidence verification and uncertainty engine |
| M8 | Interactive 3D frontend, synchronized viewer and timeline |
| M9 | Optional IoT sensor fusion |
| M10 | Evaluation harness and test corpus |
| M11 | Auth, audit, report/export and administrative operations |
| M12 | Hackathon showcase / operator controls, isolated from investigator view |

---

## 10. Meta technology selection — verified against 27 October 2026 documentation

### 10.1 Core choice matrix

| Model/tool | Verified capability | Spoor responsibility | Decision |
|---|---|---|---|
| **Muse Spark 1.3** (`muse-spark-1.3`) | Multimodal image/video/PDF input, tool calling, structured reasoning | Evidence search planning, clip interpretation, temporal questions, lead/evidence/hypothesis/verification agents | **CORE** |
| **SAM 3.1** (`sam-3.1`) | Text/box/point guided image/video object masks and per-video tracking | Per-clip object observations and candidate tracks, optional redact | **CORE** |
| **Muse Wonder** (`muse-wonder-1.0`) | Extended reasoning and long-running agentic work | Hard case escalation or independent reviewer when benefit measured | OPTIONAL |
| **Muse Glimmer** (open weights) | 30B local multimodal agent model; Apache 2.0 stated by Meta | Private/local query and metadata reasoning; may support open-weight bonus | EXPERIMENT |
| **Muse Spark Open** (open weights) | Large multimodal model served independently or by partners | Alternative reasoning model and open-weight bonus experiment | EXPERIMENT |
| **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`) | Speech-to-text, turn-level timing | Only relevant when consented footage actually contains useful speech | OPTIONAL |
| **Muse Image** | Image generation/editing | Marketing/illustrative UI only; **never evidence**, reconstruction or enhancement | OUT OF CORE |
| **Muse Code** | Coding agent | Development aid; does not prove runtime model usage | DEV TOOL |

**Why not all models:** The competition requires meaningful Meta model usage, not a model-count checklist. Added models require explicit measured benefit, a truthful privacy story and extra integration effort.

### 10.2 Muse Spark responsibilities

- Treat it as **reasoning and interpretation**, not a raw pixel-accurate tracker.
- Query bounded clips (e.g., timestamps around an event) with a structured question and source clip ID.
- Require typed `observed_facts`, `candidate_hypotheses`, `unknowns`, `requested_evidence`, `source_frame_refs`, and `abstain_reason` outputs.
- A model-produced timestamp is a *candidate* until verified against source frames.
- Use actual model version ID and evidence in every recorded conclusion; don't rely on loose prose for machine-control decisions.
- Favor Standard mode for authorized surveillance data. Do not use cheaper Contributor mode if licensing/consent is not appropriate.
- Meta's docs note that Muse Spark 1.3 audio understanding may be degraded; if audio is needed, use dedicated transcription after separate consent review.

### 10.3 SAM 3.1 responsibilities

- Use `sam-3.1` over Meta Model API Responses. It accepts short noun phrases or boxes/points and yields segmentation geometry.
- Prompt with **concrete visually grounded object concepts** (`"blue equipment case"`, `"laptop"`), not abstract events (`"the thief"`).
- Prefer user-verified target initiation for ambiguous items and specific box/point prompts where possible.
- Decode masks/boxes with the documented SAM parser/client; retain the frame index and object track ID.
- SAM object continuity is **per submitted video**. Cross-camera data association must be a separate module with conservative uncertainty handling.
- Mask output is not an object's location on a building floor plan; camera calibration is separate.
- Run small empirical tests on occlusion, reflections, small objects, false positives, and similarly colored items.

### 10.4 Hosting strategy — confirmed-access providers only 🔒/🧭

- **Confirmed by participant (27 Oct 2026):** Meta Model API hackathon credits and **Baseten $100 Muse Spark Open credits**, with an advertised up-to-2M-TPM limit. Verify actual credits, account activation, expiry, rate limits and token pricing in each provider's billing dashboard; access is not the same as unlimited free usage.
- **Meta Model API (core):** Muse Spark 1.3 for *video evidence analysis* and SAM 3.1 for *mask/track extraction*; allow Muse Wonder only if a measured complex reasoning test warrants it. Use server-side keys and per-request cost ledgers.
- **Baseten (available):** Muse Spark Open as a tested alternative for bounded multi-agent planning, hypotheses, structured evidence-graph reasoning and independent verification. Confirm the hackathon identifier `meta-models/muse-spark-open-1026` against Baseten's live model catalog/approval email. Benchmark latency, schema validity, evidence citation and cost before using it in production-like demo flows. Do not claim it is equivalent to SAM or a geometry solver.
- **Computer vision/geometry (local by default):** FFmpeg, OpenCV, SciPy and an evaluated object-appearance encoder run on the developer's existing machine or available compute. Keep GPU-heavy optional experiments disabled by default; **no unapproved partner GPU credit is assumed**. If an appearance model cannot run affordably, use explicit geometry/time constraints plus human-confirmed association and label uncertainty.
- **No Modal or Fireworks dependency in this build.** Both requests are pending/not awarded and must not appear as a runtime dependency, funded budget, deployment assumption, or required milestone. Reconsider only after confirmed approval and an explicit PRD decision entry.
- Do not quietly substitute non-Meta models for the core reasoning/perception path. Conventional CV/geometry and non-identifying item appearance embeddings are supporting tools; document licensing and their measured roles.

### 10.5 Provider smoke tests / gating

Before locking architecture, demonstrate with an original test clip:

1. Meta API key can invoke Muse Spark 1.3 standard-mode and return schema-validated tool-call output.
2. Meta API can upload/view a short video; verify format, size, rights and recorded audio handling.
3. SAM 3.1 can segment/track the target across the clip and expose frame-aligned geometry.
4. Processing cost and latency are measured and recorded, not assumed from model headline pricing alone.
5. Independent fixed image-frame inference produces stable coordinate metadata.
6. Failure fallback: if SAM cannot segment reliably, operator supplies box/point start and the tracking service retries; if results remain weak, abstain.

Official docs: https://dev.meta.ai/docs/models · https://dev.meta.ai/docs/video-understanding · https://dev.meta.ai/docs/media-segmentation · https://dev.meta.ai/docs/sam/segmenting · https://dev.meta.ai/products/meta-model-api

---

## 11. M0 — Canonical evidence data contract 🔒

Every frontend visualization, agent statement and report must refer to **identical stable IDs**. Define schemas once (JSON Schema/Pydantic with generated TypeScript) and reject invalid or mismatched IDs.

### 11.1 Canonical entities

- `site_id`: isolated physical site.
- `camera_id`: camera identity and view metadata.
- `media_id`: immutable source asset and hash.
- `frame_ref`: `{media_id, pts_ms, frame_index, source_time_utc, time_uncertainty_ms}`.
- `track_id`: ephemeral per-camera/per-clip track identity, never a person's real identity.
- `observation_id`: video- or sensor-derived observation with sources.
- `object_instance_id`: provisional physical object identifier; merges across tracks require explicit support.
- `zone_id`: floor-plan region/door/shelf and geometry.
- `event_id`: temporal interaction/status change with observation sources.
- `hypothesis_id`: explanation under investigation, with evidence for/against and status.
- `finding_id`: verified summary assertion with source observations and limitations.
- `case_revision_id`: immutable state revision.

### 11.2 Example schemas (indicative; hard rules remain invariant)

```jsonc
// RawObservation: from video/SAM/IoT, NOT from user-facing narrative
{
  "observation_id": "obs_104",
  "source_type": "video",
  "media_id": "camA_clip03",
  "source_frame": {"pts_ms": 9340, "frame_index": 280},
  "camera_id": "camA",
  "track_id": "camA_track_7",
  "label": "blue equipment case",
  "bbox_xyxy_normalized": [0.33, 0.44, 0.47, 0.67],
  "mask_asset_id": "mask_104",
  "observed": true,
  "model": "sam-3.1",
  "model_version": "documented-api-identifier",
  "quality_flags": ["partially_occluded"],
  "confidence_raw": 0.81,
  "confidence_calibrated": null
}

// SpatialEstimate: separately derived, with uncertainty
{
  "estimate_id": "loc_104",
  "observation_ids": ["obs_104"],
  "floor_plane_xy_m": [3.14, 1.82],
  "uncertainty_radius_m": 0.55,
  "method": "homography_floor_contact",
  "calibration_id": "calib_camA_v2",
  "status": "estimated_not_measured"
}

// MultiView3DEstimate: OPTIONAL, for independently corroborated points
{
  "estimate_id": "xyz_021",
  "target_kind": "non_identifying_object_landmark",
  "site_xyz_m": [2.14, 3.61, 1.06],
  "site_frame": "site_meters_z_up_v1",
  "method": "calibrated_multiview_triangulation",
  "source_observation_ids": ["camA_obs_021", "camB_obs_034"],
  "correspondence_id": "corr_021",
  "calibration_ids": ["calib_camA_v3", "calib_camB_v2"],
  "synchronization_id": "sync_session_04",
  "reprojection_error_px_by_camera": {"camA": null, "camB": null},
  "uncertainty_3d_m": null,
  "validation_status": "pending_quality_gates",
  "evidence_refs": ["camA_frame_441", "camB_frame_438"]
}

// Hypothesis: must remain contestable and grounded
{
  "hypothesis_id": "hyp_12",
  "claim": "Case may have moved beyond Door B",
  "support_observation_ids": ["obs_104", "obs_135"],
  "against_observation_ids": [],
  "missing_evidence": ["camB_14_30_to_14_35"],
  "status": "unverified",
  "next_action": "retrieve_adjacent_clip",
  "agent_proposal_id": "proposal_12"
}

// VerifiedFinding: not automatically a legal finding
{
  "finding_id": "finding_21",
  "statement": "Case last visible near Door B at the recorded timestamp",
  "observation_ids": ["obs_135"],
  "spatial_estimate_ids": ["loc_135"],
  "verification_status": "supported_by_video",
  "limitations": ["camera_clipped_exit", "clock_offset_uncertain"]
}
```

### 11.3 Non-negotiable validation

- 🔒 Reject source-free factual findings and nonexistent object/clip/zone IDs.
- 🔒 Don't let an LLM directly set verified status, override observed coordinates, or edit immutable original records.
- 🔒 All transitions `proposed -> evaluated -> supported/contradicted/insufficient_evidence` recorded with actor and evidence.
- 🔒 Never equate `confidence_raw` from two different models; calibrate on holdout data, or display as qualitative uncertainty.
- 🔒 Time is explicit: source PTS, camera clock, normalized wall time and synchronization offset.

---

## 12. M1 — Media ingestion and provenance

- Support drag/drop MP4 and other verified FFmpeg-supported media; convert working derivatives without modifying originals.
- Validate media types, codec, duration, framerate, orientation and time base. Reject corrupted, oversized, or unauthorized inputs.
- Compute SHA-256 for originals and derivatives, persist hashes with ingestion action and timestamps.
- Extract representative frames, low-resolution proxies, video segments, optional audio track availability; **audio analysis off by default**.
- Detect aspect ratio/orientation changes; map segmentation geometry to original pixel coordinates carefully.
- Store originals privately; use signed access for investigator tools and short-lived secure playback links.
- Respect model file upload expiry and internal asset IDs. Cache repeated inference results keyed by source hash, model ID, prompt/version, settings and calibration where relevant.
- Queue expensive requests with concurrency/quota control; persist provider operation/response ID and classify timeout as unknown completion, not immediate safe retry.

---

## 13. M2 — Spatial model and camera calibration

### 13.1 Site contract

- One metric coordinate system with named zones (shelf, desk, door, hallway, walkway).
- Record floor-plan dimensions/scale and how measurements were obtained.
- For each fixed camera: position, orientation/FOV estimate, frame resolution, validity period and field-of-view polygon; distinguish measured values from approximations.
- Expose calibration quality and warning state in operator setup.

### 13.2 Mapping approach — calibrated 2.5D first, true 3D only when observable 🧭

**Engineering decision:** Do not attempt to infer a complete 3D trajectory from monocular CCTV. Use a measured, editable site/floor-plan model and project **visible floor-contact observations** onto a shared metric 2D ground plane, then render those `(x,y)` positions inside a 3D scene. This is a **2.5D evidence visualization**, not volumetric motion capture.

**Fixed camera onboarding:**

1. Establish a site coordinate system in metres and a room/floorplan mesh with stable zone IDs. Record camera geometry and uncertainty. If the space has multiple floors, set `floor_id` explicitly; never project a point onto an arbitrary floor.
2. Synchronize camera clocks to one timeline using camera metadata/NTP if reliable; otherwise establish and record a manually validated offset with tolerance. Preserve original timestamps, media PTS and correction method.
3. Collect at least four well-spread, non-collinear correspondences between **known ground-plane points** in a camera image and measured floor coordinates (`(u,v) ↔ (x,y)`). Use independent calibration/validation points. Avoid mixing walls, shelf tops, and floor landmarks in the same planar fit.
4. Estimate `H_image_to_floor = cv2.findHomography(image_points, floor_points, cv2.RANSAC)` (or another documented robust estimator). Where lens distortion is noticeable, calibrate/undistort first. Transform a visible person's **feet/contact anchor** using `cv2.perspectiveTransform` after checking point validity. For stationary CCTV, mark calibration invalid if the camera moves or zooms.
5. For each valid observation, return `floor_id, x_m, y_m, ts, covariance_or_error_estimate, camera_id, calibration_version, evidence_ref`. Reject outside-floor or physically impossible projections. Compute holdout-point reprojection error in metres, report median/95th percentile and unknown rate; do not state accuracy until measured.
6. For a parcel on a shelf or an object in a person's hand, homography is **not valid** for that object's physical height. Model the known shelf/desk anchor or attach a **hypothesized carried-object relation** to the anonymous person's floor path; state that item world position is not independently measured.
7. In overlapping, synchronized calibrated camera views, stereo geometry/triangulation may be evaluated for **simultaneously observed** features only. Never offer this as a substitute for multi-camera association when cameras have no common field of view.

**Fallback hierarchy:** accurate floor position + error envelope → room/zone-level placement → image-only detection with evidence; no fake `(x,y,z)` output. A drawn path may connect observations as a *hypothesized transition* only (dashed, not observed).

**Official foundations:** OpenCV Camera Calibration and 3D Reconstruction (`https://docs.opencv.org/4.13.0/d9/d0c/group__calib3d.html`) and Homography tutorial (`https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html`). Homography is planar; perspective mapping does not magically recover object depth.

### 13.3 3D is not a generative hallucination 🔒

- Build one **known room layout** in Blender and export GLB or procedural Three.js geometry.
- Display observed floor positions and known shelf/door anchors; models cannot fill unseen room details as proven geometry.
- `world_state_at(t)` is computed from event records, with uncertainty and unknowns preserved.
- If 3D rendering fails, a synchronized **2D floor-plan fallback** shows the same evidence and labels.
- A visually convincing trajectory is **not** evidence of actual XYZ motion unless independently supported by camera observations and a validated camera rig.

### 13.4 Optional M2-3D — true metric `(x,y,z)` from synchronized multi-view observations 🧭

**Purpose:** Where two or more fixed cameras overlap in the same physical region, estimate 3D coordinates of a **specific visible and corresponding physical point**, rather than placing all detected objects on the ground plane. This is a separate **feature-gated extension**, not a prerequisite for the standard CCTV investigation system.

**Definition of success:** Output a time-indexed 3D **point or sparse landmark track** in the measured site coordinate system, with source-frame references, camera parameters, residual errors, and a quality classification. A complete 3D body mesh, unseen motion path, hidden face, or detailed 3D object shape is **not promised**.

#### 13.4.1 Preconditions — all required 🔒

1. **Overlapping line of sight:** At least two calibrated cameras simultaneously see the **same physical 3D landmark**; two non-overlapping cameras cannot triangulate an unseen point, even if object identity is suspected to match across recordings.
2. **Temporal alignment:** Frames are synchronized to a shared timeline, with estimated timestamp-offset uncertainty. Calibrate offsets using a visible shared event or independently validated camera times. Refuse dynamic-object triangulation when offset uncertainty is too large relative to object motion.
3. **Full camera geometry:** Each camera has a validated intrinsic matrix `K`, distortion coefficients, and extrinsic pose `(R,t)` relative to the same metric world frame. Floor-only homographies **do not supply sufficient full 3D camera geometry** on their own.
4. **Metric scale and axes:** The camera rig has a measured length/marker baseline or surveyed landmarks to fix scale. Use site coordinates `(X east/right, Y forward/north, Z up)` **in metres**, consistently throughout geometry outputs; transform explicitly into the renderer's Y-up convention (e.g., glTF), never by implicit axis guesses.
5. **Same point correspondence:** Both camera observations refer to the same visible point (e.g., a distinct corner/marker of a rigid case), *not* merely the center of two object bounding boxes. SAM masks/track labels select an object region but **do not establish cross-view pixel/landmark correspondences**. Use manually verified landmark selection initially; any automatic feature/keypoint association must be measured separately.
6. **Stable physical cameras:** Invalidate calibration after an unmeasured camera movement, digital crop/zoom, resolution mapping change or focus/lens setting that changes intrinsics; repeat calibration and error validation.
7. **Rights and safety:** All footage is authorized/consented. Use non-biometric object landmarks or anonymous, voluntary pose landmarks only; no cross-camera facial or biometric identity resolution.

#### 13.4.2 Camera-rig onboarding and quality checks 🧭

1. **Choose a measured scene:** Two fixed phones/webcams or existing authorized CCTV feeds filming a common desk, corridor or shelf at different angles. The room is measured in metres. For the proof, stage a visually distinctive box moving between marked positions; do not rely on identical objects.
2. **Calibrate intrinsics per camera:** Collect multiple checkerboard/ChArUco calibration images covering different regions/angles. Compute `K` and lens-distortion parameters using the selected, version-validated OpenCV 4.x calibration API or a tested BSD-licensed multicamera calibration tool (e.g., Caliscope). Document detection quality and reprojection residuals.
3. **Calibrate extrinsics jointly:** Use shared target observations or surveyed 3D landmarks to solve every camera's pose relative to a common coordinate system, using validated `solvePnP`/stereo methods or a dedicated multicamera bundle-adjustment workflow. Verify the *physical scale* with independently measured distances. Record rig version and validity interval.
4. **Calibrate time:** Store clip original PTS, stream time base, camera wall-clock offset, uncertainty and a shared event anchor. Account for dropped frames and variable FPS; don't assume the same frame index means the same instant.
5. **Validate on held-out landmarks:** Use surveyed points *not used during calibration*. Report per-camera reprojection error, 3D position error against measured test positions, fraction of failed triangulations and sensitivity to camera alignment. Retain raw and calibrated values, never force an inaccurate rig into success status.
6. **Use clear rig states:** `uncalibrated`, `calibrating`, `validated_floor_only`, `validated_multiview_3d`, `invalidated`. Runtime tools must check the required state for each requested method.

> Geometry reminder: for a world point `X = (X,Y,Z,1)^T`, each camera projects through `P_i = K_i [R_i | t_i]`, with distortion applied according to the chosen coordinate representation. Coordinate frames and distortion handling must be consistent; do not pass pixels into a normalized-coordinate solver (or vice versa).

#### 13.4.3 Landmark correspondence and triangulation runtime 🧭

For an eligible overlapping interval:

1. **Track local candidates:** Use SAM 3.1 to identify relevant visible objects within each individual camera clip. Preserve masks, crop quality and provenance.
2. **Establish cross-view landmark correspondence:** Link candidate physical object observations using geometry/time/camera topology, then identify matching **distinct feature points** within those observations. Initially require a user-confirmed landmark pair or an unambiguous marker. Appearance similarity alone is insufficient, especially for people or lookalike objects.
3. **Align samples:** Choose near-simultaneous timestamps with measured offsets. If temporal mismatch produces material motion ambiguity, mark `not_triangulatable` rather than interpolating hidden motion as truth.
4. **Undistort consistently:** Apply `cv2.undistortPoints` (or equivalent) and build matching normalized projection matrices, **or** use documented camera pixel projections with already corrected observations. Lock one convention in a tested helper; never mix both inadvertently.
5. **Triangulate:** Use `cv2.triangulatePoints(P_a, P_b, pts_a, pts_b)` with consistent projections, divide homogeneous coordinates by `w`, and transform into the shared metric world frame. For 3+ views, optionally optimize by minimizing total reprojection error or use a robust multi-view solver. This step is **deterministic geometry**, not an LLM prompt.
6. **Validate every point:** Reject missing/ambiguous correspondences, non-finite homogeneous results, points behind either camera (cheirality), near-parallel viewing rays/ill-conditioned geometry, excessive reprojection residuals, implausible workspace coordinates, and frame-to-frame jumps incompatible with the measured object motion. Thresholds must be tuned on a held-out calibration/evaluation set, never chosen merely to make a demo pass.
7. **Estimate uncertainty:** Perturb image landmarks according to observed detector/annotation error, camera parameters and time offsets (e.g., Monte Carlo or numerical propagation). Store a 3D covariance/error ellipsoid or clearly labeled empirical error bound; don't report an arbitrary model confidence as centimetre precision.
8. **Persist result:** Record `source_observation_ids`, exact timestamps, `calibration_ids`, `synchronization_id`, `correspondence_id`, metric `xyz`, residuals, uncertainty, quality-gate decisions, and software version. An accepted 3D estimate is still an **estimate**, not a measured physical trace.
9. **Maintain trace semantics:** Join consecutive **accepted, directly observed** 3D points only where tracking continuity and timing support it. A smooth interpolation is a renderer convenience and must be marked as interpolated. Keep gaps/occlusions as gaps; do not render guessed trajectories as observed.

**Object-specific interpretation:** A person's foot contact is more reliably mapped by floor homography (§13.2) than by naive body-box center triangulation. Hands, packages and shelf items can be triangulated only when the *same specific point* can be located in multiple views. If an object is fully hidden in a hand or bag, the system cannot know its actual XYZ position; an attachment to a person track remains a **hypothesis**, not an independent observation.

#### 13.4.4 Fallback, agent interface and reviewer controls 🔒

- **Never block normal operation on true 3D.** Per point/time: `validated multi-view XYZ` → `validated single-view floor XY (+ known height only if externally measured)` → `room/zone-level position` → `2D source evidence only` → `unknown`.
- Geometry service exports `get_spatial_estimates(track_or_object_id, time_window, min_quality)` plus `explain_spatial_basis(estimate_id)`. Agents can request geometry and reason about limitations; they **cannot override failed quality gates**, invent missing XYZ or promote a candidate link to verified.
- Frontend reveals multi-view XYZ in a distinct solid 3D point/trace style with an error ellipsoid; floor XY proxies use a different style; interpolated and unknown intervals are visually distinct. Clicking any 3D point opens **both source frames side-by-side**, the matching landmark overlays and calibration quality.
- An operator can correct correspondences or invalidate a calibration, creating a **new versioned estimate**. Prior evidence is retained; dependent tracks/case findings are recomputed or marked stale.
- Optional sensor logs (door contacts, RFID or load cells) may support a hypothesis about an object's presence or passage but **do not provide XYZ** unless their hardware and positioning accuracy explicitly justify it.

#### 13.4.5 Deliverables and measured evaluation 🎨

**Recommended isolated demonstration:** A small measured room with **two fixed cameras whose views overlap**, moving a distinct tagged box among measured positions (including one elevated shelf point). Include deliberate occlusion, timestamp offset, almost-parallel camera poses and a misleading lookalike item as negative cases. For the calibration example, a visible geometric marker is a legitimate *measurement aid* but the standard CCTV workflow must still work without such markers in 2.5D mode.

Report on ground-truth test points and held-out clips:

- Calibration: per-camera held-out reprojection error (pixels), independent 3D landmark position error (metres), metric-scale error and recalibration stability.
- Correspondence: fraction of valid physical-point matches, false match rate, abstention on similar/occluded candidates, time alignment error.
- Triangulation: median / 95th percentile XYZ error, reprojection residuals, rejection rate, impact of viewing angle and occlusion, and runtime cost.
- Ablations: (A) no calibration, zone labels only; (B) one-camera floor projection; (C) calibrated two-camera triangulation; (D) C with robust rejection and uncertainty reporting. Present measured wins **and failures**, not claimed precision.
- Pass/fail gate: advanced XYZ may appear in the main product only after quantitative validation and enough corresponding visible landmarks. If it fails, **disable it and keep the proven 2.5D experience**. A beautiful 3D digital twin does not depend on passing this experiment.

**Implementation references:** OpenCV `calibrateCamera`, `solvePnP`, `undistortPoints`, `triangulatePoints`, `projectPoints` (pin/verify OpenCV 4.x API); Caliscope (`https://mprib.github.io/caliscope/`, BSD-2-Clause, confirm version); multi-view tracking research benchmark TAPVid-MV (`https://tapvidmv.github.io/`, useful research context, not assumed turnkey software). No SAM/Muse model magically replaces calibrated projective geometry.

### 13.5 Scene coordinate contract — backend ⇄ 3D frontend 🔒

- **Backend storage:** Always use one measured site reference frame, metre units, explicit floor and `Z_up`; object/world transforms are versioned. No pixel coordinates in fields named `world_xyz_m`.
- **Renderer:** Define a unit-tested transform between `site_frame Z_up` and the frontend renderer's Y-up system. Display camera frusta from calibrated camera poses, not arbitrary decorative cones, and label approximate FOV when only manual onboarding exists.
- **Explicit placement type:** Every rendered marker carries `spatial_mode = multiview_xyz | floor_xy | anchored_height | zone_only | image_only | unknown` and an evidence/uncertainty payload. UI distinguishes each mode.
- **No false volumetric claims:** Floor-anchored person avatars and animated object icons are symbolic glyphs; neither implies recovered skeletons or volumetric scene capture. A named 3D mode only means point-level metric triangulation for particular observations.
- **Temporal consistency:** `world_state_at(t)` must use a consistent adjusted timestamp across cameras and immutable event versions; apparent paths across invisible intervals remain gaps.

---

## 14. M3 — Perception, object tracking and association

### 14.1 Segmentation pipeline

1. Identify candidate target object names from case details or verified user clicks.
2. Segment target on a high-quality keyframe via SAM 3.1.
3. Use SAM video tracking or a validated auxiliary tracker to follow the same *visual instance* within a clip.
4. Store timestamped boxes, masks, occlusion flags and track quality.
5. Summarize visible state transitions; flag ambiguous identity or disappearance.
6. Let an investigator correct initial target selection without rewriting prior raw observations.

### 14.2 Multi-object / multiple-person caveats

- Same visual category != same physical object. Two identical laptop cases require uncertainty or unique labels to be reliably associated.
- Anonymous person tracks are valid for movement context, not identity resolution or suspicion scoring.
- A hand near an object is not proof of transfer; use temporal evidence with before/after visibility and event confidence.
- "Object disappeared" may mean carried away, moved under a desk, occluded, or a camera glitch. Maintain alternatives.

### 14.3 Cross-camera association — a constrained global tracklet graph 🧭

**Engineering decision:** Meta SAM 3.1 delivers segmentation and **within-video** object tracking, not trustworthy global identity across independent CCTV feeds. The system must implement explicit **multi-target, multi-camera association (MTMCT)** over *tracklets*, with multiple signals and a right to abstain.

**Step A — Within-camera tracks:**

1. Muse Spark chooses/validates the target type and relevant clip windows. Call `sam-3.1` using noun phrase or **point/box prompt for a particular instance**. Persist instance boxes, masks, timestamps and source frame IDs.
2. Prefer native SAM video tracking for targeted clips. For longer sequences/multiple detections, benchmark a lightweight auxiliary single-camera tracker such as **Norfair** (BSD-3-Clause); compare it with Meta SAM on target recall and ID switches rather than assuming superiority. **BoT-SORT** is a useful ReID research baseline, but confirm its dependencies and licenses before adoption. Ultralytics implementations can carry AGPL obligations and must not be silently copied into a differently licensed project.
3. A tracklet is a bounded span where one within-camera ID is supported: `camera, start/end, track_id_local, object_class, sampled_crops, confidence, exit_zone/entry_zone, appearance_embedding_ref, provenance`.

**Step B — Cross-camera candidate generation:**

4. Normalize times (include offset uncertainty), record camera adjacency and plausible exits/entrances. Construct candidate tracklet links only when travel time, camera topology and floor-plan transitions are physically possible. Use **negative constraints**: simultaneous non-overlapping locations, incompatible dimensions, or contradictory observations forbid a match.
5. Compute appearance evidence on *several quality-filtered crops* for the tracked **object**, not a person's face. For visually distinct belongings, compare embeddings from an approved feature extractor (e.g., evaluated DINOv2 or another permitted feature model) plus color/shape where useful. For people, use only temporary anonymous movement context and consider clothing similarity **non-identifying**; disable global person-linking where legal/privacy review is absent. No biometric identification or face recognition.
6. Form a calibrated association score/cost from `appearance_similarity`, `temporal_feasibility`, `camera_topology`, `object_geometry`, `sensor_support` and `quality/occlusion`. Start with simple weighted evidence and hard rejection gates. Avoid a complex learned model until baseline results show a benefit. Don't treat a high cosine similarity alone as a verified cross-camera match.
7. Solve one-to-one candidate assignment for a small batch using Hungarian matching (`scipy.optimize.linear_sum_assignment`) *after* hard gating. For large scenarios, investigate min-cost flow or a temporal graph optimizer, but only if justified by evaluation. Permit track splitting/merging as **uncertain hypotheses**, and never force all detections to match.
8. Label output `verified_same_camera`, `candidate_cross_camera`, `rejected`, or `unresolved`; only human-confirmed or independently corroborated cross-camera links may be represented as strongly supported. An associated global object ID is a case-internal hypothesis, not biometric identity.

**Step C — Evidence-backed 3D:**

9. Project the valid camera observations onto the shared floor plan using §13.2; preserve camera-local 2D coordinates as the authoritative visual evidence. The graph stores observation nodes and separate candidate-link edges. Draw **solid** segments only where motion was actually tracked within a camera's visible coverage. **Dashed** segments can indicate a physically possible cross-camera transition; **gaps remain gaps** and no route is claimed to have been observed.
10. Every segment, transition and agent claim must be clickable back to frames and source hashes. If a visually identical object could have been swapped, return multiple candidate histories rather than claiming a single item identity.

**Cross-camera risk controls:** deliberate lookalike cases; duplicate objects; time drift; inconsistent lighting; object in hand; blind-spot exits; two people with similar clothing; camera movement; major occlusion. Matching shall become *less* certain, not more confident, when these conditions occur.

**Measured success criteria, not preset achievement:** report within-camera ID switches, cross-camera wrong-link rate and IDF1/association F1 where labeling permits, calibration position error in metres, abstention precision on ambiguous cases, and source-verified event recall. Compare `appearance-only`, `time+topology-only`, and `combined gated graph` against each other. Choose conservative match thresholds on validation footage only.

### 14.4 Model/tool responsibility boundaries

| Component | Input → output | Runtime |
|---|---|---|
| Meta Muse Spark 1.3 | Relevant clips/questions → structured proposed event descriptions, target selection, case reasoning, tool calls | Meta Model API |
| Meta SAM 3.1 | Target and clip/points → masks, boxes, track IDs **inside that video** | Meta Model API |
| Norfair / evaluated tracker | Detections → smoothed **within-camera** tracklets | Local CPU/GPU as available; no external GPU credits assumed |
| Appearance encoder | Permitted crops of an item → feature vectors | Local CPU/GPU when feasible; optional, validate weights/license |
| OpenCV calibration | Ground landmarks → homography and validated `(x,y)` estimates | CPU, deterministic |
| **Optional multi-view XYZ geometry** | Synchronized same-landmark image observations + full calibrated rig → validated metric `(x,y,z)`, residuals and uncertainty | Local OpenCV CPU; feature gated (§13.4) |
| Graph association | Tracklets + topology + timestamps + visual evidence → candidate object links | CPU, deterministic + confidence |
| Meta reasoning/verification agents | Structured evidence graph + on-demand clip tools → testable hypotheses and supported/abstaining conclusions | Meta Model API; Baseten Muse Spark Open (confirmed access, benchmarked) |
| Three.js / React Three Fiber | Versioned calibrated world state → 3D floor-plan replay and linked evidence | Browser |

**Optional sensors:** RFID/object tags, door contact, asset weight sensor, and badge events can **corroborate** transitions when present and permissioned; none is required for ingest or replay. Never infer fingerprints or reconstruct hidden faces from ordinary CCTV.

**Supporting references:** Meta SAM (`https://dev.meta.ai/docs/sam/overview`); Meta media segmentation (`https://dev.meta.ai/docs/media-segmentation`); Norfair (`https://github.com/tryolabs/norfair`, BSD-3-Clause); Ultralytics tracking documentation (`https://docs.ultralytics.com/modes/track`, evaluate licensing); OpenCV homography (`https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html`); camera-topology-aware multi-camera association paper (`https://arxiv.org/abs/2105.01213`).

---

## 15. M4 — Video reasoning with Muse Spark

**Purpose:** analyze a specific visual question rather than describe entire surveillance footage generically.

### 15.1 Structured tasks

- Identify whether a requested object is visibly present in a specified clip window.
- Describe supported interactions, with approximate timestamps and original frame citations.
- Differentiate explicit observations from hypotheses.
- Find where a candidate explanation would be contradicted by available evidence.
- Generate targeted next-step evidence queries (camera B, interval 14:30–14:35).

### 15.2 Reliability rules 🔒

- Muse Spark outputs **proposals**; deterministic ID validators and the Verification Agent decide whether claims enter case memory as supported.
- If requested detail cannot be seen, respond `not_observable` rather than fabricate.
- Verify sampled frames for time-specific claims. Don't assume a text-only model response grounds every second of a long video perfectly.
- No inferred criminal intent, identity, ethnicity, age or other personal classifications.
- Preserve prompt template version, model version, reasoning setting, token usage and evidence IDs.

### 15.3 Inference strategy

- Start with preselected short intervals around a missing-object report or motion/change observation.
- Clip-adaptive sampling: higher frequency near candidate state transitions, lower frequency elsewhere; record what was not inspected.
- Cache keyframe/clip summaries; avoid sending the same long footage to every agent.
- Evaluate Spark 1.3 against optional Wonder only on *hard* examples where added reasoning can be measured, not merely assumed.

---

## 16. M5 — Spatiotemporal evidence graph and world memory

### 16.1 Why memory matters

An LLM context window does not provide durable physical memory. The system needs a persistent record that can answer queries such as:

- When was object A last **visibly confirmed**?
- Which observed location transitions occurred between times T1 and T2?
- Which zones were unobserved during the interval?
- Which claims rely on inferred links rather than direct frames?
- Did later evidence contradict an earlier hypothesis?

### 16.2 Storage design

🧭 Postgres for authoritative case/event records, indexed by site, camera, source time, track and object. pgvector may help retrieve *textual* event descriptions, but must not replace structured temporal/spatial queries. Neo4j is optional if graph queries justify operational overhead; a few indexed adjacency tables may be enough.

- Immutable `raw_observation` and `source_media` records.
- Versioned `spatial_estimate` and `track_association` records.
- Append-only `event` and `hypothesis_status_change` logs.
- Current-case materialized projections derived from the event stream.
- Transactional optimistic versioning for agent/human edits.
- Explicit TTL/retention/deletion handling for sensitive media and derivative embeddings.

### 16.3 State machine

`unobserved -> visible -> partially_occluded -> out_of_view -> visible_again` must not collapse into an unsupported claim that the object moved continuously along a line.

### 16.4 Memory validation

- Source deletion invalidates dependent findings/reports; no orphan evidence references.
- Any corrected track or camera calibration triggers recomputation of dependent spatial estimates and invalidates affected approval.
- Historical versions remain auditable while source retention permits; current view never silently mutates earlier issued reports.

---

## 17. M6 — Multi-agent investigative reasoning

### 17.1 Coordinator and specialist roles

| Agent | Goal | Tools | Output |
|---|---|---|---|
| **Lead / Orchestrator** | Decompose a user question, allocate bounded investigation steps | search, delegate, state, budget, merge | Investigation plan, next action, user-facing answer |
| **Evidence Agent** | Find and inspect source-supported observations | clip retrieval, Spark video, SAM masks, frame access | Evidence bundle with exact source refs |
| **Hypothesis Agent** | Construct and compare possible physical explanations | temporal graph, spatial queries, sensor event search | Competing hypotheses + distinguishing evidence needs |
| **Verification Agent** | Independently challenge source validity, geometry and claim overreach | observation resolver, replay tests, consistency checks | Supported / contradicted / insufficient-evidence verdict |

**Implementation nuance:** Perception, spatial calibration, hash generation and database access are **deterministic services/tools**, not additional autonomous agents merely to increase the count.

### 17.2 Agent protocol

Every agent request has: `case_id`, `request_id`, `role`, `question`, `evidence_scope`, `available_tools`, `token_budget`, `max_steps`, `deadline`, and allowed output schema. The orchestrator must enforce these fields, log each delegation and reject agent-generated tool arguments outside granted scope.

Each agent response has: `status`, `claims`, `evidence_ids`, `unknowns`, `conflicts`, `recommended_next_tool`, `cost`, and `model_version`.

### 17.3 Example investigation sequence

1. Investigator: "Where is the blue equipment case? Did it leave the storeroom?"
2. Lead agent reads camera coverage and item history, plans investigation.
3. Evidence agent retrieves latest relevant appearances on Camera A.
4. Hypothesis agent formulates `H1: remains in room but occluded`, `H2: moved toward door`, `H3: camera clock mismatch`.
5. Verification agent rejects unsupported `left building` claims and checks timestamp plausibility.
6. Lead agent requests Camera B interval if it could distinguish H1/H2.
7. After observing Camera B, agents update hypotheses and display 3D evidence; otherwise answer "unresolved" with explicit next evidence needed.

### 17.4 Verifier invariants 🔒

- A verifier cannot treat another agent's prose as the original source.
- Check evidence IDs resolve and timestamps/geometry match; re-inspect source frames when necessary.
- Run an independent programmatic check for impossible speed/travel or contradictory location states.
- If a claim is ungrounded, issue `unsupported` and remove it from factual summary; retain it only as clearly labeled hypothesis if useful.
- Human reviewer can contest or correct AI interpretation; correction and reason are audited.

### 17.5 Agent self-correction and stopping

- Max bounded tool calls and spend per case; avoid infinite critique loops.
- A revision must add information or resolve a contradiction; if no new evidence remains, stop and abstain.
- Persist checkpoints after each tool result; idempotent tool requests prevent duplicate paid operations.
- Log the causal chain: question -> delegated task -> observation -> hypothesis -> verification -> displayed output.

---

## 18. M7 — Uncertainty and contradiction engine

### 18.1 Evidence labels (user-visible)

| Label | Meaning | Display |
|---|---|---|
| **Observed** | Directly represented in original footage/sensor source | Solid green trajectory / citation |
| **Estimated** | Mapped position or association derived from observation, with error estimate | Blue point/region with uncertainty halo |
| **Hypothesized** | Possible explanation awaiting discriminating evidence | Dashed amber connection |
| **Unknown** | No adequate observation or mapping confidence | Grey gap / no path |
| **Contradicted** | Candidate inconsistent with evidence | Rejected hypothesis with reason |

Colors are a default; ensure non-color accessibility with patterns, labels and icons.

### 18.2 Contradiction checks

- Person/object located in two mutually impossible physical positions at same synchronized time.
- Proposed route passes outside calibrated connectivity or requires implausible speed.
- Same object candidate has incompatible visible appearance where no plausible change occurred.
- Proposed object transfer lacks visible contact and before/after support.
- Sensor claims movement/door event inconsistent with usable timestamps or known installation; sensor may itself be wrong.
- Evidence quote references a nonexistent/expired source frame.

### 18.3 Confidence calibration

- Thresholds and qualitative confidence labels must be based on validation data.
- Never turn model self-reported probabilities into measured confidence without calibration.
- For any unmeasured association, display "possible" or "unverified" rather than synthetic 94.7% certainty.

---

## 19. M8 — Interactive 3D investigation workspace

### 19.1 Product feel

Professional, restrained and evidence-first. Think investigative software with the navigability of a premium 3D viewer, **not** a sci-fi police movie UI. Dark-neutral 3D canvas is appropriate, but text contrast, density and controls must remain clear.

### 19.2 Required surfaces

1. **Case overview:** question, last confirmed observation, unknowns, next recommended evidence, report state.
2. **3D scene:** fixed building/room geometry, shelves/doors, camera frustums, observed positions and uncertainty zones.
3. **Time travel:** one canonical timeline with camera time drift warnings; jump to observed events.
4. **Movement trace:** choose `Object`, `People (anonymous)` or `All`; never turn gaps into solid curves.
5. **Synchronized source panel:** click any event to see original media/time and annotated derivative toggle.
6. **Evidence graph:** view observations -> event -> hypothesis -> finding chains and counter-evidence.
7. **Investigation agent panel:** natural-language questions, tool activity, open questions, evidence requests and verified responses.
8. **Report review/export:** human approves summary; downloads source-linked report and hash manifest.

### 19.3 The signature interaction

- An investigator clicks "Where did the blue case go?"
- 3D scene moves to the **last confirmed** position; its relevant camera cone illuminates.
- A solid green line shows directly observed track segments. An amber dashed connection suggests one plausible link, separated by a grey unknown interval.
- Clicking any line segment opens exact frame/clip and overlay; an Evidence Agent message says what was observed, while Verification Agent notes uncertainty.
- User requests another camera interval and the scene updates with a clear "new evidence added" diff.

### 19.4 3D implementation 🧭

- Blender -> optimized `.glb`; Next.js/React + Three.js or React Three Fiber + drei; maintain camera/scene IDs consistent with M0.
- The renderer consumes **typed spatial event data**, not LLM-generated arbitrary WebGL code.
- 2D projection and 3D positioning are validated upstream; UI interpolations may improve animation aesthetics **only inside verified contiguous observation windows**.
- Show position uncertainty as rings or polygons; never visually overstate certainty with cinematic camera moves.
- Respect reduced motion, keyboard control, time scrubbing, web accessibility and a 2D fallback.

### 19.5 Design quality rules

- Do not overload the page with cards, neon trails, fake metadata, and decorative animations.
- One focus hierarchy: **3D scene / timeline / source evidence**, then context.
- Display provenance inline, with a source link for every meaningful event.
- Loading and errors are explicit; no pre-scripted "AI typing" that pretends to be live inference.
- Real cases never appear in public demo; use synthetic/staged media and fictional names.

---

## 20. M9 — Optional sensor fusion

Sensor signals enhance the evidence graph but are not necessary to use the product.

### 20.1 Supported event types

- `door_contact(open|closed)` with device/site/zone and clock-quality metadata.
- `weight_delta_kg` on a named shelf.
- `rfid_tag_seen` for consented tagged equipment (not people).
- `motion_trigger` if supported by the existing camera/NVR.

### 20.2 Fusion semantics 🔒

- A door-open event does **not** identify who used it.
- A weight drop does **not** identify what caused it.
- RFID observations are limited to tagged equipment and reader coverage.
- Never merge video and sensor events without timestamp alignment/confidence; expose contradictions.
- Mocked signals must be tagged `simulated`; lab ground truth is not shared with inference code.

### 20.3 Adapter design

Vendor-neutral `SensorEvent` schema with adapters for CSV, MQTT and other supported connections. Prefer robust import over writing hard-to-test integrations for the first build.

---

## 21. M10 — Evaluation harness 🔒

### 21.1 Evaluation objective

Test the *actual frontier claim*: **Does a persistent evidence graph plus bounded agent investigation produce more accurate, well-grounded answers than an ordinary video summarizer/Q&A model?**

### 21.2 Scenario matrix

| Scenario | Challenge | Expected safe behavior |
|---|---|---|
| C01 Item visibly moved | Straightforward continuity | Reconstruct observed path and correct last seen |
| C02 Occluded for a period | Missing visual evidence | Mark unknown interval, no fabricated route |
| C03 Two identical cases | Visual ambiguity | Don't conflate identities; ask for distinguishing evidence |
| C04 Multiple camera clock offsets | Temporal synchronization | Normalize or explicitly warn and abstain |
| C05 False transfer cue | Person near object, no actual movement | No theft/transfer claim |
| C06 Item returned | Non-monotonic state | Update state and preserve earlier history |
| C07 Cross-camera candidate | Association uncertainty | Show candidate link with evidence and uncertainty |
| C08 Wrong sensor log | Contradictory source | Flag inconsistency, don't blindly trust sensor |
| C09 Camera blind spot | No coverage | No inferred path as observed |
| C10 Prompt injection in filename/caption | Untrusted text | Ignore instructions, preserve investigation scope |
| C11 Two synchronized overlapping cameras | Corresponding visible item landmark | Triangulate XYZ only after calibration and reprojection checks |
| C12 Same-looking but different camera landmark | False cross-view correspondence | Reject link; don't output invented 3D point |
| C13 Camera time-offset or near-parallel rays | Degenerate multi-view geometry | Revert to validated floor XY or unknown; explain limitation |
| C14 Object occluded or outside overlap | Insufficient triangulation evidence | Keep previous verified point as last-seen, no inferred XYZ path |

### 21.3 Metrics

| Metric | Definition | Baseline/comparison |
|---|---|---|
| Object tracking | Track consistency; object switches and missed visible instances | SAM output and manually annotated target truth |
| Event precision/recall | Correctly detected object changes/interactions | Simple frame diff + direct video VLM |
| Last-seen accuracy | Timestamp and zone accuracy compared to ground truth | Raw VLM answer and manual review |
| Spatial position error | Mean/median meter error against measured ground positions | Naive box-center homography |
| **Optional XYZ error** | Median/95th percentile 3D point error in metres on independently measured landmarks | Floor-only proxy where comparison is physically meaningful |
| **Triangulation validity** | Accepted/rejected correspondence precision, per-view reprojection residual and correct abstentions | Ungated triangulation / appearance-only association |
| **Camera rig robustness** | Metric scale error, synchronization sensitivity and calibration invalidation correctness | Unvalidated/default camera pose assumptions |
| Evidence citation validity | Fraction of factual claims with frame references that genuinely support them | Single-model Q&A |
| Unsupported-claim rate | Unsupported claims per case or per 100 assertions | Single-model Q&A |
| Abstention quality | Correct unknown calls where evidence is missing | Forced-answer baseline |
| Active-evidence benefit | Additional correct conclusions after agent-selected clip retrieval | Fixed clip sampling |
| Time-to-finding | Investigator minutes to reach supported last-seen finding | Manual timeline review |
| Cost/latency | Dollars/model calls/seconds per case | Same dataset across variants |

### 21.4 Ablations

- **A0:** Muse Spark reads provided video and answers directly.
- **A1:** A0 + SAM tracks but no persistent world graph.
- **A2:** A1 + spatial graph but no active investigation.
- **A3:** A2 + agent evidence requests and independent verifier (proposed full system).
- **Geometry comparison (separate experiment):** zone-only ↔ homography 2.5D ↔ ungated triangulation ↔ quality-gated triangulation with uncertainty, using only eligible two-camera overlap samples. Keep this separate from agent ablations.

Report measured improvements and regressions. If the multi-agent system does not beat A2, simplify architecture or explain why the benefit is limited. **Do not invent percentages.**

### 21.5 Ground-truth protocol

- Annotators label object presence, movement intervals, camera-local track continuity, item zone/coordinate and observed interactions.
- Keep evaluation labels in a separate dataset inaccessible to runtime agents.
- Split holdouts by incident or scene setup, not adjacent frames from the same video.
- Blind human reviewers score whether each claim is supported by the cited original footage.
- Publish example failure cases and representative qualitative comparisons alongside numbers.

---

## 22. M11 — Investigation actions and reports

### 22.1 Actions

- `create_case`, `set_target_object`, `request_clip`, `annotate_observation`, `review_hypothesis`, `approve_report`, `export_case`, `delete_case`.
- Every external/user-visible action requiring authority goes through the authenticated backend and explicit user confirmation.
- No direct account changes, police alerts or physical access-control operation.

### 22.2 Report structure

- Case scope, purpose, recording sources, media hashes, camera time uncertainty and calibration version.
- Chronological **direct observations** with exact clip/frame references.
- Spatial estimates, error assumptions and unknown intervals in a separate section.
- Hypotheses considered, evidence for and against, and unresolved questions.
- Agent/model tool trace summary, versions and processing conditions.
- Reviewer annotations, approval and export timestamp; derivative file hashes.
- Prominent disclaimer: *"Investigative decision support; not an official forensic certification or determination of identity or wrongdoing."*

### 22.3 Chain of custody truthfulness 🔒

Cryptographic hashes and access logs support integrity checks. They do **not** automatically establish a legally accepted chain of custody. Never make courtroom-admissibility claims without applicable expert validation.

---

## 23. M12 — Operator / hackathon showcase

Separate the demonstration controls from the investigator's genuine application.

Operator mode can:

- Import labeled staged source clips and calibration JSON.
- Select predefined **input** cases, but not pre-scripted AI outputs.
- Inspect raw model responses, SAM masks, camera calibration, evidence graph changes, inference costs and evaluation results.
- Introduce optional simulated door/weight sensor events, clearly marked simulated.
- Rerun evaluation on varied examples with fixed seeds where applicable.

**No demo-specific code path can fabricate the conclusion, movement trace, provenance or metric.** Judges should be able to perturb the input clips/target object and observe a reasoned new result or honest abstention.

---

## 24. Engineering and technology stack (defaults) 🧭

| Layer | Default | Rationale / constraint |
|---|---|---|
| Frontend | Next.js / React / TypeScript | Modern application, file workflow and synchronized panels |
| 3D | Three.js / React Three Fiber, GLB from Blender | Calibrated scene and object paths with smooth camera control |
| Backend | FastAPI / Python | CV, agent tooling, validation, APIs |
| Agent runtime | LangGraph **or** simpler durable orchestrator | Typed, checkpointed tool flows; avoid duplicate systems |
| Meta API | Responses + Files APIs through official-compatible SDK | Muse Spark 1.3 + SAM 3.1 |
| CV tools | FFmpeg, OpenCV, NumPy; optional tracker | Video normalization, homography, geometry, ROI handling |
| Relational/event store | PostgreSQL; optional pgvector | Provenance, cases, time-indexed events; vector recall optional |
| Task execution | Durable queue/worker (e.g., Celery + Redis) | Bounded expensive video jobs, retries and cost controls |
| Assets | Private object storage, signed URLs | Immutable originals and generated derivatives |
| Auth | Well-supported identity provider + site RBAC | Investigator / reviewer / admin separation |
| Observability | OpenTelemetry traces + cost ledger | Correlate evidence/source/model/tool and measure failures |
| Open-weight reasoning | Baseten-hosted Meta Muse Spark Open | Confirmed hackathon access; evaluate as an agent reasoning backend, not CV/geometry |
| Optional multi-view XYZ | OpenCV triangulation and a validated camera rig | Local CPU geometry; no external GPU provider required |

**Avoid** building separate microservices for every agent role; a modular monolith with durable background jobs is sufficient and easier to evaluate.

### 24.1 Runtime principles

- Runtime services retain request IDs and checkpoints; replay/retries must be idempotent.
- Tool outputs and typed schemas get validated, not trusted merely because another agent produced them.
- Model fallbacks never silently change semantics, sensitivity, or privacy mode.
- If Meta APIs fail, the UI still displays original footage, imported observations and a clear "analysis unavailable" state, not a fabricated result.
- No automatic publication of videos or private site maps.

---

## 25. API interfaces (indicative, refine after schema design)

| Method | Route | Purpose |
|---|---|---|
| POST | `/v1/sites` | Create site and floor-plan contract |
| POST | `/v1/sites/{site}/cameras` | Register camera and draft calibration |
| POST | `/v1/media/uploads` | Authorized upload, SHA256, metadata |
| GET | `/v1/media/{id}/frames` | Secure source evidence frame retrieval |
| POST | `/v1/media/{id}/segment` | Request SAM object segmentation/tracking |
| POST | `/v1/calibrations/{id}/validate` | Reprojection and quality checks |
| POST | `/v1/cases` | Start a case with scope and target object |
| POST | `/v1/cases/{id}/investigate` | Start bounded multi-agent investigation |
| GET | `/v1/cases/{id}/state` | Case events, findings, unknowns, revisions |
| GET | `/v1/cases/{id}/world-at?time=...` | 3D scene projection at selected time |
| GET | `/v1/cases/{id}/evidence/{obs_id}` | Resolve citation to authorized original source |
| POST | `/v1/cases/{id}/evidence/import` | Import another camera clip or optional sensor log |
| POST | `/v1/cases/{id}/review` | Reviewer annotation/approval |
| POST | `/v1/cases/{id}/export` | Auditable report and hash manifest |
| GET | `/v1/evaluations` | Operator-only evaluation results |

Use REST plus WebSocket/SSE for job progress; avoid streaming raw private video through publicly accessible channels.

---

## 26. Non-functional requirements

| Area | Requirement |
|---|---|
| **Correctness** 🔒 | Claims have valid source IDs; no unobserved route displayed as observed |
| **Privacy** 🔒 | Authorized footage, isolation, deletion, no biometric identity extraction |
| **Reliability** 🔒 | Idempotent expensive tool calls, explicit failure states, repeatable full workflow |
| **Security** 🔒 | Server-only secrets, upload scanning/validation, RBAC, signed media, injection defenses |
| **Traceability** 🔒 | Original hash -> observation -> estimate -> event -> hypothesis -> verification -> UI/report |
| **Performance** 🧭 | Measured processing per video minute; viewer responsive without reprocessing footage on every scrub |
| **UX** 🧭 | Works on common laptops; 3D graceful degradation to 2D; accessible contrast and labels |
| **Budget** 🧭 | Usage ledger, per-case caps, estimated spend preflight and bounded retries |
| **Portability** 🧭 | Docker Compose local launch, `.env.example`, deployment notes |
| **Licensing** 🔒 | Dataset/footage/asset/model terms logged and respected |
| **Documentation** 🔒 | Setup, technical limitations, demo data rights, evaluation and model cost recorded |

---

## 27. Repository and documentation

Suggested structure (adjust after real implementation):

```text
/apps/web                  investigator UI and 3D
/apps/operator             private demo/evaluation surface
/services/api              FastAPI and typed tool boundary
/services/workers          ingestion, video jobs, model adapters
/packages/contracts        source-of-truth schemas and generated clients
/packages/spatial          calibration, projection, graph operations
/packages/agents           orchestrator, agent prompts, verifier policies
/ml/evaluation             ground-truth scenarios, metrics and ablations
/assets/3d                 source Blender scene and GLB
/demo                       original staged clips, labels, rights manifest
/docs                       evidence, privacy, models, decisions
```

Required documents:

- `README.md`: problem, demonstration, run steps, architecture, actual vs simulated, evaluation snapshot, limitations.
- `docs/DECISIONS.md`: why choices changed, alternatives and evidence.
- `docs/DEPENDENCIES.md`: pins, licensing, source links, checked dates.
- `docs/META_MODEL_USAGE.md`: API model IDs, roles, sample calls, usage logs, credits/hosting.
- `docs/DATA_RIGHTS.md`: media permissions, actor consent, provenance, source hashes.
- `docs/CALIBRATION.md`: camera setup, homography, **multiview intrinsics/extrinsics**, rig/time synchronization, measured errors and invalidation procedure.
- `docs/MULTIVIEW_3D.md`: optional true-XYZ implementation, tested landmark correspondence, reprojection checks, failure cases, coordinate frames and reproducible evaluation.
- `docs/EVIDENCE_SCHEMA.md`: entity/event/claim contracts and semantics.
- `docs/EVALUATION.md`: dataset, labels, holdouts, metrics, ablations, failure cases.
- `docs/PRIVACY.md`: retention, deletion, access controls, provider processing.
- `docs/NEW_WORK.md`: what was created during this hackathon with relevant commits and demo features.
- `docs/LIMITATIONS.md`: failures, unknowns, and claims *not* made.

### 27.1 Real vs simulated statement 🔒

| Category | Truthful label |
|---|---|
| Team-recorded consented CCTV footage | **Real recording of staged event** |
| Object tracks generated by SAM | **Model inference on real recorded frames** |
| World-map coordinates | **Estimated from calibrated geometry**; floor-plane XY is default |
| Optional `(x,y,z)` points | **Metric triangulation estimates only where synchronized, overlapping calibrated cameras and valid same-point correspondence exist** |
| Interactive room geometry | **Measured/prebuilt scene; not inferred from hidden imagery** |
| Hypotheses and agent conclusions | **AI-generated interpretations with source references** |
| Optional CSV door/weight events | **Simulated input if not hardware-measured** |
| Case ground-truth labels | **Evaluator-only annotations, not model inputs** |
| Example reports | **Investigation support, not forensic certification** |

---

## 28. Definition of done

This build meets its product-level definition of done when:

1. An authorized operator can upload a new, unscripted recording of a staged room and verify the original file hash.
2. The user can select a target object and obtain SAM-derived visual observations with timestamped source frame references.
3. At least one calibrated camera maps relevant ground-contact tracks to a known spatial layout with measured mapping error; no second camera or triangulation is required for the core build.
4. A missing-object query triggers a genuine **multi-step evidence investigation**: source search, hypothesis formulation, verifier check, and a supported or abstaining answer.
5. The 3D scene displays observed trajectories and clearly distinguishes spatial estimates and footage gaps.
6. Clicking a timeline event resolves to its original footage and the associated model/processing provenance.
7. Additional evidence can revise an earlier hypothesis while preserving case history.
8. A reviewer can approve/export an audit-friendly report; it never makes unsupported identity or criminal-intent claims.
9. The evaluation harness compares the full system against simpler baselines, reports actual metrics and documents failures.
10. A judge can reproduce the flow from a public repo and a **3-minute demo** highlighting genuinely new hackathon work.
11. Every 🔒 invariant holds, including rights to video, privacy, authenticity and no fabricated observations.

---

## 29. Invariants checklist 🔒

- [ ] Only authorized, consented or appropriately licensed footage is processed.
- [ ] No biometric matching, face reconstruction, fingerprint inference or suspect scoring.
- [ ] Original videos are immutable and hashed; derivatives identify their source.
- [ ] Frame-level citations are resolvable and valid.
- [ ] No claim is treated as factual solely because an agent asserted it.
- [ ] Camera clock offsets are checked or explicitly warned.
- [ ] Spatial positions carry calibration/uncertainty metadata and explicit mode (`floor_xy` vs `multiview_xyz`).
- [ ] Optional multi-view XYZ requires two+ synchronized overlapping calibrated views and independently verified same-point correspondences; invalid geometry never appears as observed motion.
- [ ] If optional XYZ fails, core 2.5D investigations remain functional and truthful.
- [ ] Solid observed paths never bridge unobserved intervals.
- [ ] Cross-camera links are unverified until supporting evidence exists.
- [ ] Hypotheses and unsupported claims are distinguished from observations.
- [ ] No ground truth or operator-selected answer leaks into model inference.
- [ ] Model/API versions and licenses are checked against current docs.
- [ ] Participant credits are not assumed available before applied to billing.
- [ ] External actions require human authorization.
- [ ] Public repo contains no secrets or private footage.
- [ ] Demo only highlights work built during the event, properly documented.

---

## 30. Open questions and research risks

1. **True model capability:** How well does SAM 3.1 track small equipment cases through complete/partial occlusion? Measure on original footage.
2. **Exact API behavior:** What duration, resolution, file and concurrency constraints apply to Meta video requests today? Confirm with smoke tests.
3. **Calibration:** Can the room be measured to useful floor-plane accuracy? If not, switch to zone-level positions. For optional XYZ, can two overlapping cameras be fully calibrated with acceptable reprojection and independent 3D landmark error? If not, keep 2.5D.
4. **Cross-camera reliability:** Are two camera clocks and routes sufficiently aligned for meaningful association? Otherwise explicitly leave links unresolved.
5. **Agent value:** Does the verifier and active evidence retrieval beat a simpler Spark baseline? Keep only measured benefits.
6. **Data rights:** Does the user's intended footage permit hosted processing? Default to local staged footage.
7. **Cost:** Actual multimodal token billing and retry behavior can differ from rough API price tables.
8. **Meta credits:** Confirm $150 redemption link activation and applied credit balance; partner award decisions are external.
9. **Camera integration:** Uploaded footage is the supported default. ONVIF/NVR integration depends on actual camera compatibility and authorization.
10. **Competition rubric:** Official written guide says 25/25/25/25, later kickoff slide 30/25/20/25; verify in Discord.
11. **Product name:** Spoor is the selected project name; check existing trademarks before commercialization.

---

## 31. Business model and future extensions (not in core build)

- **Initial customer:** business locations already using CCTV for asset protection or process auditing (small warehouses, laboratories, equipment rooms).
- **Core value:** reduce manual evidence search and make review auditable, not predict crime.
- **Possible pricing:** per site/camera or processed-hour usage; requires validation against real operational costs and privacy/security obligations.
- **Integrations:** NVR/ONVIF footage import, authorized access logs, RFID asset tracking, door sensors and existing incident platforms.
- **Future research:** distributed visual memory across many cameras, uncertain graph association, local edge models and robust scene-level causal hypotheses.
- **Enterprise requirements before real deployment:** legal/privacy review, role/access integration, security audits, evaluation across real camera conditions, data residency and third-party processing contracts.

---

## 32. Confirmed hackathon credits and budget — 27 October 2026

**Scope decision:** The participant has **received** Meta Model API hackathon credits and Baseten's award email for **$100** with access to **Muse Spark Open** and an advertised rate limit of up to **2 million tokens/minute**. There is **no confirmed Modal or Fireworks credit**. The active architecture, evaluation plan and budget use **Meta + Baseten + local CPU/GPU only**.

| Provider | User-reported access | Assigned project workload | Required before running jobs |
|---|---|---|---|
| **Meta Model API** | Hackathon model API credit access (participant reports received; offer advertised as $150) | Muse Spark 1.3 video understanding, SAM 3.1 object masks/tracking; limited Wonder tests if justified | Verify activated balance, model entitlement, privacy terms, usage caps, current API behavior |
| **Baseten** | Awarded **$100**; Muse Spark Open, up to **2M TPM** advertised | Lead/evidence/hypothesis/verifier *reasoning* over structured evidence; optional benchmark against hosted Spark | Redeem provider instructions, verify allowed model ID, credit balance, rate limit and expiry |
| **Local infrastructure** | Existing developer machine/CPU/GPU; capacity to be measured | OpenCV homography and optional triangulation, FFmpeg, association graph, appearance vectors if feasible | Benchmark speed and memory locally; don't assume a paid GPU |

**No additional partner credits are assumed.** Pending/non-awarded credits are deliberately excluded from this revision. Separate providers have separate keys, usage rules and billing; Baseten credit cannot pay for hosted SAM requests through Meta.

### 32.1 Spending safeguards 🔒

- Verify that Meta credits are **applied to billing**, not merely that an activation email was received. A billing alert is not necessarily a hard account-level cost cap.
- Create separate server-side provider adapters, spend ledgers and bounded budgets per case/test: video upload + inference, SAM calls, Muse Spark calls, Baseten agent turns, cache hits and retries.
- Run only authorized/consented staged footage on hosted APIs. Review current retention/training modes and use the data-handling option appropriate to the recordings; do not infer privacy from provider marketing claims.
- Cache by original file hash, clip window, prompt/schema/model version, frame selection and calibration version; do not reprocess every clip when scrubbing a 3D timeline.
- Use **Baseten Muse Spark Open** for structured agent tasks only after a smoke test. If Baseten service or schema validation fails, fall back to authorized Meta-hosted reasoning within budget, or return `analysis_unavailable` while leaving evidence accessible.
- Keep GPU-intensive training, unrestricted batch processing and optional true-XYZ experiments **off by default** until measured cost/capacity permits them.

### 32.2 Immediate validation checklist

1. Meta Billing confirms actual promotional balance and lists the required Muse Spark / SAM endpoints as callable.
2. Baseten redemption email/code has been applied; account dashboard shows credit, correct hackathon Muse Spark Open model and usage/expiry conditions.
3. Run one bounded Muse Spark multimodal-video request and one targeted SAM segmentation/tracking smoke test on **owned staged footage**; record exact model IDs, outputs, latency and cost.
4. Run one Baseten Muse Spark Open structured reasoning/tool-call test against a **synthetic evidence graph with known answers**. Record response parsing, model ID, latency and cost; test abstention on missing evidence.
5. Confirm OpenCV and geometry jobs (including optional triangulation) run locally without needing unreceived provider funding.
6. Record outcomes and provider constraints in `docs/DEPENDENCIES.md`, `docs/DECISIONS.md` and `docs/META_MODEL_USAGE.md`; never commit API keys, footage without rights, or billing details.

### 32.3 Provider selection by agent role 🧭

| Role | Default model/provider | Rationale / fallbacks |
|---|---|---|
| Clip interpretation and nuanced visual event grounding | **Muse Spark 1.3 / Meta Model API** | Native hosted multimodal video understanding; evidence references still verified separately |
| Segmentation and per-clip object tracking | **SAM 3.1 / Meta Model API** | Source-aligned masks/tracks; not a cross-camera identity or depth solver |
| Lead planner and hypothesis agent | **Muse Spark Open / Baseten**, **only after benchmarking** | Use selected credits for structured tool reasoning; Meta hosted Spark fallback if quality or API compatibility fails |
| Independent verification agent | Prefer **different prompts and independent evidence queries**, with Baseten Open vs Meta Spark comparative test | Using a second model alone does not guarantee independence; verify source frames deterministically |
| Calibration, homography, triangulation, track association | **OpenCV + tested local libraries** | Deterministic geometry, measurable error; **not an LLM role** |
| Interactive 3D and camera coverage | **Three.js / React Three Fiber** | Browser render of measured site and evidence, without fabricated paths |

**Note:** The open-weights bonus award requires verified eligible model execution, and the hackathon may enforce further award rules. Use Baseten's Muse Spark Open meaningfully if it performs well, but never distort the investigation to increase model count.
---

## 33. Glossary

| Term | Meaning |
|---|---|
| **SAM** | Segment Anything Model; produces video/image object masks and track geometry |
| **VLM** | Vision-language model; interprets media and outputs descriptions/reasoned text |
| **Evidence graph** | Structured links among media, observations, objects, times, locations, hypotheses and findings |
| **Event sourcing** | Storing immutable fact/change records and deriving current state from them |
| **Calibration / homography** | Transformation mapping positions on a known plane in an image to scene coordinates |
| **Camera intrinsics/extrinsics** | Camera lens/projection properties and its pose relative to the shared site coordinate system |
| **Triangulation** | Geometric estimation of a 3D point from corresponding 2D observations in two+ calibrated overlapping views |
| **Reprojection error** | Discrepancy between a 3D estimate projected back into a camera and its actual observed 2D landmark |
| **Cheirality** | Physical condition requiring a reconstructed point to lie in front of the observing cameras |
| **2.5D fallback** | Mapping observable ground locations into a prebuilt 3D scene without claiming recovered true object height |
| **PTS** | Presentation timestamp in the original video timeline |
| **Track ID** | Temporary identity for a visible object/person within a clip, **not** real-world personal identity |
| **Occlusion** | Object is blocked from camera view without proof it moved or disappeared |
| **Association** | Hypothesized link that two visual observations refer to the same physical object |
| **Hypothesis** | Testable explanation with supporting, contradictory and missing evidence |
| **Abstention** | Refusing to claim a result when observations are insufficient |
| **Agent** | Model-enabled decision component with bounded tools and responsibilities |
| **Tool** | Deterministic retrieval/CV/geometry/storage action called by agents |
| **Provenance** | Record of where data and conclusions originated and how they were transformed |
| **Digital twin** | Interactive representation of known physical layout and observed/estimated state |

---

## 34. References — current official starting points

**Meta models and implementation**
- Meta Global AI Developer Hackathon: https://events.cerebralvalley.ai/e/meta-ai-developer-hackathon
- Meta Model API and pricing: https://dev.meta.ai/products/meta-model-api
- Meta models reference: https://dev.meta.ai/docs/models
- Muse Spark 1.3: https://dev.meta.ai/models/muse-spark
- Muse Wonder: https://dev.meta.ai/models/muse-wonder
- SAM 3.1: https://dev.meta.ai/models/sam-3-1
- Video understanding: https://dev.meta.ai/docs/video-understanding
- Media segmentation: https://dev.meta.ai/docs/media-segmentation
- SAM segmenting with prompts: https://dev.meta.ai/docs/sam/segmenting
- Muse Glimmer: https://dev.meta.ai/models/muse-glimmer
- Muse Spark Open: https://dev.meta.ai/models/muse-spark-open
- Muse Voice Transcribe: https://dev.meta.ai/models/muse-voice-transcribe
- Muse Image: https://dev.meta.ai/models/muse-image
- Muse Code: https://dev.meta.ai/lp/muse-code

**Development and geometry**
- OpenCV: https://docs.opencv.org/
- OpenCV planar homography details: https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html
- OpenCV camera geometry and calibration: https://docs.opencv.org/4.13.0/d9/d0c/group__calib3d.html
- OpenCV solvePnP reference (pin correct OpenCV 4.x version before implementation): https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html
- Caliscope multi-camera calibration (BSD-2-Clause): https://mprib.github.io/caliscope/
- TAPVid-MV benchmark, multi-view 3D tracking research: https://tapvidmv.github.io/
- Norfair (BSD-3-Clause), tracker baseline: https://github.com/tryolabs/norfair
- BoT-SORT and ReID reference (licensing checks required): https://docs.ultralytics.com/modes/track
- Camera topology and MTMCT association research: https://arxiv.org/abs/2105.01213
- FFmpeg: https://ffmpeg.org/documentation.html
- Three.js: https://threejs.org/docs/
- React Three Fiber: https://r3f.docs.pmnd.rs/
- Blender: https://docs.blender.org/manual/en/latest/
- LangGraph: https://docs.langchain.com/oss/python/langgraph/overview
- FastAPI: https://fastapi.tiangolo.com/
- Next.js: https://nextjs.org/docs
- Postgres: https://www.postgresql.org/docs/
- ONVIF: https://www.onvif.org/

**Confirmed open-weight inference partner**
- Baseten: https://www.baseten.co/

**Supplied hackathon participant guide**
- Internal uploaded Participant Guide (captured October 2026). Keep its submission requirements and credit form links in the project docs; verify changes in the official authenticated dashboard/Discord.

---

*End of PRD v3. If the AI cannot show the evidence, it must not present the claim as fact. Optional true-XYZ geometry is a rigorously gated feature, never an excuse to invent unseen physical motion.*

---

## Addendum A — Parcel-hub pivot (2026-10-28)

**Decision (owner):** the demonstration site changes from a small storeroom with a missing equipment case to a
**fictional Malaysian parcel sorting hub**, modelled in Blender with virtual CCTV, and the missing object is a **parcel**.
Research basis: `reports/Parcel hub tracking and investigations.md`.

What changes:
- **Canonical use case (§5.2):** a customer reports a parcel never arrived. The hub's scan log shows where the parcel
  was last *scanned*; Spoor establishes what the CCTV shows between scans, where it was last *seen*, and whether any
  evidence shows it leaving (directly, or inside a bag/cage/trailer that left).
- **New evidence source (§8.2):** barcode/RFID scan logs. A scan proves *identity* at a read point; it does not prove
  where the parcel went next. Scan logs must be labelled `scan_real` or `scan_simulated` end to end.
- **Identity:** parcels look alike, so identity comes from scans (and relabel/alias links), and is carried by video only
  along continuous tracking. Ambiguous look-alikes yield `unresolved`, never a guess (§14.3).
- **Containers:** a parcel's location inside a bag/cage/trailer is inherited and labelled *estimated* (EPCIS
  aggregation semantics: a presumption until contradicted).
- **Time:** device clocks (sorter, handhelds, NVR, cameras) are fitted from matched anchor events, with residuals
  recorded in the case file.
- **Scope of 3D:** one hub only; the wider journey (linehaul, other hubs, last mile) appears as a 2D scan timeline.
- **Privacy positioning (Malaysia PDPA):** purpose is parcel chain-of-custody and claims evidence, not worker
  monitoring; no face recognition; operators only as pseudonymous tokens; synthetic footage contains no personal data.

All 🔒 invariants in this PRD are unchanged.
