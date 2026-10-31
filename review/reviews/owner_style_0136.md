# OWNER 01:35 Sat (Rexton): frontend must use his design skills + the Reelism style

1. **Skills** — load them (Skill tool / slash command) before EVERY UI task and follow them: `rexton-ui`, `emilkowalski`
   (as installed — Rexton wrote "emilokoski"; use the exact installed name), `impeccable`, `taste`. If one is not
   found, say which in FOR_REXTON.md and continue with the others.
2. **Reelism style** — Rexton's own product at `C:\Users\ooiru\Reelism\` (read-only; never edit it). Read its frontend
   design tokens (colours, type scale, radius, shadows, motion timings, components, layout rhythm) and screenshots if any.
   Spoor gets the same design DNA and finish, but stays its own product: keep Spoor's evidence colour language
   (green observed / amber inferred / grey gap / red conflict / blue scan) and honesty labels; WCAG AA contrast.
3. **First deliverable (before restyling everything):** `F-style_request.md` with a one-page style mapping
   (Reelism token → Spoor token), and 3 restyled screens as proof (case workspace, the new case summary page H14, the
   hub dashboard H15) at 1440×900 + 390×844. Rexton approves the direction; then apply app-wide.
4. Same rules: frontend/ lane only, no keys, no pushes.

## Update 02:02 (Rexton): Reelism's main brand colours are too colourful for Spoor
Take Reelism's FINISH (spacing, type scale, radius, shadows, motion timing, component quality), NOT its palette.
Spoor palette: calm dark-neutral base, ONE restrained brand accent, plus the evidence colours (green observed / amber
inferred / grey gap / red conflict / blue scan) which carry meaning and must stay the most saturated things on screen.
Logo is being designed separately (trail motif) — leave a placeholder wordmark slot.

## Update 02:05 (Rexton): brand accent = deep indigo (#4F46E5 light / #6366F1 on dark)
Not teal (it reads as the "observed" green). Logo direction: monochrome trail (solid line → dots → end dot), only the end dot in indigo. Indigo must not be used for any evidence meaning.

## Update 02:08 (Rexton): LOGO CHOSEN — assets/brand/logo_concept_chatgpt.png (ChatGPT concept 1)
An "S" built from the evidence trail: solid segments, dotted gaps, hollow nodes, ending in a filled dot; indigo symbol,
near-black (white on dark) geometric wordmark. Rebuild it as clean SVG — do NOT trace the raster (dots/weights are uneven):
1. `frontend/public/brand/spoor-logo.svg` (symbol + wordmark, light) and `spoor-logo-dark.svg`; exact geometry: one stroke
   weight, perfectly even dot size/spacing, same node size, rounded caps; wordmark in a real font (check licence; e.g.
   a geometric sans like Satoshi/General Sans/Inter Display — pick one that matches the bold geometric look).
2. `spoor-mark.svg` (symbol only) and a SIMPLIFIED small mark for ≤ 32 px / favicon: the S path with fewer dots and one
   end dot — the full symbol turns to mush at 16 px. Favicon + app icon (indigo mark on near-black rounded square).
3. Colours: symbol #4F46E5 (light) / #6366F1 (dark), wordmark #0E1116 / #FFFFFF.
4. Use: app header, login, report header (small), case summary page, video title card, README, gallery thumbnail.
5. Provenance note in assets/brand/README.md: concept generated with ChatGPT (image), rebuilt by hand as SVG.
