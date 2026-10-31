# S2 · Removal into the blind spot

> EVALUATOR-ONLY. Synthetic scenario from the CONTOH Express hub (fictional). The Spoor runtime never reads this card or anything under `assets/hub/build/truth/`.

**Length:** 90.0 s at 10 fps from 2026-10-28T14:32:07+08:00 (hub clock; each camera's OSD runs on its own drifting clock).

**Subject:** `CTX468083768412`

**What happens:** taken off cage S11's shelf by a person, carried into the exception store (BLIND_NW) and left there: he came back out empty-handed

**Cameras rendered:** CAM_01, CAM_06, CAM_09, CAM_11, CAM_13, CAM_15, CAM_19

**Scan lines about the subject** (scan_simulated, device clocks):

- `2026-10-28T14:10:40.690+08:00` tunnel_read @ SP-TUNNEL (clkd_wcs)
- `2026-10-28T14:10:50.490+08:00` induct_to_carrier @ SP-INDUCT (clkd_wcs)
- `2026-10-28T14:11:12.190+08:00` divert_confirm @ SP-DIV-C12 (clkd_wcs)
- `2026-10-28T14:21:33.600+08:00` container_add @ SP-CAGE-W (clkd_handheld)

**Expected Spoor answer:** went into Z11 carrying it at ~14:32:30 (t=24 s) through its only entrance; came out empty-handed at ~14:32:48 (t=42 s); no camera sees inside Z11 but every way out is watched (CAM_19) and nothing came out with it before the window ended -> the parcel is in Z11. Neutral: moved by a person into the exception store; the cage scan (container_add) is out of date after t=6.0 s, so the cage's RFID read at D07 (t=79 s) does not mean the parcel left on that truck

**One line:** Went in carrying it, came out empty-handed: it is in the exception store (Z11).

**Must not:**

- say 'left the hub'
- say 'left on the D07 truck' (the cage's RFID read)
- say 'stolen' or name / describe a person beyond a token
- trust the cage scan after t=6.0 s

**Known limitations of the coverage:**

- unseen: a 0.25 m strip behind the south rack's end upright (x 13.45-13.55, z >= 0.7 m), reachable only through the gap's fully seen south face (review 019 #3)
- a throw over the 3 m racks: 49 % of the air over them and 83 % of the floor band where it would land are seen (review 019 #4); not a way out for a person

**Key truth values:**

```json
{
 "scenario": "S2",
 "seconds": 90.0,
 "t0": "2026-10-28T14:32:07+08:00",
 "story_parcel": "CTX468083768412",
 "story_object": "flow_parcel_5013",
 "picked_t_s": 6.0,
 "enters_blind_t_s": 23.7,
 "placed_t_s": 32.6,
 "exits_empty_t_s": 41.7,
 "final_location": {
  "zone": "Z11",
  "where": "exception store shelving (unseen by every camera)",
  "xyz": [
   10.5,
   34.01,
   1.145
  ]
 },
 "cage_id": "RC-760",
 "person": "worker_s2_1",
 "cage_push": {
  "grab_t": 60.300000000000004,
  "at_door_t": 79.0,
  "door": "D07",
  "where": [
   29.06,
   38.28,
   0.0
  ]
 },
 "cameras": [
  "CAM_13",
  "CAM_19",
  "CAM_01",
  "CAM_06"
 ],
 "lookalike": [
  {
   "parcel_id": "CTX181432283202",
   "object": "flow_parcel_5014",
   "what": "same size kraft carton with a white label, another customer's parcel",
   "scans": [
    {
     "event": "tunnel_read",
     "t_s": 4.7,
     "scan_point": "SP-TUNNEL"
    },
    {
     "event": "induct_to_carrier",
     "t_s": 10.1,
     "scan_point": "SP-INDUCT"
    },
    {
     "event": "divert_confirm",
     "t_s": 33.0,
     "scan_point": "SP-DIV-C08"
    }
   ],
   "why_not_the_subject": "while it rides line A / the tunnel / the sorter the story carton is in a person's hands by cage S11 or in Z11: it would have had to cross the hub in seconds; and its label reads another waybill at the tunnel"
  }
 ],
 "exits_covered": true,
 "exits": [
  {
   "exit": "entrance gap x 13.4-15.2, y 33.0-33.6 (the only walk-in)",
   "watched_by": [
    "CAM_19",
    "CAM_01",
    "CAM_06"
   ],
   "seen_fraction": {
    "south_face": 1.0,
    "person_column": 1.0
   },
   "note": "CAM_19 sees all of the gap's south face; unseen only a 0.25 m strip behind the south rack's end upright above 0.6 m, reachable only through that face"
  },
  {
   "exit": "over the 3 m racks (a throw, not a way out for a person)",
   "watched_by": [
    "CAM_19"
   ],
   "seen_fraction": {
    "air_over_racks": 0.49,
    "landing_band": 0.83
   },
   "note": "CAM_19 (yaw 65, tilt 30) sees 49 % of the air 0.3 m over the racks; 83 % of the 1.5 m floor band where a thrown parcel would land outside the racks is seen"
  }
 ]
}
```

Key stills: `stills/` (3 frames: before, the moment, after).

**Hub load:** two induction lines (A: 4 inductors off the dock-fed queue; B: 3 inductors off gaylords). The sorter loop runs at about 27-32 % carrier occupancy - a believable mid-shift load (review 013: accepted; the earlier 30-35 % target was not sourced).
