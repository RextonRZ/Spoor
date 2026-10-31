# S0 · Control path

> EVALUATOR-ONLY. Synthetic scenario from the CONTOH Express hub (fictional). The Spoor runtime never reads this card or anything under `assets/hub/build/truth/`.

**Length:** 30.0 s at 10 fps from 2026-10-28T14:32:07+08:00 (hub clock; each camera's OSD runs on its own drifting clock).

**Subject:** `CTX260172023384`

**What happens:** normal path: tunnel -> merge -> loop -> divert -> chute -> bag

**Cameras rendered:** CAM_01, CAM_02, CAM_03, CAM_04, CAM_05, CAM_06, CAM_07, CAM_08, CAM_09, CAM_10, CAM_11, CAM_12, CAM_13, CAM_14, CAM_15, CAM_16, CAM_18

**Scan lines about the subject** (scan_simulated, device clocks):

- `2026-10-28T14:32:11.400+08:00` tunnel_read @ SP-TUNNEL (clkd_wcs)
- `2026-10-28T14:32:16.400+08:00` induct_to_carrier @ SP-INDUCT (clkd_wcs)
- `2026-10-28T14:32:33.400+08:00` divert_confirm @ SP-DIV-C01 (clkd_wcs)

**Expected Spoor answer:** last seen dropping into the bag at chute C01 (t~28 s)

**Key truth values:**

```json
{
 "scenario": "S0",
 "seconds": 30.0,
 "t0": "2026-10-28T14:32:07+08:00",
 "story_parcel": "CTX260172023384",
 "story_object": "flow_parcel_141",
 "chute": "C01",
 "tunnel_read_t_s": 4.4,
 "in_bag_t_s": 27.89
}
```

Key stills: `stills/` (3 frames: before, the moment, after).
