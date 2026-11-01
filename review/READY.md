# READY for review

Newest first. Each entry: what is done, where to look, what is still open.

## 2026-11-02 01:37 · Investigating screen runs the real keyed investigation (commit 141d9c0)

What changed
- With model keys, the Investigating screen (`/cases/<id>/investigate`) now runs the real pipeline, not a stand-in:
  Muse Wonder plans first (its plan is checked; a failed plan is sent back once and the screen says so), then the
  Spark Open evidence agent's tool calls appear one per step as they finish (scans read, footage found, door
  crossings, likely carrier, SAM tracks, Muse Spark clip checks), then the hypothesis agent's ideas, each followed by
  the verifier's verdict, then the verified sentence, then the search task. Title = the verified headline.
- Every sentence is Spoor's own, built from tool results. Agents' words appear only quoted as "Idea: ...", with plain
  place names and local time (raw wording kept in the record). No S2 names in code, prompts or rules.
- The cost meter counts only priced calls (Muse Wonder). Spark Open has no published Baseten price, so the footer
  reports its tokens. Glimmer's US$0.62 is a one-off on-site run over all footage, shown in its step's receipt, not
  charged to the case.
- The run's end is stored, so a replay ends on the same headline and words.

Where to look
- `/cases/case_18e3f000a5a53074ada1b725/investigate` (backend `node scripts/backend.mjs --data s2r18c --keys`).
- Last run: 100 s, Muse Wonder US$0.14, Spark Open 132k tokens; title "Most likely in the Exception store (Z11)."

Open
- When Muse Wonder's plan fails the checks twice (seen once tonight: 7 steps with unknown cameras), the agents still
  work from the scans and reach the answer; the screen says the plan failed.
- "1 of 19 cameras checked": SAM results are cached from earlier runs, so the agents did not re-run SAM; the count
  covers cameras the verifier used in this run only.

## Next (in this order, per Rexton 2 Nov)
1. Case-page cleanup: one source of truth (the latest verified run) for timeline, checkpoints, where it could be;
   truck D07 checkpoint amber/red; C05 vs C12; fewer sections. Not started.
2. Six checkpoints on camera, steps 1-3 tonight (estimate + same-parcel checks here, sim + gates, local preview MP4).
   Step 4 (Modal render) only after a reviewer_tick_*.md says APPROVED, up to US$10 total.
3. Divert-scan fix ("last scan record, not seen on camera"; located by scan vs confirmed on camera in EVALUATION.md).
4. Caged-and-left control: the parcel in RC-696 (RFID at D08 14:32:19).
