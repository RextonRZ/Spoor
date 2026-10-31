# F-051 — Cameras (Cameras.dc.html): one clock, zone filter, Camera wall | 3D hub (real hub.glb)

From the frontend agent.

## 1. Changed since last request
- **`/wall` = Cameras**, ported from `Cameras.dc.html`. The old camera-wall page and the `components/wall` code are
  deleted.
  - "19 cameras · all playing the same moment" / **"The whole hub at hh:mm:ss"**.
  - Zone filter **All 19 · Inbound · Sorting · Outbound** (the prototype's grouping), and the **Camera wall | 3D hub**
    switch.
  - **One clock for every camera**: play, scrub, time, "Each clip placed by its own clock check". It spans the
    imported footage; with none, ±10 min around the end of the scan log.
  - **Wall** (4 columns): each camera's original frame at that instant, fetched once the scrubber rests. With no
    footage for that instant it reads "No footage for this moment". The camera name is in plain words ("Chutes C07 to
    C12"). **"In a case"** links to the open case's Proof for cameras the case depends on.
  - **3D hub = the real Blender `hub.glb`** (`Scene3D`), centred on the open case's trail, in plan orientation, with
    landmark labels, the trail's start and end ("Scanned 14:10:40", "Last seen 14:11:12"), the compass and Reset
    view.
- Fix: `Scene3D` now imports its own styles (labels, compass, tools). They were loaded only by the deleted workspace
  page, so the Proof page's 3D view had lost them too.

## 2. Check these
- `frontend/review_pack/flow/desktop_07_cameras.png`, `desktop_07b_cameras_3d.png`, `mobile_07_cameras.png`
- No console errors on desktop or mobile. Typecheck and lint clean.

## 3. Next
- **Settings & data** (from the avatar menu; today's Operator page) gets the flow look: Data sources (drop zones),
  Cameras & clocks, Model calls (incl. Malaysian context), Evaluation.
- The "Cases" nav item opens `/`, which still renders the old case list. I'll rebuild it as a plain list of cases in
  the Hub's row style. The prototype has no Cases list, so say if Cases should instead open the latest case's
  Answer.
- After the flow is complete, I'll replace the old e2e/review specs with flow specs on the S2 store, including the
  em-dash check and a11y.
