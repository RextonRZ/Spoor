# S3 · Phantom containment

> EVALUATOR-ONLY. Synthetic scenario from the CONTOH Express hub (fictional). The Spoor runtime never reads this card or anything under `assets/hub/build/truth/`.

**Length:** 30.0 s at 10 fps from 2026-10-28T14:32:07+08:00 (hub clock; each camera's OSD runs on its own drifting clock).

**Subject:** `CTX765044089872`

**What happens:** scanned INTO the C04 bag (handheld container_add), then set down on the floor against the front of the C04 frame and left there

**Cameras rendered:** CAM_09, CAM_10, CAM_11, CAM_13, CAM_14, CAM_15, CAM_16

**Scan lines about the subject** (scan_simulated, device clocks):

- `2026-10-28T14:25:27.340+08:00` tunnel_read @ SP-TUNNEL (clkd_wcs)
- `2026-10-28T14:25:37.440+08:00` induct_to_carrier @ SP-INDUCT (clkd_wcs)
- `2026-10-28T14:25:54.140+08:00` divert_confirm @ SP-DIV-C04 (clkd_wcs)
- `2026-10-28T14:32:11.760+08:00` container_add @ SP-BAG-C04 (clkd_handheld)

**Expected Spoor answer:** the scan says it is in BAG-C04-6915, but the video shows it set down beside the C04 bag frame at t~9 s and still there at the end: physical location = floor beside chute C04, not in the bag

**Key truth values:**

```json
{
 "scenario": "S3",
 "seconds": 30.0,
 "t0": "2026-10-28T14:32:07+08:00",
 "story_parcel": "CTX765044089872",
 "story_object": "flow_parcel_5013",
 "bag_id": "BAG-C04-6915",
 "scanned_t_s": 6.76,
 "set_down_t_s": 9.16,
 "set_down_at": [
  43.95,
  21.56,
  0.0
 ],
 "cameras": [
  "CAM_10",
  "CAM_11",
  "CAM_13",
  "CAM_14"
 ]
}
```

Key stills: `stills/` (3 frames: before, the moment, after).
