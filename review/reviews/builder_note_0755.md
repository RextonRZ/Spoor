# Builder note (07:55 Sat) — S2 long scan log

`events_scan_simulated_S2_long.jsonl` traffic runs 14:28 → 14:34:50, ~74 s past the window. For the stalled inbox
to prove "the hub kept working and this parcel didn't show up", the next scan points on S2's route (bag scan at
SP-BAG-C04 / bagging, cage scans, loads) must keep scanning other parcels for **at least 12 min after S2's C04
divert**. Size the stations' supply for that (sim-only, no render) and say the end time in 021d. Everything else
in the log check is good (430/431 sorter events identical in the window).
