# Builder note (04:45 Sat)

1. Good catch on the cage rule: the old checker hid real hits (hands, moving cage surfaces, cage children, a
   15 mm carton-in-shelf). Keep the new rule; show old vs new counts in 021c as planned.
2. **Request from the frontend review (F-026…F-031 P0 #1):** the stalled-parcel inbox needs a **longer sim-only
   scan log for S2** — about 15 min of hub traffic around S2's window, with bag scans / cage scans / loads for other
   parcels continuing after S2's C04 divert. No render needed. Same seed and clock domains as the S2 scenario.
   Put it next to the S2 scenario files and name the path in your next request. Do it after 021c, before the render.
