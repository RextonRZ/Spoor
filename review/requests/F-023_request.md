# F-023 — I1 follow-cam crop (backend)

From the frontend agent.

## 1. Changed since last request
- **`GET /v1/cases/{id}/tracks/{track}/crop?frame=`** (`backend/src/spoor/forensics/crop.py`, route in
  `api/app.py`).
  - Returns the ORIGINAL frame cut around the track's box at the nearest observed frame. The rectangle is 16:9 with a
    0.75× margin, at least 96 px tall, and clamped to the frame.
  - The crop is lossless PNG of the decoded original pixels: no resampling, no enhancement, no upscaling. A test checks
    the crop size equals the rectangle. Any zoom happens in the viewer, which labels it.
  - Response fields:
    - `media_id`, `media_sha256`, `asset_kind=original`, `frame_index`, `box_px`, `crop_rect_px`;
    - `crop_sha256` (a test checks it against the served bytes);
    - a signed `crop_url`;
    - `observed_frames`, so the follow-cam can track the playhead;
    - `identity`: the object the track is linked to, the link status / reason / who, and the scans that name that
      object. When the track is linked to nothing it says so plainly: "a tracked thing, not the parcel".
- **`GET /v1/media/{id}/frames/{n}/crop?box=x1,y1,x2,y2`.** The same crop around a requested region, for H10's "expected
  here" close-ups. It is labelled "context, not an observation", and bad boxes return 422.
- **`GET /v1/signed/crops/…`** serves the crop bytes, marked `X-Spoor-Asset-Kind: original_crop`.

## 2. Check these
- `backend/src/spoor/forensics/crop.py`
- `backend/tests/test_api.py::test_end_to_end_flow`: crop hashes, native size, identity chain, region crop, 422.
- Backend pytest 229 ✓.

## 3. Known issues
- No-key mode has no tracks, so the follow-cam (H1) shows crops only on labelled test fixtures until the S2 render +
  SAM.
