# F-034 — H13 scan cards

From the frontend agent.

## 1. Changed since last request
- **When the playhead reaches one of the parcel's scans** (−0.3 s to +2.5 s), a **scan card** appears at the top of the
  CCTV hero. It reads what the scan record says:
  - "✓ Label read at the scan tunnel (line A)";
  - "CTX160258795857 · 6.7 kg · 40×30×25 cm · → chute …" (weight / dims / destination when the record has them);
  - "14:32:07.9 MYT (scanner clock, not synchronized) · source: scan record 72aec475 · scan_simulated".
- **Source is the record, not the video.** The card offers "See CAM_xx at this moment": the frame of a camera the plan
  says watches that read point, which is where the builder's stack light flashes.
- **On the plan,** the active scan bead gets a blue ring, and its time chip is shown even on small plans.
- The journey beads now carry `read_outcome` and `source_type`.

## 2. Check these
- `frontend/review_pack/{desktop,mobile}/39_h13_scan_card.png`
- `frontend/src/components/workspace/ScanCard.tsx`
- Review spec H13 ✓, typecheck ✓, lint ✓.

## 3. Known issues
- **Red no-read card:** styled (`data-ok=false`) but not reachable for a case parcel. A no-read carries no identity, so
  it is never one of the parcel's own scans. S1's REJECT no-read will appear as an unidentified event in the hub
  timeline, not as a card.
- **No stack-light frame link yet:** it waits for the builder's stack-light event times. The card links to the
  watching camera's frame at the scan time.
