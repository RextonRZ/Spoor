"""Copy repaired static geometry from the authoritative build (build_hub.py -> build/hub_lineAb.blend) into a dressed /
run blend without re-running anything (Rexton 1 Nov, zone repairs: fix build_hub.py, then bring the same meshes into
the S2 final blend - parcel animation untouched). Only the named objects' MESH DATA is swapped: the object (name,
transform, parent, animation) and the scene's own materials (relit by light_test.py) stay.

  blender -b <blend> -P assets/hub/sync_static.py -- --objects conveyors [--src build/hub_lineAb.blend] --save <out>
touchup_final.py calls sync() for its STATIC_SYNC entries (with the run-time cut flow.py made, e.g. D02's boom).
"""
import argparse
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent


def sync(sc, obj, src="build/hub_lineAb.blend", cut_box=None):
    """Swap obj's mesh for the one in src; cut_box (x0, x1, y0, y1, z0, z1): faces whose centre is inside go, as flow.py
    cuts them at run time. Returns (old verts, new verts, faces cut)."""
    import bmesh
    import bpy
    ob = sc.objects[obj]
    with bpy.data.libraries.load(str(HUB / src)) as (_, dt):
        dt.objects = [obj]
    so = dt.objects[0]
    new, old = so.data, ob.data
    assert len(new.materials) == len(old.materials), f"{obj}: material slots {len(new.materials)} != {len(old.materials)}"
    for i, m in enumerate(old.materials):
        new.materials[i] = m
    n_cut = 0
    if cut_box:
        x0, x1, y0, y1, z0, z1 = cut_box
        bm = bmesh.new()
        bm.from_mesh(new)
        mw = ob.matrix_world
        dead = [f for f in bm.faces if (lambda c: x0 <= c.x <= x1 and y0 <= c.y <= y1 and z0 <= c.z <= z1)(
            mw @ f.calc_center_median())]
        n_cut = len(dead)
        bmesh.ops.delete(bm, geom=dead, context="FACES_ONLY")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(new)
        bm.free()
    nv_old = len(old.vertices)
    ob.data = new
    bpy.data.objects.remove(so)
    bpy.data.meshes.remove(old)
    new.name = obj
    return nv_old, len(new.vertices), n_cut


if __name__ == "__main__":
    import bpy
    ap = argparse.ArgumentParser()
    ap.add_argument("--objects", required=True)
    ap.add_argument("--src", default="build/hub_lineAb.blend")
    ap.add_argument("--save", required=True)
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
    for o in a.objects.split(","):
        print("SYNC", o, sync(bpy.context.scene, o, a.src), flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.save).resolve()), compress=True)
