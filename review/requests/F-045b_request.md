# F-045b — Hub redone to match Main.dc.html exactly; top bar; one demo user

From the frontend agent. Follows the owner's 09:22 and 09:24 orders.

## 1. Changed since last request
- **Top bar, no sidebar** (`components/Shell.tsx` + `shell.css`, values lifted from the prototype). It has:
  - the logo mark at 28 px with "Spoor" at 19/700;
  - Hub · Cases · Cameras (active `#1B1D24`, 600);
  - the centred search (max 440 px, 40 px tall). It is real: an open case opens; otherwise it shows "N scans of
    CTX… No case yet. Investigate";
  - the "Synthetic demo hub" chip;
  - the 36 px avatar.
  - The Reelism rail and all sidebar CSS are deleted.
- **One user, no account switching.**
  - Backend: `Principal` gained `also` (further roles), and `require_role` passes when any role matches; checks are
    unchanged otherwise. Test: `test_single_demo_supervisor_holds_every_role`.
  - Local: a `supervisor_01` token holding all three roles, in the git-ignored `users.json` and `.env.local`;
    `setup-local.mjs` creates it.
  - The proxy always acts as the supervisor. The per-role tokens remain only for backend RBAC tests.
  - The avatar menu shows "Hub supervisor", Settings & data, and the model status. **No role switch anywhere.**
- **Hub = Main.dc.html**: the same widths (`max-width 1376`, the `999 1 700` / `1 1 340` flex), paddings, radii
  (cards 20, tiles 16, trails card 18), type (34/700 title, 21/600 card headline, 17/600 compact, 13–14 grey), colours,
  buttons (primary `#5558EE` 44 px; outline 40 px) and copy, all in Inter (loaded via next/font).
  - The large first card, then compact cards.
  - The filter is built from the real row categories: "All 2 · Lost track 1 · Stalled 1".
  - Tiles: "found today" and "median time to find". Median is shown only when there is one; the slot then shows
    "open case", never "—".
  - Trails card: the building crop, the zones where cases end, and the top case's route, drawn quietly with no chips.
- **Removed:** the evidence-graph page (not in the flow), the old shell CSS, the old mobile drawer rules, the v2 nav
  overrides.
- **Old UI is in history:** `b957423` (local).

## 2. Check these
- **`frontend/review_pack/flow/sbs_01_hub.png`**: prototype (left) vs app (right), both at 1440 × 900.
- `frontend/review_pack/flow/desktop_01_hub.png`, `frontend/review_pack/flow/mobile_01_hub.png`
- Tests:
  - backend 251 + supervisor test ✓;
  - typecheck and lint clean.

## 3. Where real data differs from the prototype (asking, not redesigning)
1. **Thumbnails:** the S2 store has no footage until S2 renders, so each thumbnail is the plan crop pinned where the
   parcel stopped, tagged "Where it stopped · 14:11". Once clips exist, the same slot shows the camera frame tagged
   "CAM 19 · 14:32:38", as in the prototype. OK as the no-footage state?
2. **Primary card pill:** the prototype says "Records disagree" plus "Customer called 2 days ago · COD RM 189". Real
   S2 data has no records-vs-video conflict yet (that needs the keyed run), so the pill is "Lost track". The context
   reads "Customer says it never arrived · case opened today"; there is no COD value in the data.
3. **Investigate caption:** "about 1 min · ~US$0.30" with keys; "Shows what the scan log knows" without (F-045 #2).
4. **Mobile:** the prototype has no phone layout for the Hub. The bar wraps search to a second row, and cards stack.

## 4. Next
The Investigating screen: backend typed run steps are in place (`POST /v1/cases/{id}/run` streams `run_step`
events, `GET /v1/cases/{id}/run` replays them). Then Answer, Proof, Go look, Report, Cameras, each with a
side-by-side shot.
