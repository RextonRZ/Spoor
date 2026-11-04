last commit reviewed: c345a18

Reviewed demo_path2 (15:11). W1q2 re-render exists (7 W1 clips, not only the 2 asked): log its Modal actual.
Investigating (3_investigating_1440.png), strong overall. Fix:
1. Log times "12:21:38" are today's run clock beside footage times "14:32"; viewers will read them as hub time.
   Show run time as elapsed (+0:00, +0:37 ...) or label the column "run time".
2. Tracker (SAM 3.1) is dashed/greyed: SAM did not run in this live run (cached). For the showcase, the run must use
   SAM visibly: either run sam_track on the planned window (small cost) or show "used SAM 3.1 tracks from <time>"
   as a done step. Same for Muse Spark: fine (observe_clip ran).
3. Idea texts are cut mid-word ("through the en", "resolution and"); wrap or end at a sentence. Map inset labels
   cut ("Cage stagi") and "Asking a person" covers the map corner.
Answer (4_answer_1440.png):
4. Hero frame (CHK_STORE 14:32:33) shows the worker's back; the carton isn't visible or outlined. Pick the frame
   where the carton is in view with SAM's outline (e.g. 14:32:30-31 walking up past the post).
5. Journey player is a black box before play; show the first chapter's frame as the poster (c345a18 says done,
   check the screenshot was taken after load). Unloaded step still says "Several cartons handled here at once:
   no outline": apply the W1q2 quiet-door clips + handshake so it shows the outline + number.
