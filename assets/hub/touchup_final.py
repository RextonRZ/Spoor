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
FIXES = [
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
    sc.frame_set(sc.frame_start)
    print("TOUCHUP", len(FIXES), "fixes:", json.dumps(rep), flush=True)
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
