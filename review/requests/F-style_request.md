# F-style — Style mapping: Reelism's finish on Spoor's palette (for Rexton's OK before app-wide)

From the frontend agent, per owner_style_0136.md (+ update 02:02). Skills loaded before this UI work: `rexton-ui`,
`emil-design-eng`, `design-taste`, `impeccable`. Reelism was read only (`C:\Users\ooiru\Reelism\DESIGN.md` and its
CSS variables); nothing in it was changed.

## How to see it
- The new style is **off by default**. Open any page with `?style=v2` to turn it on; your browser remembers the choice.
  `?style=v1` turns it off.
- After your OK I make it the default and remove the switch.
- All tokens are in one file: `frontend/src/app/style-v2.css`, scoped to `:root[data-style="v2"]`.

## What comes from Reelism and what stays Spoor's
I took Reelism's **finish**, not its palette: type, weights, radius scale, doubled shadows, grain, motion curves and
control chrome. The colours are Spoor's: a calm dark-neutral base, one restrained accent, and the evidence colours.
The evidence colours carry meaning, so they stay the most saturated things on screen.

| Reelism token | Reelism value | Spoor v2 token | Spoor v2 value | Note |
|---|---|---|---|---|
| font (display + body) | Google Sans Flex Variable | `--font` | same family (OFL-1.1, `@fontsource-variable/google-sans-flex`) | one family; weight steps 560 / 620 / 680 like Reelism |
| body | 18px / 1.5, ss01 cv11 | body | 14.5px / 1.5, ss01 cv11 | a work surface, so smaller than Reelism's landing body |
| headline | 680, -0.038em | `.sp-h1` | 680, clamp(26–34px), -0.032em, balanced wrap | |
| title-sm | 640, 20px | `.sp-h2` / `.sp-h3` | 640 20px / 620 15px | |
| numeral (tnum) | 700, tabular | `.sp-num` | same family with tabular figures (was a monospace font) | times and counts don't jitter |
| dark-bg / surface / surface-2 | #0B0C10 / #14151B / #1B1D24 | `--bg` / `--surface` / `--surface-2` | same | Reelism's night sheet = Spoor's canvas |
| dark inks | #F4F5F7 / #C9CCD3 / #8B909B / #5A5F69 | `--ink-strong` / `--ink` / `--ink-muted` / `--ink-faint` | same | muted on surface ≈ 5.9:1 (AA); faint is for marks only |
| dark hairlines | 8 % / 14 % white | `--hairline` / `--hairline-strong` | same | |
| brand spectrum + gradient | blue, indigo, coral, orange, yellow | **not used** | — | too colourful for Spoor (Rexton 02:02) |
| Proof Indigo (only solid brand hue) | #818CF8 (dark) | `--accent` | **#9EA5E6** (low-chroma indigo) | one accent: primary button, focus, selected states; no evidence colour uses this hue |
| confirmed green | #5EE29A | `--ev-observed` | #4ADE80 | Spoor's evidence language, unchanged meaning |
| — | — | `--ev-hypothesis` / `--ev-unknown` / `--ev-contradicted` / `--ev-scan` | amber #FBBF24 dotted · grey #8B909B hatched · red #F87171 · **blue #60A5FA** | scan beads are now blue, per the journey design bar (they were near-white) |
| radius | 8 / 12 / 16 / 22 | `--radius-xs` / `-sm` / `--radius` / `-lg` | same | buttons 12, cards and panels 16, highlight panel 22 |
| shadows (doubled) | ambient + contact, navy | `--shadow` / `--shadow-chip` | same structure, pure black at night | |
| grain | 3.5 % at night, screen | `body::after` | 3.5 %, screen; hidden in print | felt, not seen |
| motion | ease-out (0.22,1,0.36,1), ease-in-out (0.65,0,0.35,1) | `--ease`, `--ease-inout` | same | ≤ 300 ms; press scale 0.97 at 120 ms; no ambient motion on work surfaces |
| button | 54px, radius 15, deep-stop gradient | `.sp-btn` | 40px (32px small), radius 12, solid accent + a faint top highlight | no gradient fills anywhere |
| nav link | 14px / 520, radius 10 | `.sp-nav` | 14px / 560, 44px rows, radius 10 | |
| logo | lockup | brand slot | placeholder "S" mark kept | the trail-motif logo drops into `.sp-brand-mark` |

Light theme: Reelism's light sheet would map the same way (#FFFFFF / #F6F7F9, inks #101116 → #6C717B, accent
deepened). I haven't built it: the PRD sets a dark canvas, and you asked for direction first.

## The 3 proof screens (style v2 on, real no-key data)
1. **Case workspace**: `frontend/review_pack/style_v2/desktop_workspace.png`, `mobile_workspace.png`
2. **Case summary, page 1 of every report (H14, new)**: `desktop_summary.png`, `mobile_summary.png`
   - The answer is one sentence, built only from the typed journey: "Last confirmed: sorter divert to C04 at
     14:32:31.8 MYT. Where it went next is not shown yet: the cameras watching that moment (CAM_07 and CAM_10) have
     not been analysed."
   - Status chip **Unknown**. Found and Located need a search outcome (I7) or a collapsed possible area (I4), so no
     case can show them yet.
   - 4 key frames:
     1. Last confirmed: CAM_07, the original frame at the scan time, labelled "parcel not yet identified in it";
     2. The missing moment: CAM_10 at the predicted time, with a dashed box where it should appear (approximate,
        mounting-plan pose);
     3. Where it is: an empty tile with the reason;
     4. Found: an empty tile with the reason.
   - Mini route map from the backend site plan: blue scan beads, amber dotted belt route, grey "trail ends".
   - "How sure" in plain words, next action ("Review CAM_07 and CAM_10 from 14:32:31 to 14:32:34 MYT"), open time, a
     link to the Evidence appendix, and print / save as PDF (one A4 landscape page).
3. **Hub dashboard (H15, new, top of Operator)**: `desktop_dashboard.png`, `mobile_dashboard.png`
   - KPIs: open cases, located or found, median time to locate, model cost per case. Empty values say why, never a
     fake zero.
   - Where evidence trails end: zones shaded on the plan.
   - Cameras the open cases depend on.
   - Records that disagree: scan pairs faster than the belt allows.
   - Cases table.
   - Backend: `GET /v1/sites/{id}/dashboard` (`backend/src/spoor/forensics/dashboard.py`, test added).

## Known issues
- Hard-coded colours inside the 3D scene and the 2D floor plan still use the v1 values. They move to tokens when v2
  becomes the default.
- With one default case the dashboard is sparse. It fills in when the scenario cases are seeded (F1, after renders).
- The summary's frames are the old white-floor QA renders in this no-key case. S2's final render replaces them.

## Questions for Rexton
1. Is the direction right: Reelism's finish, Spoor's calm palette, the indigo accent #9EA5E6? If yes, I make v2 the
   default app-wide.
2. Do you want a light theme too, or dark only?

## Update 02:40: Rexton's accent and logo (owner_style_0136, updates 02:05 and 02:08) applied
- **Accent = deep indigo #6366F1** (on dark); #4F46E5 is kept for light.
  - White on #6366F1 is 4.47:1, just under AA. Button fills therefore use #5558EE (5.2:1).
  - Accent text and focus rings on dark use #818CF8 (6.1:1).
  - Indigo carries no evidence meaning anywhere. The scan beads are blue #60A5FA, a different hue.
- **Logo rebuilt as exact SVG**, not traced (`frontend/scripts/build_logo.py`):
  - The symbol is one stroke weight with rounded caps, evenly spaced dots, equal hollow start nodes and filled end
    dots. Indigo on both themes.
  - The wordmark is Google Sans Flex 700 (OFL-1.1), outlined to paths.
  - Files in `frontend/public/brand/`: `spoor-logo.svg` / `spoor-logo-dark.svg`, `spoor-mark*.svg`, and a simplified
    `spoor-mark-small.svg`. `spoor-icon.svg` (indigo mark on a near-black rounded square) is also the app favicon via
    `src/app/icon.svg`.
  - In the app: the sidebar shows the full logo, and the mark alone when the rail is collapsed. The mobile top bar
    shows the logo.
  - Provenance: `assets/brand/README.md`.
  - Preview of all variants on light and dark, including 16 / 32 / 64 px icons: `frontend/.local/shots/logo.png`.
- The proof screens in `frontend/review_pack/style_v2/` were re-shot with the indigo accent and the logo.
- Not yet placed: the logo on the report header, login, video title card, README and gallery thumbnail. These come with
  the app-wide switch after your OK.
