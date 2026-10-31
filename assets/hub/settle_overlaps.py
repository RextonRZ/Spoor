"""Still parcels that overlap another still parcel (run 9: line B's unstaffed gaylords, 5-13 cm for the whole window,
after flow.py's snap lowered one onto the side of its neighbour): the upper one is set on the other's top. Only parcels
that never move in the window (no location animation, or constant): a static fix, no flow re-run.

  blender -b <S2.blend> -P assets/hub/settle_overlaps.py -- --save <out.blend>
"""
import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ap = argparse.ArgumentParser()
ap.add_argument("--save", required=True)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
sc = bpy.context.scene
sc.frame_set(1)


def still(o):
    ad = o.animation_data
    if not (ad and ad.action):
        return True
    import people
    for _b, fcs in people._channelbag_fcurves(ad.action):
        for fc in fcs:
            if fc.data_path == "location" and len({round(k.co.y, 4) for k in fc.keyframe_points}) > 1:
                return False
    return True


sys.path.insert(0, str(Path(__file__).resolve().parent))
obs = [o for o in sc.objects if o.name.startswith("flow_parcel_") and o.type == "MESH" and not o.name.endswith("_label")
       and not o.hide_render and still(o)]


def geo(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    M = ev.matrix_world
    vs = [M @ v.co for v in me.vertices]
    t = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in me.polygons])
    ev.to_mesh_clear()
    return t, min(v.z for v in vs), max(v.z for v in vs), (min(v.x for v in vs), max(v.x for v in vs),
                                                           min(v.y for v in vs), max(v.y for v in vs))


moved = []
for _ in range(4):  # a raised parcel can land on a third: a few passes
    G = {o.name: geo(o) for o in obs}
    changed = False
    for o in sorted(obs, key=lambda o: G[o.name][1]):
        t, lo, hi, bb = G[o.name]
        for p in obs:
            if p is o:
                continue
            t2, lo2, hi2, bb2 = G[p.name]
            if bb[0] > bb2[1] or bb2[0] > bb[1] or bb[2] > bb2[3] or bb2[2] > bb[3] or lo < lo2 - 1e-4:
                continue  # apart, or p is the upper one (it moves when its turn comes)
            if t.overlap(t2):
                dz = hi2 + 0.002 - lo
                o.location.z += dz
                if o.animation_data and o.animation_data.action:  # constant keys: shift them all
                    import people
                    for _b, fcs in people._channelbag_fcurves(o.animation_data.action):
                        for fc in fcs:
                            if fc.data_path == "location" and fc.array_index == 2:
                                for k in fc.keyframe_points:
                                    k.co.y += dz
                                    k.handle_left.y += dz
                                    k.handle_right.y += dz
                bpy.context.view_layer.update()
                G[o.name] = geo(o)
                t, lo, hi, bb = G[o.name]
                moved.append((o.name, p.name, round(dz, 3)))
                changed = True
    if not changed:
        break
print("SETTLE", len(obs), "still parcels,", len(moved), "raised:", moved[:30], flush=True)
bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.save).resolve()), compress=True)
