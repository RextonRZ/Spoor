# 3-minute demo script

Parcel CTX334048419302 on the fictional CONTOH Express hub (synthetic footage, simulated scan log). Every number on
screen comes from a real run; never narrate a result that is not on screen. Browser 1440x900, 100 % zoom. Deadline for
the submission: Thu 5 Nov 2026, 10:00 MYT.

## Before recording (not on camera)

1. Restart the backend fresh, even if it is already up: `cd frontend && npm run backend:keys` (keys in `backend/.env`:
   Meta Model API, Baseten) and `npm run dev`. After a long day of jobs the case page once took ~20 s per call (0.07 s
   after a restart); the cause was not reproduced (page traffic and reel builds stay at ~0.1 s), so restart anyway.
2. Check it: `curl -s localhost:8000/healthz` must say `"status": "ok"` with `store_read_ms` well under 1000 and
   `"jobs_busy": 0`. No background jobs running (handshakes, watches): the investigation in step 3 is the only job.
3. Open the Hub once so the frames are cached.

## The script

| Time | Screen | Click / show | Say |
|---|---|---|---|
| 0:00 | (customer chat card) | "Where is my parcel? Two weeks now." | A customer says their parcel never arrived. Tracking says it was loaded on a truck. |
| 0:12 | Landing, hero | scroll once | Spoor reads a hub's own cameras and scan records together. |
| 0:20 | Hub | the red live alert at the top: "A carton left the west cage bays without a scan", SAM's outline on the carton | Before anyone complained, the hub was told: a carton left a cage with no scan. It could only be one parcel. |
| 0:35 | Hub | the CTX334048419302 row: "Customer asked", "Likely location found"; the side panel | The records say it left on truck D07. The cameras say it never left. |
| 0:45 | Investigating | press Replay | Muse Glimmer on the hub's own GPU flagged 17 % of the footage. Muse Wonder plans: the doorway camera, then the store's close-up. Spark Open agents run the checks; the verifier passes one idea and rejects the others. |
| 1:15 | Answer | the hero clip (carried in past the scan-in post), the five moments, the plan | Most likely in the Exception store. Carried in at 14:32:32, the carrier came out without it, nobody carried it out. No camera sees inside, and it says so. |
| 1:45 | Answer | "Its journey on camera": click "Into chute C12" | At every scan, the barcode says which parcel and SAM 3.1 outlines that carton. A number goes on an outline only when no other carton could be the one scanned: 51 of 51 right against the truth. |
| 2:10 | Proof | the checkpoint tiles, then the dock tile | Each checkpoint on camera, in order. Here the cage leaves through D07 without it. |
| 2:25 | Go look | the search task on the phone | A person checks the store; the case closes with what they find. |
| 2:40 | Report | "Draft the update to the customer" | The update is written from the verified answer only. A person approves it; Spoor sends nothing. |
| 2:55 | (closing card) | | Lost parcels, found with proof. Spoor also flags them before anyone complains. |

## If something fails on the day

- The investigation is slow or fails: the Investigating screen replays the last stored run (press Replay).
- A frame is slow to load: it is a preview of the original frame; wait a second, do not narrate a blank tile.
- Never show the Hub's Resolved tab or the control parcels on camera; they are for EVALUATION.md.
