# S5 · Look-alike pair

> EVALUATOR-ONLY. Synthetic scenario from the CONTOH Express hub (fictional). The Spoor runtime never reads this card or anything under `assets/hub/build/truth/`.

**Length:** 15.0 s at 10 fps from 2026-10-28T14:32:07+08:00 (hub clock; each camera's OSD runs on its own drifting clock).

**Subject:** `CTX409459446096`

**What happens:** two look-alike blue mailers (same size, colour); only the labels differ

**Cameras rendered:** CAM_01, CAM_04, CAM_05, CAM_06, CAM_07, CAM_09, CAM_10, CAM_11

**Scan lines about the subject** (scan_simulated, device clocks):

- none (no scanner saw it in or before the window)

**Expected Spoor answer:** CTX409459446096 -> chute C12 (not C03): follow the tunnel read and the carrier, not the appearance

**Key truth values:**

```json
{
 "scenario": "S5",
 "seconds": 15.0,
 "t0": "2026-10-28T14:32:07+08:00",
 "pair": [
  {
   "parcel_id": "CTX409459446096",
   "object": "flow_parcel_5013",
   "chute": "C12",
   "tunnel_read_t_s": null,
   "divert_t_s": null,
   "in_bag_t_s": null
  },
  {
   "parcel_id": null,
   "object": null,
   "chute": "C03",
   "tunnel_read_t_s": null,
   "divert_t_s": null,
   "in_bag_t_s": null
  }
 ],
 "story_parcel": "CTX409459446096",
 "cameras": [
  "CAM_04",
  "CAM_05",
  "CAM_06",
  "CAM_07",
  "CAM_09",
  "CAM_11"
 ]
}
```

Key stills: `stills/` (3 frames: before, the moment, after).
