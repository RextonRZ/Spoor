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
| 0:00 | (customer chat card) | "Where is my parcel? Four days now." (the case data: last scan 28 Oct, asked 1 Nov) | A customer says their parcel never arrived. Tracking says it was loaded on a truck. |
| 0:12 | Landing, hero | scroll once | Spoor reads a hub's own cameras and scan records together. |
| 0:20 | Hub | the red live alert at the top: "A carton left the west cage bays without a scan", SAM's outline on the carton | Before anyone complained, the hub was told: a carton left a cage with no scan. It could only be one parcel. |
| 0:35 | Hub | the CTX334048419302 row: "Customer asked", "Likely location found"; the side panel | The records say it left on truck D07. The cameras say it never left. |
| 0:45 | How the agents worked (from the case header) | press Replay; the dots fill in, agent by agent | Muse Glimmer on the hub's own GPU sent only 17 % of the footage to the cloud. Muse Wonder picks the cameras. SAM 3.1 tracks who went in and out. Spark Open tests three ideas; the rules-only verifier lets one through. Each place they worked is a real camera frame. |
| 1:15 | Answer | the hero frame (carried in past the scan-in post, SAM's outline), the three facts | Most likely in the Exception store. Carried in at 14:32, not seen coming out. The truck record says D07; the cameras say it never left. No camera sees inside, and it says so. |
| 1:45 | Proof | "Watch the proof": the journey player; click the "Into chute C12" frame | Every step on its own camera. At each scan the barcode says which parcel and SAM 3.1 outlines that carton. A number goes on an outline only when no other carton could be the one scanned: every number shown was right against the truth (13 of 13). |
| 2:10 | Proof | click stop 11 on the plan | The route on the plan, numbered like the steps. Here the cage leaves through D07 without it. |
| 2:25 | Go look (Spoor Floor, the worker's phone) | Open the task, Start search, Scan barcode (type 9302) | The worker gets the frame, the parcel's photo and a walking route; scans the label; the case closes with what they found. A voice note can go in, in Malay or English. |
| 2:40 | Report | scroll the case file; "Draft the update to the customer", switch to Malay | The case file: every step's frame, the route, records against cameras. The update is written from verified facts only, each linked to its frame; a person approves it. |
| 2:55 | (closing card) | | Lost parcels, found with proof. Spoor also flags them before anyone complains. |

## If something fails on the day

- The investigation is slow or fails: the Investigating screen replays the last stored run (press Replay).
- A frame is slow to load: it is a preview of the original frame; wait a second, do not narrate a blank tile.
- Never show the Hub's Resolved tab or the control parcels on camera; they are for EVALUATION.md.
