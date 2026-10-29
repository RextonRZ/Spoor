# Step 09 — API, audit, reports & access (M11)

**PRD:** §7.4, §22, §25, §26 · **Depends on:** 04, 08 · **Location:** `services/api`

## Goal

Expose everything through an authenticated FastAPI backend that a future frontend (step 12) can consume, and export
an audit-friendly investigation-support packet.

## Build

1. **Routes** from PRD §25 (`/v1/sites`, `/v1/media/uploads`, `/v1/cases/{id}/investigate`, `/world-at`,
   `/evidence/{obs_id}`, `/export`, …). Job progress via SSE.
2. **Auth & RBAC:** roles `site_admin | investigator | reviewer`; per-site isolation. 🧭 Simple token auth for the
   hackathon; document the gap.
3. **Media access:** short-lived signed URLs; originals never public.
4. **Actions** (§22.1) with explicit confirmation: `create_case`, `set_target_object`, `request_clip`,
   `annotate_observation`, `review_hypothesis`, `approve_report`, `export_case`, `delete_case`.
5. **Report export** (§22.2): scope, sources + hashes, clock uncertainty, calibration version, chronological direct
   observations, spatial estimates + unknowns (separate section), hypotheses for/against, model/tool trace,
   reviewer approval, disclaimer. JSON + PDF/HTML; hash manifest.
6. **Audit log** for every human/agent action; rate limits; upload validation.
7. **Docker Compose:** api + worker + postgres (+ redis if queue needed). `.env.example`.

## Done when

- End-to-end via HTTP (no UI): upload → segment → investigate → export, with report hashes verifiable.
- Reviewer can approve; investigator cannot approve their own report if roles differ.

## Status — done (2026-10-27)

Code: `backend/src/spoor/api/` (`app`, `auth`, `jobs`, `services`), `spoor/reports.py`. Tests: `tests/test_api.py`.
Run: `cd backend && uv run uvicorn spoor.api.app:create_app --factory` (needs `USERS_FILE`, see
`users.example.json`). 29 routes. Bearer tokens + per-site RBAC; HMAC-signed 5-minute frame links; rate limit;
audit entry on every write; jobs with SSE progress; report export (JSON/HTML + hash manifest) and approval by a
different reviewer against the same case revision. `docker-compose.yml` + `backend/Dockerfile` written, **not built**
(Docker daemon not running).
