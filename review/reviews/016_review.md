# 016 review — M4 part 1: line A, 4 inductors on own 45° induct belts (front frames 1–300 every 5th, I2 dense
# f90–f109 every frame, CCTV f100)

**Verdict: APPROVED WITH FIXES.** From CAM_01 this now reads as a real induction line: 4 different people, each at
their own station, out of phase (at f100: I1 holding a white carton, I2 carrying, I3 setting down, I4 reaching),
mixed carton sizes/colours with labels, cartons merging onto belt A with gaps. No overlap (min 0.40 m), no spins.

Fixes:
1. P1 Palms-up empty hands after the release (banned pose): I2 f104–f109 — right arm stays stretched toward the belt
   with the palm open and up for ~0.5 s after letting go. Same follow-through visible on I4 around f86 and I1 f91.
   After the push: hands come back toward the body within 0.3 s, palms turn down/in, fingers relax. Check every
   release on all 4.
2. P1 I4 head over the carton at the set-down (f100 front, f106): head within a few cm of the carton top — the 38°
   cap is on the trunk, but the neck still drops. Cap neck+head flexion so the eyes stay ≥ 25 cm above the carton.
3. P1 Hands vs carton while carrying (I2 f97–f103): the palms sit at the top corners and the carton hangs slightly
   below between them. Grip lower on the side faces (mid-height), or tilt the carton into the hands; and the
   "carton follows the reached hand" safety net must never let a carton float off a hand — add a QA row for
   carton-to-palm distance on BOTH hands (> 1 cm on either = flag).
4. P1 Collisions: 32 frames > 1 cm (fingers 1.1–4.1 cm, forearm 1.9–2.6 cm, I2 chest 1.2–1.4 cm, I1 hand on the end
   stop). Blocker for M5 as agreed.
5. P2 Cycle 3.1–4.4 s: real manual induction is ~1.8–3 s, but labelled-facing work at 3–3.5 s is believable. Add the
   hold-back stop ~0.3 m before the end so the next carton is waiting when the hands come back; target 2.8–3.4 s.
6. P2 One woman on line A once the per-avatar palm offset is fixed (agreed), flat shoes.

## M5 status reply (23–34 h): accepted as honest. My recommendation is in FOR_REXTON.md (owner decision):
scope S2 first (pitch core) — line A + D05 docks on mocap in S2, gates clean, render S2 at full quality; the other
stations keep procedural motion only if they pass every gate and sit outside the pitch camera's main view, then
upgrade them in order line B → bagger → cage → opener/tech while S2 renders.
