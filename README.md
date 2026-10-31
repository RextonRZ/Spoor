# Spoor

**Give physical spaces a searchable memory — and every answer a source.**

Spoor turns authorized CCTV recordings into a queryable history of where a physical object was *observed*. An
investigator asks "Where is the blue equipment case? Did it leave the room?" and gets the last **visibly confirmed**
position with a link to the exact original frame, the intervals where nothing is known, competing hypotheses with
their verification status, and a report that separates observation from inference.

Built for the Meta Global AI Developer Hackathon 2026 (theme: Push the Frontier). Full spec:
[Spoor_Meta_Hackathon_PRD_v3.md](Spoor_Meta_Hackathon_PRD_v3.md) · build plan: [docs/build/](docs/build/README.md).

> Investigative decision support; not an official forensic certification or determination of identity or wrongdoing.

## How it works

```
authorized MP4 ──> ingest (SHA-256, read-only original, frame-aligned proxy, timing flags)
                     │
         SAM 3.1 (Meta Model API) ──> per-clip tracks & observations, citing ORIGINAL frames
                     │
   floor homography (OpenCV) ──> metric floor position + measured uncertainty, or honest fallback
                     │
        append-only evidence store ──> last confirmed · visibility timeline · unobserved intervals
                     │
   Evidence & Hypothesis agents (Muse Spark) ──> structured claims ──> deterministic Verifier
                     │
        answer composed ONLY from verified findings · report export · reviewer approval
```

**Muse Spark interprets. SAM 3.1 sees object regions. The geometry engine maps. The store remembers. The verifier
challenges. The human decides.**

## Status (2026-10-27) — read this first

| Area | State |
|---|---|
| Backend (contracts, ingest, calibration, store, perception, reasoning, verifier, agents, API, reports) | Built; 183 tests pass; independent logic review done and fixed ([IMPROVEMENTS](docs/IMPROVEMENTS.md)) |
| Live Meta Model API (SAM 3.1, Muse Spark 1.3) and Baseten | **Not yet run** — adapters tested against fixtures only; awaiting API keys |
| Real staged footage, real room calibration | **Not yet recorded** |
| Evaluation results | **None yet** — harness ready (`ml/evaluation`) |
| Frontend / 3D | Not started (owner is designing it; backend exposes everything over HTTP) |
| Postgres, Docker images | Written, **untested** |

## Run it

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/), FFmpeg on PATH.

```bash
cd backend
uv sync
uv run pytest                       # 183 tests, no keys needed
cp .env.example .env                # add MODEL_API_KEY (Meta) and optionally Baseten
cp users.example.json users.json    # set long random tokens
uv run uvicorn spoor.api.app:create_app --factory
```

Provider smoke tests (need keys + your own staged clip): see
[docs/build/00-setup-and-smoke-tests.md](docs/build/00-setup-and-smoke-tests.md).

## Real vs simulated (PRD §27.1)

| Category | Label |
|---|---|
| Team-recorded consented footage | Real recording of staged event |
| SAM tracks | Model inference on real recorded frames |
| Floor positions | Estimated from calibrated geometry (floor XY by default) |
| Optional XYZ | Metric triangulation estimates only with a validated overlapping rig (off by default) |
| Room geometry | Measured / prebuilt; never inferred from hidden imagery |
| Hypotheses and agent output | AI-generated interpretations with source references |
| Door/weight CSV events | Simulated unless hardware-measured — each row must declare which |
| Ground-truth labels | Evaluator-only, never model inputs |

Test fixtures (synthetic ffmpeg clips, synthesized SAM wire output, scripted agent turns) exist only under
`backend/tests/` and are never presented as inference results.

## Docs

[DECISIONS](docs/DECISIONS.md) · [DEPENDENCIES](docs/DEPENDENCIES.md) · [META_MODEL_USAGE](docs/META_MODEL_USAGE.md) ·
[CALIBRATION](docs/CALIBRATION.md) · [MULTIVIEW_3D](docs/MULTIVIEW_3D.md) · [EVIDENCE_SCHEMA](docs/EVIDENCE_SCHEMA.md) ·
[EVALUATION](docs/EVALUATION.md) · [PRIVACY](docs/PRIVACY.md) · [DATA_RIGHTS](docs/DATA_RIGHTS.md) ·
[NEW_WORK](docs/NEW_WORK.md) · [LIMITATIONS](docs/LIMITATIONS.md) · [IMPROVEMENTS](docs/IMPROVEMENTS.md) ·
[DEMO_SCRIPT](docs/DEMO_SCRIPT.md) · [DEPLOYMENT](docs/DEPLOYMENT.md)
