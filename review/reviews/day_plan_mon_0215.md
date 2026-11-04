# Day plan, Mon 2 Nov (Rexton out ~09:30-19:00). Work through this in order without waiting for him.
Rules for the whole day: before each step read the newest review/reviews/reviewer_tick_*.md and follow it; commit
after every step that works; one log line per commit with the real time (`date`); write review/READY.md after each
step with what to look at. Stop and wait ONLY if: spend would pass US$12 on Modal (or any single run > US$10),
the keyed S2 answer stops being "most likely in the Exception store", or tests fail and you can't fix them.
No S2 hardcoding; plain words; no em dashes; fictional brands; parcels not people.

A. Finish six_checkpoints_on_camera_0915.md (render -> ingest + clock fits -> handshake + follow -> passport + live
   alert -> keyed re-run -> screens + landing), build order from reviewer_tick_0147.md. Time box: done by 13:00.
   If a close-up is still glitchy at 13:00, drop it (cage close-up first) and move on.
B. Divert-scan fix (general): when a divert/bag scan is the last record and no camera contradicts it, answer
   "last scanned into chute X, not seen on camera" and plan the chute camera. Then re-run ALL control parcels incl.
   a parcel in RC-696 (RFID D08 14:32:19). EVALUATION.md: count "located by scan" and "confirmed on camera"
   separately; the live alert must not fire on any control. Time box 1.5 h.
C. "Customer asked" flow (meta_stack_and_complaint_2300.md section 2): Hub chip, Customer box (complaint, days
   waited), "Send update to customer" on Report (drafted from verified findings only, human approves, nothing sent).
   Simulated fictional marketplace. Time box 2 h.
D. Consistency pass on EVERY page (Landing, Hub, Investigating, Answer, Proof, Go look, Report, Cameras, Settings)
   at 1440x900 and 390 wide: one source of truth, no "No footage"/"Not checked yet" where the run checked it,
   no internal IDs or UTC times, camera counts = 19 wide + 6 checkpoint CCTV + 1 tunnel label camera, Glimmer
   either run on the new clips (<= US$0.30) or worded "19 wide cameras swept". Save screenshots to
   review/shots/mon/ and list problems fixed. Time box 2 h.
E. Numbers for the video and README (from real runs only): time to answer vs manual review (hours of footage a
   person would scroll), cost per case (sum of the run's actual costs), Glimmer % footage skipped, keyed runs N/N,
   controls table, calibration and clock-fit accuracy. Put them in EVALUATION.md and a short "Numbers" section.
F. Docs: README (what Spoor is, how it works diagram: on-site Glimmer + cloud models + inputs WMS scan log / VMS
   CCTV export / floor plan; Meta models table; real vs simulated labels; how to run), LIMITATIONS (synthetic
   footage, simulated scans/RFID, line B idle, S2 rendered only, S0-S5 designed and how the handshake covers each),
   DEMO_SCRIPT rewritten for the new flow (customer hook -> hub alert -> investigating -> checkpoints on camera ->
   answer -> live alert -> go look -> customer update). Fix the wrong weekdays (deadline is THU 5 Nov 10:00 MYT).
G. Video prep (no narration): record clean screen captures of the full demo flow with Playwright (1920x1080, fresh
   backend/frontend start), one MP4 per scene in review/video/, matching DEMO_SCRIPT; plus 3 candidate thumbnails
   (circled carton + "RFID says it left. It never did."). Rexton narrates and edits Wed.
H. Only if A-G are done: real-footage check (one MEVA CC BY 4.0 clip, credited, faces blurred, SAM + door check
   only, max 2 h), else skip.
By 19:00 Rexton expects: A-F done and committed, G started or done, a short summary at the top of READY.md
("Today: done / dropped / open / decisions for Rexton").
