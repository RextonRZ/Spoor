"""QA: the head's clearance to every carton box, per frame (review 016b #1: head >= 5 cm off any carton).

  blender -b qa/review/m4_dock/m4_dock.blend -P assets/hub/mocap/head_clear.py -- <armature> <carton prefix> <out.json>

Head = body vertices weighted > 0.5 to the head / neck bones. Clearance = distance from the nearest head vertex to
the carton's box (negative = inside).
"""
import json
import sys

import bpy
import numpy as np

arm_name, prefix, out = sys.argv[sys.argv.index("--") + 1:][:3]
sc = bpy.context.scene
arm = bpy.data.objects[arm_name]
body = next(o for o in bpy.data.objects if o.type == "MESH" and o.parent == arm and o.vertex_groups.get("Bip01 Head"))
gi = {body.vertex_groups[n].index for n in ("Bip01 Head", "Bip01 Neck") if body.vertex_groups.get(n)}
head = np.array([v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in gi) > 0.5])
boxes = []
for o in bpy.data.objects:
    if o.type == "MESH" and o.name.startswith(prefix) and not o.name.endswith("_label"):
        bb = np.array([v.co for v in o.data.vertices])
        boxes.append((o, bb.min(0), bb.max(0)))
rows = []
for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ob_ = body.evaluated_get(dg)
    me_ = ob_.to_mesh()
    co = np.empty(len(me_.vertices) * 3)
    me_.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)[head]
    co = co @ np.array(ob_.matrix_world)[:3, :3].T + np.array(ob_.matrix_world)[:3, 3]
    ob_.to_mesh_clear()
    best = (9.0, "")
    for o, lo, hi in boxes:
        Mi = np.array(o.matrix_world.inverted())
        loc = co @ Mi[:3, :3].T + Mi[:3, 3]
        out_d = np.linalg.norm(np.maximum(np.maximum(lo - loc, loc - hi), 0.0), axis=1)
        ins = np.all((loc > lo) & (loc < hi), axis=1)
        d_ = np.where(ins, -np.minimum(loc - lo, hi - loc).min(1), out_d)
        if d_.min() < best[0]:
            best = (float(d_.min()), o.name)
    rows.append((f, round(best[0] * 100, 1), best[1]))
under = [r for r in rows if r[1] < 5.0]
res = dict(head_vertices=int(len(head)), cartons=len(boxes), min_cm=min(r[1] for r in rows),
           frames_under_5cm=len(under), under_5cm=under, rows=rows)
open(out, "w").write(json.dumps(res, indent=0))
print("HEAD_CLEAR", res["min_cm"], len(under), under[:40], flush=True)
