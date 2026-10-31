# F-036 — J2 lead investigator (Muse Wonder 1.0) + docs (deployment, privacy)

From the frontend agent.

## 1. Changed since last request

### J2 — lead investigator (`backend/src/spoor/forensics/lead.py`)
- **`POST /v1/cases/{id}/lead-plan`** (investigator, paid).
  - Muse Wonder 1.0 (`/v1/responses`, strict json_schema) plans which footage to analyse next.
  - Its input is the typed journey and the missing moment, passed as quoted data. These are the read models the UI
    shows.
- **Deterministic check on the plan:**
  - a step is kept only when its camera is one of the missing moment's candidates and every cited evidence id exists;
  - the rest are **dropped and listed as rejected**, with the reason;
  - the plan says "a plan for what to analyse next, not evidence".
- **Recorded:** a `CostEntry` (model, tokens, US$ estimate at $4 in / $20 out per 1M tokens) and an `AgentStep` (role
  `lead`). `GET` returns the latest plan, whether the key is present, and the cost estimate (about US$0.07, from the J1
  run).
- **No key:** 503 "analysis unavailable: no API key (Muse Wonder needs MODEL_API_KEY)".
- **Test** with a fake Wonder: 1 valid step kept; a non-candidate camera and a made-up evidence id rejected with their
  reasons; cost 0.068 recorded; the latest plan readable.
- **UI:** the Agent tab opens with "Lead investigator · muse-wonder-1.0".
  - The button states the cost before spending: "Plan the next footage to analyse · about US$0.07".
  - No key: "Unavailable: no API key …".
  - After a run: summary, steps (camera · what to check · why), "N steps dropped by the evidence check", and the real
    cost.
- **Not run against the live case yet:** the local backend runs in no-key mode. The first real lead plan will be on S2
  in the keyed run, which is the comparison J1 step 4 asks for. Expected cost ≈ $0.07.

### Docs
- **`docs/DEPLOYMENT.md`** (owner_ideas §2), linked from the README:
  - day one from the floor plan, machine spec, scan points and camera calibration;
  - an optional one-time 3D scan (phone LiDAR / BLK360 / Matterport Pro3 / NavVis / Gaussian splatting), registered
    to the same site frame;
  - "live" from CCTV + the scan log + PLC, never from re-scanning.
- **`docs/PRIVACY.md`:**
  - signed frame / crop / playback / reel links: 5 min, issued by case- or site-checked routes, audited (F-023 P2 #1);
  - parcels-not-people rules (owner_ideas §4);
  - scanner user ids not displayed, and a later reveal must carry a typed reason and be audited;
  - floor search outcomes are pseudonymous.

## 2. Check these
- `backend/src/spoor/forensics/lead.py`, `frontend/src/components/workspace/LeadPlan.tsx`
- `docs/DEPLOYMENT.md`, `docs/PRIVACY.md`
- **Tests:** backend forensics 20 ✓; frontend e2e 17/17 ✓ (the Agent tab still shows the honest no-key state).

## 3. Next
- J2b wiring: the agents attach the key frames (last confirmed, missing-moment frames, CAM_19 doorway) as images to
  Spark Open.
- Then the keyed S2 run once the render exists.
