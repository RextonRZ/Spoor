# F-048 — Flow screen 4: Proof (Proof.dc.html)

From the frontend agent.

## 1. Changed since last request
- **`/cases/{id}/proof`**, ported from `Proof.dc.html` (widths, sizes, colours, copy).
  - **Video | 3D hub** switch. 3D is the real hub (`hub.glb`, `Scene3D` with §H/§I: plan orientation, compass,
    landmarks, trail framing) in the player area.
  - **One player, one transport** (play/pause, −1/+1 frame, scrub ±10 s around the moment, time, 1× / 4×). It shows
    the camera's original frame at that time. With no footage it says, in the player, "No footage from CAM 11 for
    14:11:12 yet." and the controls are disabled. A selected records conflict shows the prototype's red dashed panel
    ("The sorter's times don't fit the belt." plus the statement).
  - **"Every camera on its route, in order":** the camera watching each scan point (tunnel, sorter, chute), then the
    cameras due next from the missing moment, then a **Records** tile when the case has a records conflict. Statuses
    are Seen hh:mm:ss / Expected, not seen / Not checked yet / No footage / Records disagree. Clicking a tile selects
    that moment.
  - **Side card:** camera · place · time, a headline ("Into chute C12 at 14:11:12."), and two plain sentences.
  - **Plan:** the route with the selected camera in play.
  - **"Go look: blind corner, exception store"** (short place words from a new `shortPlace` helper; the Answer's
    "Most likely" reason uses it too).
  - **Evidence details** (folded): the original recording id and SHA-256 when there is one, the clock state and the
    records check.
- Breadcrumb "Hub › CTX… › Proof" (CaseSteps gained a `page` crumb).

## 2. Check these
- `frontend/review_pack/flow/desktop_04_proof.png`, `desktop_04_proof_full.png`, `mobile_04_proof.png`
- No console errors on Hub, Investigating, Answer or Proof. An earlier hydration warning came from a hot reload
  during my edit; it doesn't reproduce.
- Typecheck and lint clean.

## 3. Notes
- With the S2 render imported, the same page shows real frames, Seen / Expected-not-seen tiles, the follow box,
  and the §G pin or box. Nothing on this screen is mock data.
- Next: Go look (phone), Report (with "Share report", no approval step), Cameras.
