# F-031 — I8 evidence reel (backend) + H7 export button (frontend)

From the frontend agent.

## 1. Changed since last request

### I8 — `POST /v1/cases/{id}/reel` → MP4 + manifest, download via `GET /v1/signed/reels/{id}` (signed, short TTL)
`backend/src/spoor/forensics/reel.py`, rendered with OpenCV cards + ffmpeg (H.264, 1280×720).

- **Cards, in time order:**
  - **seen:** the original pixels around the confirmed box (I1 crop rectangle), scaled to fit and never enhanced, with
    a green frame;
  - **scan:** the original frame of a camera the plan says watches that read point, at the scan time. Blue frame,
    labelled "context frame, the parcel is not identified in it". When no camera with footage watches it, a card says
    so;
  - **inferred:** an amber card "Inferred along the belt (not seen)" with the belt route, belt time and recorded gap;
  - **gap:** a grey card "No camera 14:32:31.8 → 14:32:47.0 · unknown · never bridged".
- **Burned into every card:** time (MYT), camera, source SHA-256 prefix, and **SYNTHETIC**. A title card carries the
  colour key.
- **Manifest:** every source with its media id, frame index, full SHA-256 and crop rectangle, plus the card count and
  length.
- **Test:** a scan + gap journey gives 3 cards in order, the context-frame source listed with its hash, and the MP4 and
  manifest written (skipped without ffmpeg).

### H7 — "Export evidence reel (MP4)" in the summary's Evidence appendix card
- Builds the reel and plays it inline.
- Shows "N cards · S s · K source frames, each with its SHA-256 in the manifest", plus a download link.

## 2. Check these
- `frontend/review_pack/reel/evidence_reel_default_case.mp4`: **real reel of the default no-key case**.
  - 7 cards, 14 s: title → tunnel scan (no camera watches it) → belt inference 4.66 s vs 4.7 s → CAM_01 context frame
    at the carrier assignment → belt inference 19.23 s vs 19.2 s → CAM_10 context frame at the divert → grey gap card.
- `frontend/review_pack/reel/evidence_reel_sheet.png`: contact sheet.
- `backend/src/spoor/forensics/reel.py`, `frontend/src/components/ReelExport.tsx`
- Tests: backend forensics 19 ✓; frontend typecheck ✓, lint ✓.

## 3. Known issues
- No-key mode has no seen cards (no tracks). S2 + SAM fills them with real follow-cam crops.
- Reels are written under the backend data dir (`reels/`) and are not cleaned up automatically yet. They are small:
  ~0.2 MB each.

## 4. Next
- H6 plan-built 3D
- H13 scan cards
- H3 polish
- the 3D twin (owner_ideas §1) after the S2 render
