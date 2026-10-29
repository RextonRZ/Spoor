# Step 02 — Media ingest & provenance (M1)

**PRD:** §7.1, §7.3, §8.3, §12 · **Depends on:** 01 · **Location:** `services/workers/ingest`

## Goal

Accept an authorized video, store the original bytes untouched, hash it, read its timing metadata, and produce
working derivatives that each point back to their parent.

## Build

1. **Upload intake:** requires an authorization record (uploader, rights statement, purpose, retention period) —
   reject without it 🔒.
2. **Store original** in a content-addressed private dir (`data/originals/<sha256>`), read-only after write.
3. **SHA-256** of the original; derivatives get their own hash + `parent_media_id`, method, tool version, time.
4. **Probe with ffprobe:** codec, duration, fps (incl. variable fps), time base, resolution, rotation, per-frame
   PTS, creation time if present. Flag: missing/non-monotonic PTS, rotation, VFR, suspicious creation time.
5. **Derivatives (FFmpeg):** MP4/H.264 working proxy (Meta only lists `video/mp4`), low-res proxy, keyframe JPEGs
   with `frame_index` + `pts_ms`, optional clip windows. **Audio stripped by default** (§12).
6. **Frame retrieval:** `get_frame(media_id, pts_ms | frame_index)` → image + `FrameRef`. This backs every citation.
7. **Inference cache key** helper: `(source_sha256, model_id, prompt_version, settings, clip_window)` (§12, §32.1).
8. **Filename/metadata are data, not instructions** 🔒: store raw, never pass unescaped into prompts (§7.4, C10).

## Done when

- Tests: re-ingesting the same file yields same hash and no duplicate; original bytes are byte-identical after
  derivative generation; corrupted file rejected; rotation and VFR fixtures flagged.
- `get_frame` returns the same pixels for the same `FrameRef` every time.

## Status — done (2026-10-27)

Code: `backend/src/spoor/ingest/`. Tests: `backend/tests/test_ingest.py` (synthetic ffmpeg clips).

- Originals are content-addressed (`data/originals/<sha[:2]>/<sha>`) and set read-only; `media_id = media_<sha[:20]>`
  so re-ingest is idempotent.
- Proxy: H.264/yuv420p MP4, audio dropped, rotation applied, timestamps passed through. Ingest **fails** if the
  proxy's frame count or timestamps (>1 ms) differ from the original, so frame `i` means the same instant in both.
- Flags: `rotated`, `frame_gap`, `variable_frame_rate`, `missing_pts`, `duplicate_pts`, `non_monotonic_dts`,
  `audio_present_not_analyzed`, `creation_time_in_future`.
- `extract_frame` decodes from the original and is tested to equal frame `i` of a full sequential decode, including
  next to a timestamp gap (this test caught a real off-by-3-frames bug during development).
- Not yet: signed URLs (step 09), persistence of `MediaAsset` records in the DB (step 04 — JSON manifests for now).
