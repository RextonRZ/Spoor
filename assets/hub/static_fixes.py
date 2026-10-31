"""Fixes to the dressed hub that the flow simulation reads (run on hub_lineAb_dressed_lit.blend, saved in place):
- static parcels heaped ABOVE a chute bag's lip (C05's contents stood at 1.068 m over a 1.0 m lip: drops cut
  through its crest, run 9-11) are taken out whole (a parcel's own faces: never cut open).

  blender -b assets/hub/build/hub_lineAb_dressed_lit.blend -P assets/hub/static_fixes.py
"""
import json
from pathlib import Path

import bmesh
import bpy

HUB = Path(__file__).resolve().parent
SPEC = json.loads((HUB / "hub_spec_lineAb.json").read_text(encoding="utf-8"))
ob = bpy.data.objects["parcels_static_merged"]
M = ob.matrix_world
bm = bmesh.new()
bm.from_mesh(ob.data)
bm.faces.ensure_lookup_table()
bags = [(c["x"] - 0.5, c["bag_frame_y"], c["x"] + 0.5, c["bag_frame_y"] + 0.8, c["lip_z"]) for c in SPEC["machines"]["chutes"]
        if c.get("bag_frame_y") is not None]
seen, dead, n_isl = set(), [], 0
for f in bm.faces:
    if f.index in seen:
        continue
    isl, stack = [], [f]
    seen.add(f.index)
    while stack:  # the parcel this face belongs to (linked faces)
        g = stack.pop()
        isl.append(g)
        for e in g.edges:
            for h in e.link_faces:
                if h.index not in seen:
                    seen.add(h.index)
                    stack.append(h)
    vs = [M @ v.co for g in isl for v in g.verts]
    cx, cy, zt = sum(v.x for v in vs) / len(vs), sum(v.y for v in vs) / len(vs), max(v.z for v in vs)
    if any(x0 <= cx <= x1 and y0 <= cy <= y1 and zt > lip - 0.02 for x0, y0, x1, y1, lip in bags):
        dead += isl
        n_isl += 1
bmesh.ops.delete(bm, geom=list({id(g): g for g in dead}.values()), context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.to_mesh(ob.data)
bm.free()
print("STATIC_FIXES parcels over a bag lip removed:", n_isl, flush=True)
bpy.ops.wm.save_mainfile(compress=True)
