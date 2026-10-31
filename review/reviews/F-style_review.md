# F-style review — v2 style + 3 proof screens — APPROVED WITH FIXES (direction yes; screens not at the bar yet)

Reviewed 03:10 Sat from `frontend/review_pack/style_v2/desktop_*.png` (+ mobile summary).
Read together with `floorplan_design_0300.md` (Rexton 02:53–02:59: "UI still needs to improve a lot";
he wants Reelism-level polish on 3 pages: hub dashboard, case journey, case report/share).

Good, keep: tokens in one file; Reelism finish without its palette; one indigo accent; evidence colours the
only saturated things; honesty everywhere (synthetic/simulated chips, "not analysed yet", no fake zeros,
eval headline marked "control flow (fallback)"). H14 sentence built only from the typed journey — exactly right.

Make v2 the default? **Rexton's call** — I've asked him. Keep the switch until he answers. Light theme: not now.

## Hub dashboard (H15)
1. **P1 Make it its own home page.** Today it sits inside "Operator · Inputs and inspection" above import forms,
   camera tables and eval (page is 4,300 px tall). Dashboard = first screen ("Hub" in nav). Imports, cameras/clocks,
   footage, eval move to Operator tabs.
2. **P1 Exceptions inbox + search** per floorplan_design_0300 §3 (stalled-scan rule, list with age, tracking-number
   search at the top).
3. **P1 Map** in the new floor-plan language (refs/floorplan_reference.png); trail ends shown as zone tint + count,
   with zone names, not "Z06 …" text under an empty map.
4. **P2 KPIs:** "none" as a big numeral reads broken. Use an em dash and the reason underneath.

## Case journey workspace
5. **P1 Proof shot shows "Loading 3D scene" and skeleton bars.** Re-shoot after load. If 3D is slow, show a poster
   frame of the hub while it loads.
6. **P1 Same answer, same words, on every screen.** Workspace says "Observed: fixed scanner read ·
   site_contoh_hub/zone_Z06 · site_contoh_hub/zone_Z06" and "Next evidence: No suggestion: no last read point";
   the summary says "sorter divert to C04" and "Review CAM_07 and CAM_10 14:32:31–34". Both must come from the same
   journey/next-action fields. No raw ids (`site_contoh_hub/…`) in UI text.
7. **P1 Legend must match the map:** hypothesis = amber dotted on the map, dashed in the legend.
8. Journey-screen layout fixes: floorplan_design_0300 §2 (footage as hero, no empty right third, timeline visible).

## Case summary (H14)
9. **P1 Headline too long** (3 lines at display size). H1: "Last confirmed at chute C04 · 14:32:31.8 MYT".
   One sub-line: "Where it went next isn't shown yet — CAM_07 and CAM_10 haven't been analysed."
10. **P1 Missing-moment tile claims a dashed box that isn't drawn** in the CAM_10 frame. Draw it or drop the claim.
11. **P2 Expected time:** tile 2 says expected 14:32:31.8 (= the last-confirmed time). Show the predicted window
    (e.g. 14:32:31.8–34.0) that matches Next action.
12. **P2 Route map** → new floor-plan language.

## All pages
13. **P1 Background seam** at y≈900 px in the full-page shots (sidebar/bg band changes colour). Make the sidebar
    and page background extend the full document height.
14. Logo: ON HOLD (floorplan_design_0300 §5). Don't touch it further.

Re-shoot all 3 screens (desktop 1440×900 viewport + full page, mobile 390) after 1–13 and send F-style-b.
