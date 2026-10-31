"""Touch-ups on the FINAL S2 blend (Rexton 1 Nov: no more full hub runs - small leftover glitches are fixed here,
WITHOUT re-running flow.py). The same idea as static_fixes.py, for moving objects:
- each fix is one entry in FIXES below: a named object, a frame range, what changes, why;
- only keyframe VALUES of that object inside its range change (eased in and out over EASE frames each side, so
  nothing jumps): never a key's frame (timing), never which parcel goes where, never a scan event - the scan log
  stays exactly as the final run wrote it (this script does not open it);
- workers' rigs and the S2 story parcel are not touched;
- input: the final run's blend; output: a NEW file (never the run's own blend).

  blender -b assets/hub/build/hub_lineAb_S2_<tag>c.blend -P assets/hub/touchup_final.py -- \\
      --save assets/hub/build/hub_lineAb_S2_final.blend
  py -X utf8 assets/hub/touchup_final.py --propose qa/review/s2_hub_<tag>/gates
      (system Python: candidate FIXES entries from that run's visible collision rows, to review and paste below)
Then re-gate the new blend (gate_all.sh) and compare: gate_table.py <new> --prev <run>, plus --pairs for the per-pair
table (no row may get worse).
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HUB = Path(__file__).resolve().parent
EASE = 2  # frames each side of a fix's range: the change ramps in / out (0.33, 0.66, 1)

# ------------------------------------------------------------------------------------------------ the fixes
# obj: object name; frames: (first, last) inclusive; move_cm: (x, y, z) world offset in cm at full strength;
# why: the gate row it clears (run, frames, pair, depth). Filled from --propose after review.
FIXES = [  # run 18 (final), from --propose, reviewed 1 Nov
    dict(obj="flow_parcel_053", frames=(19, 19), move_cm=(0.0, 0.0, 2.3), why="s2_hub_r18: 1 rows f19-19 vs chutes, 1.3 cm"),
    dict(obj="flow_parcel_054", frames=(117, 117), move_cm=(0.0, 0.0, 2.3), why="s2_hub_r18: 1 rows f117-117 vs chutes, 1.3 cm"),
    dict(obj="flow_parcel_059", frames=(189, 191), move_cm=(0.0, 0.0, 3.7), why="s2_hub_r18: 3 rows f189-191 vs chutes, 2.7 cm"),
    dict(obj="flow_parcel_064", frames=(414, 416), move_cm=(0.0, 0.0, 7.0), why="s2_hub_r18: 3 rows f414-416 vs chutes, 6.0 cm"),
    dict(obj="flow_parcel_064", frames=(598, 598), move_cm=(0.0, 0.0, 2.5), why="s2_hub_r18: 1 rows f598-598 vs flow_parcel_073, 1.5 cm"),
    dict(obj="flow_parcel_065", frames=(39, 42), move_cm=(0.0, 0.0, 3.4), why="s2_hub_r18: 4 rows f39-42 vs conveyors, 2.4 cm"),
    dict(obj="flow_parcel_069", frames=(441, 441), move_cm=(0.0, 0.0, 3.1), why="s2_hub_r18: 1 rows f441-441 vs parcels_static_merged, 2.1 cm"),
    dict(obj="flow_parcel_073", frames=(595, 599), move_cm=(0.0, 5.0, 0.0), why="s2_hub_r18: 1 rows f597 vs chutes, 3.9 cm - into the bin, away from the chute end over it (lifted, it met its underside: pass 2)"),
    dict(obj="flow_parcel_074", frames=(596, 596), move_cm=(0.0, 0.0, 3.1), why="s2_hub_r18: 1 rows f596-596 vs chutes, 2.1 cm"),
    dict(obj="flow_parcel_5015", frames=(9, 9), away_from='worker_dock_D05_s', cm=2.3, why="s2_hub_r18: 1 rows f9-9 vs worker_dock_D05_s_body, 1.3 cm"),
    dict(obj="flow_parcel_5017", frames=(88, 88), away_from='worker_dock_D05_s', cm=2.1, why="s2_hub_r18: 1 rows f88-88 vs worker_dock_D05_s_body, 1.1 cm"),
    dict(obj="flow_parcel_5018", frames=(120, 122), away_from='worker_dock_D05_n', cm=4.0, why="s2_hub_r18: 3 rows f120-122 vs worker_dock_D05_n_body, 8.4 cm"),
    dict(obj="flow_parcel_5018", frames=(137, 137), away_from='worker_dock_D05_n', cm=2.5, why="s2_hub_r18: 1 rows f137-137 vs worker_dock_D05_n_body, 1.5 cm"),
    dict(obj="flow_parcel_5019", frames=(155, 158), away_from='worker_dock_D05_s', cm=4.0, why="s2_hub_r18: 4 rows f155-158 vs worker_dock_D05_s_body, 3.3 cm"),
    dict(obj="flow_parcel_5020", frames=(208, 209), away_from='worker_dock_D05_n', cm=2.5, why="s2_hub_r18: 2 rows f208-209 vs worker_dock_D05_n_body, 1.5 cm"),
    dict(obj="flow_parcel_5021", frames=(498, 500), move_cm=(0.0, 0.0, 3.1), why="s2_hub_r18: 3 rows f498-500 vs conveyors, 2.1 cm"),
    dict(obj="flow_parcel_5021", frames=(223, 226), away_from='worker_dock_D05_s', cm=2.7, why="s2_hub_r18: 2 rows f223-226 vs worker_dock_D05_s_body, 1.7 cm"),
    dict(obj="flow_parcel_5021", frames=(239, 239), away_from='worker_dock_D05_s', cm=2.1, why="s2_hub_r18: 1 rows f239-239 vs worker_dock_D05_s_body, 1.1 cm"),
    dict(obj="flow_parcel_5022", frames=(511, 516), move_cm=(0.0, 0.0, 4.0), why="s2_hub_r18: 6 rows f511-516 vs conveyors, 4.0 cm"),
    dict(obj="flow_parcel_5022", frames=(251, 251), move_cm=(0.0, -2.0, 0.0), why="s2_hub_r18: 1 rows f251-251 vs lorries, 1.0 cm"),
    dict(obj="flow_parcel_5022", frames=(252, 252), away_from='worker_dock_D05_n', cm=4.0, why="s2_hub_r18: 1 rows f252-252 vs worker_dock_D05_n_body, 3.8 cm"),
    dict(obj="flow_parcel_5022", frames=(258, 258), away_from='worker_dock_D05_n', cm=4.0, why="s2_hub_r18: 1 rows f258-258 vs worker_dock_D05_n_body, 3.4 cm"),
    dict(obj="flow_parcel_5022", frames=(273, 273), away_from='worker_dock_D05_n', cm=2.8, why="s2_hub_r18: 1 rows f273-273 vs worker_dock_D05_n_body, 1.8 cm"),
    dict(obj="flow_parcel_5024", frames=(335, 335), move_cm=(0.0, 0.0, 3.4), why="s2_hub_r18: 1 rows f335-335 vs conveyors, 2.4 cm"),
    dict(obj="flow_parcel_5024", frames=(354, 354), away_from='worker_dock_D05_n', cm=2.6, why="s2_hub_r18: 1 rows f354-354 vs worker_dock_D05_n_body, 1.6 cm"),
    dict(obj="flow_parcel_5025", frames=(277, 277), away_from='worker_dock_D05_s', cm=2.6, why="s2_hub_r18: 1 rows f277-277 vs worker_dock_D05_s_body, 1.6 cm"),
    dict(obj="flow_parcel_5025", frames=(373, 376), away_from='worker_dock_D05_s', cm=4.0, why="s2_hub_r18: 3 rows f373-376 vs worker_dock_D05_s_body, 3.4 cm"),
    dict(obj="flow_parcel_5025", frames=(388, 388), away_from='worker_dock_D05_s', cm=2.3, why="s2_hub_r18: 1 rows f388-388 vs worker_dock_D05_s_body, 1.3 cm"),
    dict(obj="flow_parcel_5026", frames=(679, 683), move_cm=(0.0, 0.0, 4.0), why="s2_hub_r18: 5 rows f679-683 vs conveyors, 4.0 cm"),
    dict(obj="flow_parcel_5026", frames=(399, 402), away_from='worker_dock_D05_n', cm=3.6, why="s2_hub_r18: 3 rows f399-402 vs worker_dock_D05_n_body, 2.6 cm"),
    dict(obj="flow_parcel_5026", frames=(410, 410), away_from='worker_dock_D05_n', cm=4.0, why="s2_hub_r18: 1 rows f410-410 vs worker_dock_D05_n_body, 3.7 cm"),
    dict(obj="flow_parcel_5026", frames=(424, 424), away_from='worker_dock_D05_n', cm=2.1, why="s2_hub_r18: 1 rows f424-424 vs worker_dock_D05_n_body, 1.1 cm"),
    dict(obj="flow_parcel_5027", frames=(449, 450), away_from='worker_dock_D05_s', cm=4.0, why="s2_hub_r18: 2 rows f449-450 vs worker_dock_D05_s_body, 3.9 cm"),
    dict(obj="flow_parcel_5028", frames=(487, 491), away_from='worker_dock_D05_n', cm=4.0, why="s2_hub_r18: 5 rows f487-491 vs worker_dock_D05_n_body, 4.5 cm"),
    dict(obj="flow_parcel_5028", frames=(497, 497), away_from='worker_dock_D05_n', cm=3.3, why="s2_hub_r18: 1 rows f497-497 vs worker_dock_D05_n_body, 2.3 cm"),
    dict(obj="flow_parcel_5028", frames=(510, 510), away_from='worker_dock_D05_n', cm=2.5, why="s2_hub_r18: 1 rows f510-510 vs worker_dock_D05_n_body, 1.5 cm"),
    dict(obj="flow_parcel_5029", frames=(526, 526), move_cm=(0.0, 2.2, 0.0), why="s2_hub_r18: 1 rows f526-526 vs lorries, 1.2 cm"),
    dict(obj="flow_parcel_5029", frames=(528, 531), away_from='worker_dock_D05_s', cm=2.4, why="s2_hub_r18: 2 rows f528-531 vs worker_dock_D05_s_body, 1.4 cm"),
    dict(obj="flow_parcel_5030", frames=(594, 594), away_from='worker_dock_D05_n', cm=2.4, why="s2_hub_r18: 1 rows f594-594 vs worker_dock_D05_n_body, 1.4 cm"),
    dict(obj="flow_parcel_5031", frames=(629, 629), away_from='worker_dock_D05_s', cm=2.2, why="s2_hub_r18: 1 rows f629-629 vs worker_dock_D05_s_body, 1.2 cm"),
    dict(obj="flow_parcel_5032", frames=(654, 654), move_cm=(0.0, -2.0, 0.0), why="s2_hub_r18: 1 rows f654-654 vs lorries, 1.0 cm"),
    dict(obj="flow_parcel_5032", frames=(655, 665), away_from='worker_dock_D05_n', cm=4.0, why="s2_hub_r18: 10 rows f655-665 vs worker_dock_D05_n_body, 9.5 cm"),
    dict(obj="flow_parcel_5032", frames=(684, 684), away_from='worker_dock_D05_n', cm=2.6, why="s2_hub_r18: 1 rows f684-684 vs worker_dock_D05_n_body, 1.6 cm"),
    dict(obj="flow_parcel_5034", frames=(781, 781), away_from='worker_dock_D05_s', cm=2.2, why="s2_hub_r18: 1 rows f781-781 vs worker_dock_D05_s_body, 1.2 cm"),
    dict(obj="flow_parcel_5036", frames=(887, 890), move_cm=(4.0, 0.0, 0.0), why="s2_hub_r18: 4 rows f887-890 vs truck_wall_D05, 4.1 cm"),
    dict(obj="flow_parcel_5036", frames=(894, 897), away_from='worker_dock_D05_s', cm=4.0, why="s2_hub_r18: 4 rows f894-897 vs worker_dock_D05_s_body, 5.6 cm"),
    dict(obj="flow_parcel_072", frames=(453, 900), move_cm=(0.0, 0.0, 4.3), why="s2_hub_r18: landed f453 3.3 cm into flow_parcel_059 (at rest since f194), 449 rows: the newcomer goes up"),
    dict(obj="flow_parcel_5015", frames=(620, 900), move_cm=(0.0, 0.0, 14.0), why="s2_hub_r18: landed f624 14 cm into flow_parcel_059 (bottom 0.73, 059's top 0.868; the gate's 7.9 cm under-read it; from f620: falling past 072 (lifted) it clipped it, pass 2) (at rest since f194), 279 rows: the newcomer goes up"),
    dict(obj="flow_parcel_5018", frames=(386, 388), move_cm=(0.0, 0.0, 2.5),
         why="zone repairs 1 Nov: its corner dipped 2.3 cm below belt A's top f387 turning off induct 0 - over the 5 cm "
             "gap then, into the induct belt's new nose now (7.94, 9.97)"),
]


# static: whole loose parts (a sack / parcel of a merged static mesh) whose box meets this region are taken out (never cut
# open), as static_fixes.py does. obj; box (x0, x1, y0, y1, z0, z1); why.
STATIC_CUTS = [
    dict(obj="cage_loads_merged", box=(36.3, 37.1, 29.3, 29.95, 0.3, 1.9),
         why="final pass 3: worker_cage_1 walks past the parked cage's load corner, vest 5.9 cm into it f294-295, "
             "CAM_13 - Rexton: too much; the path cannot move (flow), the load items there go"),
]


# static geometry repaired in build_hub.py (the authoritative source): the object's mesh is swapped for the rebuilt one
# (sync_static.py, materials kept); cut_box: the run-time cut flow.py made in it for this scenario.
STATIC_SYNC = [
    dict(obj="conveyors", src="build/hub_lineAb.blend", cut_box=(-6.0, 0.58, 10.4, 11.6, 0.3, 1.3),
         why="zone audit 1 Nov: belt gaps / open bend corners / 0.4 m before the carriers / 5 cm boom + induct gaps "
             "(qa/review/zone_audit/defects.md); cut_box = flow.py --unstaff dock_D02 (D02's boom extension)"),
]


# ------------------------------------------------------------------------------------------------ propose
def propose(gates):
    """Per parcel, contiguous frame runs of its visible collision rows -> one entry each: up out of something static or
    another parcel (depth + 1 cm), across away from a worker (depth + 1 cm, at most 4 cm: further and the hands baked
    onto it are left behind - the held-object gate)."""
    scen = json.loads((HUB / "build" / "truth" / "scenario_S2.json").read_text(encoding="utf-8"))
    story = scen.get("story_object")
    rows = json.loads((Path(gates) / "rows_in_view.json").read_text(encoding="utf-8"))["seen_rows"]
    by = defaultdict(list)
    rest = defaultdict(int)
    for r in rows:
        pa, pb = r["a"], r["b"]
        par = pa if pa.startswith("flow_parcel_") else (pb if pb.startswith("flow_parcel_") else None)
        if par is None or par == story:
            rest[f"{pa.split('_body')[0]} | {pb}"] += 1
            continue
        other = pb if par == pa else pa
        by[(par, other)].append(r)
    out = []
    for (par, other), rs in sorted(by.items()):
        rs.sort(key=lambda r: int(r["frame"]))
        runs, cur = [], [rs[0]]
        for r in rs[1:]:
            if int(r["frame"]) - int(cur[-1]["frame"]) <= 3:
                cur.append(r)
            else:
                runs.append(cur)
                cur = [r]
        runs.append(cur)
        for run in runs:
            f0, f1 = int(run[0]["frame"]), int(run[-1]["frame"])
            dep = max(float(r["depth_cm"]) for r in run) + 1.0
            if other.startswith("worker_"):
                move = f"away_from={other.split('_body')[0]!r}, cm={min(dep, 4.0):.1f}"
            else:
                move = f"move_cm=(0.0, 0.0, {dep:.1f})"
            out.append(f'    dict(obj="{par}", frames=({f0}, {f1}), {move}, '
                       f'why="{Path(gates).parent.name}: {len(run)} rows f{f0}-{f1} vs {other}, {dep - 1:.1f} cm"),')
    print("\n".join(out))
    print(f"# not parcel rows (left as they are): {dict(rest)}")


# ------------------------------------------------------------------------------------------------ apply
def apply(save):
    import bpy
    from mathutils import Vector
    sys.path.insert(0, str(HUB))
    import people  # (layered-action F-curve helper)
    sc = bpy.context.scene
    story = json.loads((HUB / "build" / "truth" / "scenario_S2.json").read_text(encoding="utf-8")).get("story_object")
    rep = []
    for fx in FIXES:
        ob = sc.objects.get(fx["obj"])
        assert ob is not None, fx
        assert not ob.name.startswith("worker_") and ob.name != story, f"not allowed: {ob.name}"
        f0, f1 = fx["frames"]
        if "away_from" in fx:  # across, away from that worker's pelvis at the middle of the range
            sc.frame_set((f0 + f1) // 2)
            arm = sc.objects[fx["away_from"]]
            wp = arm.matrix_world @ arm.pose.bones["Bip01 Pelvis"].head
            d = ob.matrix_world.translation - wp
            d.z = 0.0
            if "dock" in fx["away_from"]:  # along the boom only: across, away from the north / south unloader
                d.y = 0.0  # is into the lorry's side wall (9 pairs worse, first touch-up pass)
            off = d.normalized() * fx["cm"] / 100.0
        else:
            off = Vector(fx["move_cm"]) / 100.0
        fcs = {}
        if ob.animation_data and ob.animation_data.action:
            fcs = {fc.array_index: fc for _b, l_ in people._channelbag_fcurves(ob.animation_data.action) for fc in l_
                   if fc.data_path == "location"}
        if len(fcs) < 3:  # never moves: as a whole (only if the fix covers the window)
            assert f0 <= sc.frame_start and f1 >= sc.frame_end, f"{ob.name}: no keys, the fix must cover the window"
            ob.location += off
            rep.append((ob.name, "whole", [round(v * 100, 1) for v in off]))
            continue
        n = 0
        for i in range(3):
            if abs(off[i]) < 1e-6:
                continue
            for kp in fcs[i].keyframe_points:
                g = int(round(kp.co.x))
                w_ = 1.0 if f0 <= g <= f1 else max(0.0, 1.0 - min(abs(g - f0), abs(g - f1)) / (EASE + 1))
                if w_ > 0:
                    kp.co.y += off[i] * w_
                    kp.handle_left.y += off[i] * w_
                    kp.handle_right.y += off[i] * w_
                    n += 1
            fcs[i].update()
        rep.append((ob.name, f"f{f0}-{f1}", [round(v * 100, 1) for v in off], n))
    import bmesh
    for cut in STATIC_CUTS:
        ob = sc.objects[cut["obj"]]
        M = ob.matrix_world
        x0, x1, y0, y1, z0, z1 = cut["box"]
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        seen, dead = set(), []
        for f0_ in bm.faces:
            if f0_.index in seen:
                continue
            isl, st = [], [f0_]
            seen.add(f0_.index)
            while st:
                g = st.pop()
                isl.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in seen:
                            seen.add(h.index)
                            st.append(h)
            vs = [M @ v.co for g in isl for v in g.verts]
            if (min(v.x for v in vs) < x1 and max(v.x for v in vs) > x0 and min(v.y for v in vs) < y1
                    and max(v.y for v in vs) > y0 and min(v.z for v in vs) < z1 and max(v.z for v in vs) > z0):
                dead += isl
        n_ = len({id(g) for g in dead})
        bmesh.ops.delete(bm, geom=list({id(g): g for g in dead}.values()), context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(ob.data)
        bm.free()
        rep.append((cut["obj"], "cut faces", n_))
    import sync_static
    for sy in STATIC_SYNC:
        rep.append((sy["obj"], "synced (verts old, new, faces cut)", sync_static.sync(sc, sy["obj"], sy["src"], sy["cut_box"])))
    import static_settle  # loose static items resting on something (as rebuild_lineAb.sh does after dressing)
    st = static_settle.settle(sc, json.loads((HUB / "hub_spec_lineAb.json").read_text(encoding="utf-8")))
    rep.append(("static_settle", [(r["obj"], r["at"], r["action"], r["gap_cm"]) for r in st]))
    rep.append(("separate_on_benches", static_settle.separate_on_benches(sc, json.loads((HUB / "hub_spec_lineAb.json")
                                                                                     .read_text(encoding="utf-8")))))
    sc.frame_set(sc.frame_start)
    print("TOUCHUP", len(FIXES), "fixes,", len(STATIC_CUTS), "static cuts,", len(STATIC_SYNC), "synced:", json.dumps(rep),
          flush=True)
    out = Path(save).resolve()
    assert "_final" in out.name and out != Path(bpy.data.filepath).resolve(), "output: a new *_final blend, never the input"
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--propose", default="")
    ap.add_argument("--save", default="")
    a = ap.parse_args(argv)
    if a.propose:
        propose(a.propose)
    else:
        assert a.save, "--save <new blend> (never the run's own blend)"
        apply(a.save)
