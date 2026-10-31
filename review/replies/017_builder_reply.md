# 017 reply (builder, 30 Oct ~19:55)

| # | Your call | Done / plan |
|---|---|---|
| 1 | Waiting must look like waiting (no frozen stand > 3 s) | **Plan (step 3, next):** holds over 1.5 s get a desynced idle variation: weight shift, glance up the feed, shoulder roll, hand on the table rail, or stepping to straighten the next parcel. The holds today only carry a breathing sway and an upstream glance. Source: 100STYLE neutral idles (CC BY, already fetched) and Rocketbox idles (MIT). Gate row: the longest still stretch per worker < 3 s. |
| 2 | Mailers: (b) side-edge pinch + 1–3 cm sag; > 40 cm → two hands on the side edges | **Next.** The 44 cm mailer size in `flow.MAILER_DIMS` goes two-handed. |
| 3 | Hold ≤ 1.5 s over the belt | **Done:** `stations.MocapInductors.MAX_WAIT_S = 1.5` (was 8 s). If the set-down zone is still taken after 1.5 s, he should put the parcel back at the table's stop and wait hands off. That motion isn't built yet, so for now it's **counted as an overflow and must stay 0**. Over 5 seeds (incl. the 240 s pre-roll): **0 overflows, 0 conflicts**, no hold in any 30 s window. The induct belt already accumulates (set-down zone + queue to the merge). |

Also since 017:
- **The first full-hub run with the mocap inductors works:** layout (b), all stations, 7.5 min, `build/hub_lineAb_dressed.blend`, 4 inductors with 6 / 7 / 6 / 2 cycles in the window.
- **Before anything is shown, I'm measuring three problems:**
  - the engine's release lands up to 25 cm from the flow's place point, and some parcels end up beside their induct belt;
  - the IK falls up to 61 mm short on a few reaches;
  - 3 belt starts at 0.3 s come before the hands are clear.

  The hub collision check is running.
