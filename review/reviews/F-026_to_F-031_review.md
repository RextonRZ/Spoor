# F-026 … F-031 review (I4/H4, F-style-b fixes, I6/H5, I5/H11, I7/H12, I8/H7) — APPROVED WITH FIXES

Reviewed 04:45 Sat: 30b_h2 (possible area), 33_h14, 34b_h15_inbox_plus_30_min, fx_35b_h5, 36_h11, fx_37_h12,
reel sheet. Six requests in 25 min: keep this pace only while every one stays this honest. Fixtures are bannered,
"computed" is labelled, reel cards say SYNTHETIC and "inferred (not seen)". F-027 fixes landed (media settled,
chips compact, short button, one window). Good.

## P0
1. **The stalled inbox floods with false alarms.** At "+30 min after the last imported scan" every parcel in the
   60 s simulated log is "stalled" (40+ rows, all 28–30 min overdue) because the log simply ends. A real
   supervisor would ignore this screen. Rule change:
   - a parcel is **stalled** only if its next expected scan point (or the next device on its route) **kept producing
     events for other parcels after the allowance ran out** — proof the hub kept working and this parcel didn't
     show up;
   - otherwise it is **"log ended — can't judge"** (not counted, one summary line).
   - For the demo the scan log must run long enough past S2's divert (bag scans at SP-BAG-C04 etc. continue for
     other parcels). **Builder:** please produce a longer sim-only scan log for S2 (e.g. 15 min of hub traffic; no
     render needed) and say where it is. Frontend: test that S2's parcel is the only stalled row in that log.

## P1
2. **H5 wording over-claims.** "CAM_19 confirmed it in Cage + bag store" — CAM_19 only sees the doorway (Z11
   interior 4.8 %). Say "CAM_19 saw it carried **into** the exception store at …". Use "exception store" (the sign's
   name) with "(inside the cage + bag store)" once. Also align the fixture with S2 truth: the builder pushes RC-864
   to **D07**; the fixture says SP-LOAD-**D08**. Read the door from the scenario truth, don't hard-code.
3. **Search order (H12) must favour blind places and searchable places.** The list starts with "Cross-belt loop"
   (nobody searches inside a running loop) and leaves out the exception store / no-coverage corner, which is where
   a missing parcel that walked away most often is. Rank by: still-possible share × not watched by any camera ×
   reachable on foot × searchable (machines last, with "stop the line to check" wording). Show the blind store
   first when it is reachable.
4. **Camera moment grid (H11) shows only the 2 cameras with footage.** Show the cameras around the break point
   from the plan too (CAM_11, CAM_13, CAM_19 …) as quiet tiles: "no footage imported" — so the gap is visible.

## P2
5. Fixture outcome time 13:04:00 is before the event (14:32); use a time after it.
6. Reel opens with two identical title cards; one is enough.
7. Seam: check the left rail bottom again in the hub shot after F-027.

Next as you planned, then the 3D twin view (owner_ideas_0303 §1).
