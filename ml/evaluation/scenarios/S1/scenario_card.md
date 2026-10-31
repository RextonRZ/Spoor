# S1 · No-read rework

> EVALUATOR-ONLY. Synthetic scenario from the CONTOH Express hub (fictional). The Spoor runtime never reads this card or anything under `assets/hub/build/truth/`.

**Length:** 90.0 s at 10 fps from 2026-10-28T14:32:07+08:00 (hub clock; each camera's OSD runs on its own drifting clock).

**Subject:** `CTX260172023384`

**What happens:** tunnel no-read -> REJECT chute -> rework bin -> exception bench (manual encode) -> carried back to the induction feed -> inducted again, read, sorted

**Cameras rendered:** CAM_01, CAM_04, CAM_05, CAM_06, CAM_07, CAM_08, CAM_09, CAM_10, CAM_11, CAM_12

**Scan lines about the subject** (scan_simulated, device clocks):

- `2026-10-28T14:33:03.000+08:00` manual_encoded @ SP-REWORK (clkd_handheld)

**Expected Spoor answer:** first pass: no read at the tunnel, reject bin at t~38 s; reworked at the bench (manual_encoded at t~58 s); re-inducted from the feed at t~90 s

**Key truth values:**

```json
{
 "scenario": "S1",
 "seconds": 90.0,
 "t0": "2026-10-28T14:32:07+08:00",
 "story_parcel": "CTX260172023384",
 "story_object": "flow_parcel_141",
 "times_s": {
  "land": 37.62,
  "notice": 41.9,
  "walk_bin": 42.4,
  "at_bin": 45.65,
  "reach": 45.95,
  "grip": 47.15,
  "lift": 47.4,
  "walk_bench": 48.4,
  "at_bench": 51.8,
  "put_bench": 52.7,
  "read": 53.2,
  "key": 55.4,
  "encoded": 58.0,
  "pick_bench": 58.6,
  "walk_feed": 59.6,
  "at_feed": 88.9,
  "put_feed": 89.8,
  "done": 90.6
 },
 "cameras": [
  "CAM_04",
  "CAM_05",
  "CAM_06",
  "CAM_07",
  "CAM_08",
  "CAM_09",
  "CAM_12",
  "CAM_10",
  "CAM_11"
 ]
}
```

Key stills: `stills/` (3 frames: before, the moment, after).
