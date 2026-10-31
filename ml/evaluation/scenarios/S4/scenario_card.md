# S4 · Mis-load onto the wrong truck (RFID cross-read)

> EVALUATOR-ONLY. Synthetic scenario from the CONTOH Express hub (fictional). The Spoor runtime never reads this card or anything under `assets/hub/build/truth/`.

**Length:** 30.0 s at 10 fps from 2026-10-28T14:32:07+08:00 (hub clock; each camera's OSD runs on its own drifting clock).

**Subject:** `RC-169`

**What happens:** roll cage meant for D08 pushed onto the D09 lorry; the D08 portal cross-reads its tag

**Cameras rendered:** CAM_10, CAM_11, CAM_13, CAM_14, CAM_15, CAM_16, CAM_17

**Scan lines about the subject** (scan_simulated, device clocks):

- `2026-10-28T14:32:25.700+08:00` rfid_read @ SP-RFID-D09 (clkd_wcs)
- `2026-10-28T14:32:26.000+08:00` rfid_read @ SP-RFID-D08 (clkd_wcs)

**Expected Spoor answer:** the cage went into the D09 lorry (video), despite the RFID read at D08's portal: a cross-read (weaker RSSI, 0.3 s after the D09 read)

**Key truth values:**

```json
{
 "scenario": "S4",
 "seconds": 30.0,
 "t0": "2026-10-28T14:32:07+08:00",
 "story_container": "RC-169",
 "story_object": "cage_rolling_out_D08",
 "intended_door": "D08",
 "actual_door": "D09",
 "loaded_t_s": 19.3,
 "cameras": [
  "CAM_13",
  "CAM_14",
  "CAM_15",
  "CAM_16",
  "CAM_17"
 ]
}
```

Key stills: `stills/` (3 frames: before, the moment, after).
