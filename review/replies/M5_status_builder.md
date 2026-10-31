# M5 (21:45, S0 + S2 rebuilt on mocap, full gates): not reachable tonight. Here is why and what comes next

From the builder, 30 Oct evening. You asked for a reply with the blocker rather than silence.

## Why
Everything on mocap so far is a **standalone bench in the lit hub** with its own geometry and cartons:
- the inductor (M3);
- line A with 4 induct points (M4, request 016);
- the dock unloader (M4 part 2, rendering now).

None of it is in `flow.py` yet. S0–S5 still run the old procedural workers. Wiring needs, in order:
1. **The line A (b) geometry into the hub build** (feed belt north, tables, diverters, 4 induct belts, old feed run out). About 2–3 h.
2. **Flow:** induct belts with indexing and merge gap control, and the parcel route through diverter → table → inductor → induct belt. About 3–4 h.
3. **Stations:** `MocapInductors` and `MocapDocks` replacing the old classes, keeping the dock wall plan and the "picked carton becomes a flow parcel at the release" link. About 3–4 h.
4. **Gates** on the whole hub, then fixes. About 4–8 h.
5. **The other stations on mocap:** line B, bagger, cage pushers, opener, tech. About 11–15 h.

Total is roughly **23–34 working hours**. The plan is in `assets/hub/mocap/M5_PLAN.md`.

## Tonight, until 22:00
- Send the dock (016b) when its render is composed.
- Write the end-of-day summary in `FOR_REXTON.md`, with the Nov 4 risk and the options.

## Tomorrow (unless you reorder)
- Start M5 step 1 (geometry) and step 2 (flow) for line A first, because the pitch camera covers it.
- Then the dock.

**Avatars:**
- Female avatars need hand-grip tuning first. Both F09 and F17 curl their little fingers 4–5 cm. A per-avatar palm offset, measured from the bind pose, fixes most of it; F17's hips still touch the carton at the lift.
- Line A is all male tonight. I'd like at least one woman on the line once that is clean.
