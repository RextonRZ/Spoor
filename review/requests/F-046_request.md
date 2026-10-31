# F-046 — Flow screen 2: Investigating (agent_showcase_0925), driven by typed run steps

From the frontend agent.

## 1. Changed since last request
- **Backend: the investigation run as typed steps** (`backend/src/spoor/forensics/run.py`).
  - `POST /v1/cases/{id}/run` starts a job that streams `run_step` events over `/v1/jobs/{id}/events`.
    `GET /v1/cases/{id}/run` replays the latest run and also returns the crew, tools, optional tools and map columns.
  - Each step carries:
    - role and model (Lead investigator · Muse Wonder, On-site triage · Muse Glimmer · Modal, Camera analysts ·
      Muse Spark, Tracker · SAM 3.1, Verifier · rules, no AI, Reporter · Muse Spark Open · Baseten);
    - tool, status (done / unavailable / rejected), one plain sentence and a MYT clock;
    - the search-map node and its state;
    - the running cost, cameras checked, and a receipt.
  - Every step is stored as an `AgentStep` (role `run:*`), so the Answer screen can show the frozen map later.
  - **No-key honesty:**
    - read_scans, pick_cameras (from the floor plan, belt routes and camera views), verify and create_search_task
      really run;
    - the Wonder plan, Glimmer triage, Spark per camera and SAM tracking emit `unavailable` with the reason ("no
      model key", "no footage imported for this camera in the window", "no results for this window");
    - with keys configured but a step not yet wired, it says "isn't part of this run yet". It never fakes a result.
  - Wording matches the Hub ("Read 3 scans. Last: went into chute C12 at 14:11:12."); camera places are in the
    prototype's style ("chutes C07 to C12").
  - Tests: `backend/tests/test_run.py` (typed and honest no-key run, replayable; keyed-but-unwired wording).
- **Frontend: `/cases/{id}/investigate`**, ported from `Investigate.dc.html` (sizes, colours, copy).
  - Breadcrumb, title, live meter (US$ spent · N of 19 cameras checked · seconds · Replay).
  - **Search map:** columns Last scan / Watching that spot / Where the belt takes it / Ways out on foot. Node states
    are seen, checking, ruled out, rejected, records disagree, no footage, not chosen.
  - **What the crew did:** the timestamped log.
  - **Hero:** the camera being checked; with no footage, the prototype's placeholder style.
  - **The investigation crew:** ✓ done, dashed = only when needed, struck = needs a model key.
  - Footer: the run's end line ("Took 0.5 s and US$0.00. 0 cameras checked of 19.") and **See the answer**.
  - First visit with no run: it starts the run and streams it. With a stored run: it replays it; Replay replays
    again.
  - The Hub's Investigate button leads here.

## 2. Check these
- `frontend/review_pack/flow/desktop_02_investigating.png` (1440 × 900), `frontend/review_pack/flow/mobile_02_investigating.png`
- The prototype is a template file (placeholders without its runtime), so there is no image side-by-side this time.
  The structure and copy follow its markup and step data.
- Tests: backend `test_run` ✓; typecheck and lint clean.

## 3. Notes and questions
- **The showcase needs the keyed S2 run** for checking / seen / rejected / re-plan / records disagree to appear. The
  verifier rejection needs the look-alike candidate the builder is placing. I'll wire the keyed steps next to the
  existing backends: Wonder `plan_investigation`, Spark clip analysis, `run_perception` for SAM, Glimmer flags as
  `triage_flags`.
- I left out **"By hand: about 2 to 4 hours of watching 19 cameras"**: I have no source for that baseline yet. With
  a cited figure (docs), I'll add it to the end line.
- Next: Answer.
