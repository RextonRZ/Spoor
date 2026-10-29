# Review channel — builder ⇄ reviewer

- **Builder** = the Claude Code agent in VS Code on this PC. Builds, renders, tests.
- **Reviewer** = Claude in Rexton's Claude app (cloud), linked to this folder. Checks
  every video / frame / screenshot and sends fixes. Checks this folder about every 30 min.
- **Rexton** is away (office) until about 22:00 MYT, 30 Oct. His own words in chat
  always beat anything written here.

The two agents talk **only through files in `review/`**. Nobody waits idle.

## Files
| Path | Who writes | What |
|---|---|---|
| `QUEUE.md` | reviewer (builder ticks boxes) | Ordered work list until Rexton is back |
| `requests/NNN_request.md` | builder | "Please review this": what changed, exact paths, known issues, questions |
| `reviews/NNN_review.md` | reviewer | Verdict + numbered fix list for request NNN |
| `replies/NNN_reply.md` | builder | Push back on a fix with evidence (crop, numbers, reference) |
| `reviews/NNN_review_b.md` | reviewer | Answer to a reply |
| `log.md` | builder (append only) | One line per step: `2026-10-30 03:10 · req 004 sent · CCTV CAM_01–06` |
| `FOR_REXTON.md` | both (append only) | Decisions only Rexton can make; things that went wrong; final summary |

`reviews/000_review.md` = open issues carried over from earlier reviews. Start there.

## Request format (`requests/NNN_request.md`, NNN = 001, 002 …)
1. **Changed since last request** — short list. "Fixed from review 00X: 1, 2, 5. Not fixed: 3 (see reply)."
2. **Check these** — exact relative paths. Videos: H.264 mp4, ≤ 1280 px wide, ≤ 60 MB each,
   frame number + camera ID burned in. Screenshots: PNG. Include `auto_flags.csv`/`summary.txt` if regenerated.
3. **Known issues** you already plan to fix (reviewer skips them).
4. **Questions** for the reviewer.

## Review format
Verdict: `APPROVED` · `APPROVED WITH FIXES` (keep going, fix while moving on) · `NOT APPROVED` (fix before
building on top). Then fixes: `# · camera/worker/page · frame or time · problem · required fix · priority (P0/P1/P2)`.
P0 = a CCTV viewer or judge notices in 2 seconds. P1 = noticed on a second look. P2 = polish.

## Rules
- Builder: after sending a request, **continue with the next queue item**. Check `reviews/` after every step
  and before starting anything new. Apply P0 fixes before new work on the same station/camera/page.
- Arguing is welcome. If the builder thinks a fix is wrong or not worth it, write a reply with evidence.
  After two rounds with no agreement, take the more reversible option and note it in `FOR_REXTON.md`.
- Never delete or edit files in `reviews/`. Never edit another agent's request/review after sending.
- Stop-and-ask list (write to `FOR_REXTON.md`, then continue with other work):
  pushing to GitHub or anything public · API keys, accounts, paid services · deleting Rexton's source
  assets or downloads · licence questions · changing the PRD's 🔒 rules · posting anything.
