"""How many people does each camera see? (021d review condition 3: with stations unstaffed for a render, each camera
that had people still shows at least one, so the hub doesn't read as empty.) Per sampled frame and camera: workers
whose pelvis or head is in the frame, kept by the lens crop and not hidden behind the static hub (the in-view test of
mocap/rows_in_view.py).

  blender -b <scenario.blend> -P assets/hub/qa_people_in_view.py -- --cams CAM_01,CAM_06 --out <json> [--step 30]
"""
import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--cams", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--step", type=int, default=30)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

import importlib.util  # noqa: E402

spec_ = importlib.util.spec_from_file_location("riv_src", Path(__file__).resolve().parent / "mocap" / "rows_in_view.py")
src = spec_.loader.get_source("riv_src")
src = src[:src.index("cams = [sc.objects[c]")]  # only its functions (sees, lens_keeps), not its main pass
riv = {"__file__": str(Path(__file__).resolve().parent / "mocap" / "rows_in_view.py")}
exec(compile(src.replace("a = ap.parse_args(sys.argv[sys.argv.index(\"--\") + 1:])", "a = None"), "riv", "exec"), riv)
sees = riv["sees"]

sc = bpy.context.scene
cams = [sc.objects[c] for c in a.cams.split(",") if c in sc.objects]
workers = [o for o in sc.objects if o.type == "ARMATURE" and o.name.startswith("worker_")]
F0, F1 = sc.frame_start, sc.frame_end
per = {c.name: [] for c in cams}
names = {c.name: set() for c in cams}
for f in range(F0, F1 + 1, a.step):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    for c in cams:
        n = 0
        for w in workers:
            if w.hide_render or not w.visible_get():
                continue
            pts = []
            for bn in ("Bip01 Pelvis", "Bip01 Head", "Hips", "Head"):
                if bn in w.pose.bones:
                    pts.append(w.matrix_world @ w.pose.bones[bn].head)
            if not pts:
                pts = [w.matrix_world.translation + Vector((0, 0, 1.0))]
            ign = {w.name} | {ch.name for ch in w.children}
            if any(sees(c, p, ign, dg) for p in pts):
                n += 1
                names[c.name].add(w.name)
        per[c.name].append((f, n))
out = {c: dict(min=min(n for _, n in v), max=max(n for _, n in v), mean=round(sum(n for _, n in v) / len(v), 1),
               frames_with_none=[f for f, n in v if n == 0], people=sorted(names[c])) for c, v in per.items()}
Path(a.out).write_text(json.dumps(out, indent=1))
print("PEOPLE", json.dumps({c: {k: v[k] for k in ("min", "max", "mean")} | {"none": len(v["frames_with_none"])}
                            for c, v in out.items()}))
