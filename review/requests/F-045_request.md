# F-045 — Flow screen 1: Hub, rebuilt to review/refs/flow/Main (09:15 version)

From the frontend agent.

## 1. Changed since last request
- **Hub (`frontend/src/app/hub/page.tsx` + `hub.css`), on the S2 demo data.**
  - "{site} · updated HH:MM", then **"N parcels need attention"**; "Every parcel is on track" when there are none.
  - Above the list: filter **All · Customer cases · Stalled**.
  - Search: "Find a parcel by tracking number". An open case opens it; otherwise it shows the scan count and Open
    case.
  - **One row per parcel**, from open cases first, then stalled parcels (the proof rule):
    - a pill (Lost track / Likely location / Found / Stalled N min) plus "Customer says it never arrived" when the
      case has a complaint;
    - **one bold sentence in supervisor words**, from the shared `lib/words.ts` ("Went into chute C12 at 14:11. No
      bag scan since." / "Read at the scan tunnel at 14:33. Never loaded onto the sorter.");
    - **the mini trail**: Tunnel · Sorter · Chute · Cage · Truck. Reached stages are filled, the stage that never
      came is an open ring;
    - waybill · size, or waybill · next expected scan.
  - **Row button:** "Investigate" + "about 1 min · ~US$0.30" with model keys. In no-key mode it reads "Open case"
    with the line "scan log only, no model keys", because Investigate runs the agents.
  - **Thumbnail:** the frame of a camera that watches the last scan point at that time, tagged "CAM 19 · 14:32:38".
    With no footage (the S2 store, until S2 renders) it shows **the plan zoomed on where it stopped, pinned**, rather
    than an empty box. HubPlan gained a `focus` option for this.
  - **Aside:** only stat tiles with data ("0 found today", "1 open case"; median time to find is hidden until there
    is one), "Where today's trails ended" with a 3D hub link, and the tagline.
  - One explanatory line: "A parcel shows here when its next scan is late and the next scanner kept working…", plus
    "N more are late, but the log ends too soon to tell."
- **Removed:** the old Hub's stalled table, rule paragraph, inbox-clock link and the `HubDashboard` component
  (deleted).
- **One look:** the `?style` switch is gone; v2 is the only style (owner 09:04).
- **Old UI is in git history:** commit `b957423` (local, not pushed).
- **S2 demo store:** `.local/backend-data-s2`, started with `SPOOR_DATA=s2`. Seeded by `seed_nokey.py`, which gained
  `--case-input` and `--window-s`:
  - the S2 long scan log: 884 scans, the cage membership, 282 photo-eye pulses, all labelled simulated;
  - the S2 case for **CTX711983880419**, with the question and complaint from `case_input.json`;
  - no clips until S2 renders. The 12 CAM_19 final-look frames are sparse, and their burned-in clock doesn't match
    their frame numbers, so I didn't fake a clip from them.
  - The Thursday store stays as the test store.
- **§J, no em dashes:**
  - `backend/tests/test_copy.py` fails on "—" in any non-docstring backend string;
  - `frontend/tests/e2e/copy.spec.ts` fails on "—" in the rendered text of every screen;
  - fixed: report placeholders ("not recorded", "None listed."), the report title and draft banner (now a middle
    dot), plus three journey/possible/agent wordings.
- **J6 (the builder ran my script):** Glimmer-30B on an A100-80GB flagged 4 of 12 synthetic CAM_19 frames, all
  "person carrying parcel into exception store"; GPU at most $0.23. Proof:
  `docs/open_weights_proof/2026-10-31_j6_glimmer_triage.json`.

## 2. Check these
- `frontend/review_pack/flow/desktop_01_hub.png` (1440 × 900)
- `frontend/review_pack/flow/mobile_01_hub.png` (390 wide, full page)
- Tests:
  - backend 251 ✓, including `test_copy`;
  - e2e `copy.spec` ✓;
  - typecheck and lint clean.

## 3. Notes and questions
- The S2 row says "No bag scan since", with "Cage?" open. The S2 log does record a cage add at 14:21:33, but it is
  imported as a **cage membership**, not a scan, and the journey read model shows scans only. On the Answer screen I
  plan to show memberships as moments ("Put in cage W at 14:21"). Say if the Hub row should use it too.
- The old e2e and review specs are written for the old screens on the Thursday store. As each screen is rebuilt, I'll
  replace its specs (flow specs, S2 store). Until then the old suites aren't a meaningful gate.
- Next: Investigating, then Answer.
