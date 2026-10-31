"""Mesh hygiene report (review "mesh_hygiene", Rexton 11:44 "spiderweb" white lines): per mesh object, the topology
faults that show as radiating lines / streaks under smooth shading or as z-fighting.

  blender -b --factory-startup <hub .blend> -P assets/hub/mesh_hygiene.py -- --out <dir> [--frame 1]

Per object (evaluated, world space): n-gons (> 4 verts) and the biggest one, non-planar faces (> 0.1 mm), sliver
triangles (min angle < 2 deg or aspect > 50), zero-area faces, duplicate vertices (< 0.1 mm), non-manifold edges (> 2
faces), loose verts / edges, smooth-shaded faces across > 60 deg edges, and z-fighting: faces of DIFFERENT objects that
lie within 1 mm of each other, facing the same way (cos > 0.999) and overlapping. Writes <out>/mesh_hygiene.csv and
<out>/mesh_hygiene_summary.txt (worst 20 per fault). Exit 0 always (qa_gate reads the csv).
"""
import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--frame", type=int, default=1)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out)
OUT.mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene
sc.frame_set(a.frame)
dg = bpy.context.evaluated_depsgraph_get()

SKIP = ("worker_", "flow_parcel_", "qa_", "crop_cam", "probe")
obs = [o for o in sc.objects if o.type == "MESH" and not o.hide_render and not o.name.startswith(SKIP)
       and o.visible_get()]
rows, bvhs = [], {}
for o in obs:
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(o.matrix_world)
    bm.normal_update()
    ev.to_mesh_clear()
    r = defaultdict(float)
    r["object"] = o.name
    r["faces"] = len(bm.faces)
    big = 0
    for f in bm.faces:
        n = len(f.verts)
        if n > 4:
            r["ngons"] += 1
            big = max(big, n)
        if n >= 4:
            no, c = f.normal, f.calc_center_median()
            dev = max(abs((v.co - c).dot(no)) for v in f.verts)
            if dev > 1e-4:
                r["nonplanar"] += 1
        if f.calc_area() < 1e-8:
            r["zero_area"] += 1
        if f.smooth:
            for e in f.edges:
                if len(e.link_faces) == 2 and e.smooth:  # (edges marked sharp are shaded flat)
                    ang = e.calc_face_angle(0.0)
                    if ang > math.radians(60):
                        r["smooth_sharp"] += 1
                        break
    r["biggest_ngon"] = big
    for e in bm.edges:
        lf = len(e.link_faces)
        if lf > 2:
            r["nonmanifold"] += 1
        if lf == 0:
            r["loose_edges"] += 1
    r["loose_verts"] = sum(1 for v in bm.verts if not v.link_edges)
    # slivers on the triangulation the renderer sees
    tris = bm.calc_loop_triangles()
    for lt in tris:
        p = [l.vert.co for l in lt]
        e = [(p[1] - p[0]).length, (p[2] - p[1]).length, (p[0] - p[2]).length]
        if min(e) < 1e-7:
            r["slivers"] += 1
            continue
        angs = []
        for i in range(3):
            u_, v_ = p[(i + 1) % 3] - p[i], p[(i + 2) % 3] - p[i]
            if u_.length < 1e-9 or v_.length < 1e-9:
                continue
            angs.append(u_.angle(v_, 0.0))
        area = 0.5 * (p[1] - p[0]).cross(p[2] - p[0]).length
        aspect = max(e) ** 2 / max(area * 2, 1e-12)  # ~ longest edge / height
        if (angs and min(angs) < math.radians(2)) or aspect > 50:
            r["slivers"] += 1
    # duplicate vertices
    if len(bm.verts) < 200000:
        kd = KDTree(len(bm.verts))
        for i, v in enumerate(bm.verts):
            kd.insert(v.co, i)
        kd.balance()
        seen = set()
        for i, v in enumerate(bm.verts):
            for co, j, d in kd.find_range(v.co, 1e-4):
                if j != i and (j, i) not in seen:
                    seen.add((i, j))
        r["dup_verts"] = len(seen)
    verts = [v.co.copy() for v in bm.verts]
    polys = [[v.index for v in f.verts] for f in bm.faces]
    fdata = [(f.calc_center_median(), f.normal.copy(), f.calc_area(), f.index) for f in bm.faces if f.calc_area() > 1e-4]
    bm.free()
    if verts and polys:
        lo = Vector([min(c[i] for c in verts) for i in range(3)])
        hi = Vector([max(c[i] for c in verts) for i in range(3)])
        bvhs[o.name] = (BVHTree.FromPolygons(verts, polys), lo, hi, fdata)
    rows.append(r)
print("HYG topology done", len(rows), flush=True)

# z-fighting between objects: a face centre of A within 1 mm of B's surface, parallel normals
byname = {r["object"]: r for r in rows}
zf_pairs = defaultdict(int)
names = sorted(bvhs)
for i, na in enumerate(names):
    A = bvhs[na]
    for nb in names:
        if nb == na:
            continue
        B = bvhs[nb]
        if any(A[1][k] > B[2][k] + 0.002 or B[1][k] > A[2][k] + 0.002 for k in range(3)):
            continue
        for c, nrm, area, fi in A[3]:
            if nrm.z < -0.9:  # an underside (facing the floor): no camera - all above it - can ever see it
                continue
            hit = B[0].find_nearest(c, 0.001)
            if hit[0] is not None and hit[1].dot(nrm) > 0.999:  # SAME-facing only: a bottom face resting on the
                # floor faces the other way and is hidden - it cannot flicker
                zf_pairs[(na, nb)] += 1
for (na, nb), n in zf_pairs.items():
    byname[na]["zfight_faces"] += n
    byname[na]["zfight_with"] = (byname[na].get("zfight_with") or "") + f"{nb}:{n} "
print("HYG z-fight pairs", len(zf_pairs), flush=True)

keys = ["object", "faces", "ngons", "biggest_ngon", "nonplanar", "slivers", "zero_area", "dup_verts", "nonmanifold",
        "loose_verts", "loose_edges", "smooth_sharp", "zfight_faces", "zfight_with"]
with open(OUT / "mesh_hygiene.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, keys)
    w.writeheader()
    for r in rows:
        w.writerow({k: (int(r[k]) if isinstance(r.get(k), float) else r.get(k, "")) for k in keys})
lines = [f"Mesh hygiene: {len(rows)} objects"]
for k in keys[2:-1]:
    tot = sum(r.get(k, 0) for r in rows if isinstance(r.get(k, 0), (int, float)))
    worst = sorted(rows, key=lambda r: -float(r.get(k, 0) or 0))[:20]
    lines.append(f"\n{k}: total {int(tot)}")
    lines += [f"  {int(r.get(k, 0)):6d}  {r['object']}" for r in worst if float(r.get(k, 0) or 0) > 0]
lines.append("\nz-fighting pairs (faces of A within 1 mm of B, parallel):")
lines += [f"  {n:5d}  {na} | {nb}" for (na, nb), n in sorted(zf_pairs.items(), key=lambda kv: -kv[1])[:40]]
(OUT / "mesh_hygiene_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("HYG done", flush=True)
