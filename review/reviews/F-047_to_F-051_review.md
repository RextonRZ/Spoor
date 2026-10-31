# F-047 … F-051 review (Answer, Proof, Go look, Report, Cameras) — APPROVED WITH FIXES (10:40 Sat)

The flow is real now: Answer, Proof (Video | 3D hub, one transport), Go look (phone), Report and Cameras follow the
prototype's structure and words, one user, top bar. **The 3D hub (Cameras › 3D hub) is a big win**: the real Blender
hub, landmarks (Inbound docks 01–06, Sorter, Chutes, Cage staging), "Scanned 14:10:40" / "Last seen 14:11:12" pins,
compass, Reset view. Keep it.

## P0 — a false "Records disagree" is driving the whole S2 story (builder + frontend)
Answer and Report say "the sorter's own times don't fit the belt: recorded 21.7 s, but the belt route needs 25.9 s"
and "What to fix: check the sorter's tracking". That is almost certainly **our geometry, not the parcel**:
- the backend's site plan is seeded from `assets/hub/hub_spec.json` (**line A layout "a"**), while S2 is simulated
  and rendered on **layout "b"** (`hub_spec_lineAb.json`);
- in layout b the carrier load happens at the loop merge, but SP-INDUCT still sits at (12.0, 9.5) upstream of the
  tunnel in both specs, so the plan's induct → divert route is longer than the real one.
Fix: **builder** — make the layout-b spec the single source (scan point positions, conveyor paths, belt routes) or
write `hub_spec.json` for layout b; say which file is canonical. **Frontend** — seed and gen:hub from that file, then
re-run S2; the only S2 conflict must be the designed one (cage RC-864 loaded at D07 without the parcel). Add a test:
no belt-timing conflict on S2's subject with the canonical plan.

## Four-eyes question (F-050) — reviewer decision, within Rexton's "one user" rule
Keep the four-eyes rule in code, but make it a **site setting** "Require a second person to approve reports",
default ON for real sites, **OFF for the demo site**. With it OFF: no "DRAFT · not reviewer-approved" banner, "Share
report" shares the report as an investigation summary (still "decision support, not a forensic certificate"). One
line in Settings shows the setting. No silent relaxation.

## P1
1. Proof "No footage" hero is fine pre-render; once S2 renders, the default selected tile must be the most telling
   one (CAM 19 carried in), not the last scan.
2. Report thumbnails are plan crops (honest); after the render, switch to the 4 real key frames.
3. Go look: check the place list shows ONE place at a time, the most likely first ("blind corner, exception store"),
   matching the prototype.

Next: Settings › Data sources + Models (proof of spend), then the keyed S2 run once the render lands.
