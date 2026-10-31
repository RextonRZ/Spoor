"""Line A (b) inductor setup, shared by the bench (m4_line_a.py) and the hub (stations.MocapInductors, M5 step 3):
the avatar (Rocketbox FBX + hi-vis vest), its trunk clearance from its own mesh, and the station dict the mocap engine
(inductor.build) works to. Geometry as the bench measured it (belt A's belt surface y 9.13-9.85 at 1.0 m; the gravity
table 0.68 m left of the worker, 0.95 -> 0.88 m; the induct belt 1.2 m at 45 deg into belt A).
"""
import math
from pathlib import Path

import numpy as np

OP_Y, BELT_Y, BELT_HALF, BELT_TOP = 11.15, 9.49, 0.36, 1.0
TDX, TW, TZ0, TZ1 = 0.68, 0.5, 0.95, 0.88
TY0, TY1 = OP_Y + 0.63, OP_Y - 0.10  # table head (at the feed) .. low end
STOP_Y = TY1 - 0.03
SLOPE = math.atan((TZ0 - TZ1) / (TY0 - TY1))
IND_D = np.array([math.sqrt(0.5), -math.sqrt(0.5)])  # induct belt direction (45 deg into belt A, downstream)
IND_HW = 0.25
IND_LEN = (OP_Y - 0.5 - (BELT_Y + BELT_HALF - 0.05)) / math.sqrt(0.5)  # ~1.2 m, ends 5 cm over belt A's edge


def induct_start(x0):
    """Where his induct belt starts: 0.5 m in front of him, a little to his right."""
    return np.array([x0 - 0.15, OP_Y - 0.5])


def induct_qa_boxes(x0):
    """The induct belt's volume as 6 stepped boxes along it: [(lo xyz, hi xyz)] and the engine's surface tuples."""
    S = induct_start(x0)
    nrm = np.array([-IND_D[1], IND_D[0]])
    vols, surf = [], []
    for j in range(6):
        pts = [S + IND_D * IND_LEN * (j + u) / 6 + nrm * v * IND_HW for u in (0, 1) for v in (-1, 1)]
        lo, hi = np.min(pts, 0), np.max(pts, 0)
        vols.append((np.array([lo[0], lo[1], BELT_TOP - 0.06]), np.array([hi[0], hi[1], BELT_TOP])))
        surf.append((lo[0], lo[1], hi[0], hi[1], BELT_TOP))
    return vols, surf


def import_avatar(sc, rb, avatar, vest_colour, name, x, y):
    """Rocketbox avatar (its own actions dropped) + a hi-vis vest, standing at (x, y). Returns (armature, body)."""
    import bpy
    import people
    before_o, before_a = set(sc.objects), set(bpy.data.actions)
    bpy.ops.import_scene.fbx(filepath=str(Path(rb) / avatar / f"{avatar}.fbx"))
    new_o = [o for o in sc.objects if o not in before_o]
    arm = next(o for o in new_o if o.type == "ARMATURE")
    body = next(o for o in new_o if o.type == "MESH" and o.parent == arm)
    people._fix_materials(body, Path(rb) / avatar)
    for o in new_o:
        if o.animation_data:
            o.animation_data.action = None
    for act in [x_ for x_ in bpy.data.actions if x_ not in before_a]:
        bpy.data.actions.remove(act)
    arm.name = name
    try:
        vest = people._vest(body, arm)
        sc.collection.objects.link(vest)
        vest.material_slots[0].link = "OBJECT"
        vest.material_slots[0].material = people._vest_material(vest_colour, people.VEST_COLOURS[vest_colour], False,
                                                                vest["front_is_low_y"])
    except Exception as e:  # noqa: BLE001
        print("vest failed", repr(e), flush=True)
    arm.location.x, arm.location.y = x, y
    bpy.context.view_layer.update()
    return arm, body


def trunk_clearance(arm, body):
    """From this avatar's own body (rest pose, facing -y): furthest-forward torso vertex (hips included) from the
    Spine2 line, + the hi-vis vest (~3.5 cm) + 2 cm."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    me_r = body.evaluated_get(dg).to_mesh()
    co_r = np.empty(len(me_r.vertices) * 3)
    me_r.vertices.foreach_get("co", co_r)
    co_r = co_r.reshape(-1, 3) @ np.array(body.matrix_world)[:3, :3].T + np.array(body.matrix_world)[:3, 3]
    body.evaluated_get(dg).to_mesh_clear()
    sp2 = arm.matrix_world @ arm.pose.bones["Bip01 Spine2"].head
    pel = arm.matrix_world @ arm.pose.bones["Bip01 Pelvis"].head
    band = (co_r[:, 2] > pel.z - 0.15) & (co_r[:, 2] < sp2.z + 0.1) & (np.abs(co_r[:, 0] - sp2.x) < 0.2)
    return float(np.max(sp2.y - co_r[band, 1])) + 0.035 + 0.02


def torso_front(arm, body, z0, z1):
    """Furthest-forward body vertex (rest pose, facing -y) in the band z0..z1 m above the pelvis head, from the
    Spine2 line (no vest margin): how close a carried box can sit at that height (S2 carry, review 021 #2)."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    me_r = body.evaluated_get(dg).to_mesh()
    co_r = np.empty(len(me_r.vertices) * 3)
    me_r.vertices.foreach_get("co", co_r)
    co_r = co_r.reshape(-1, 3) @ np.array(body.matrix_world)[:3, :3].T + np.array(body.matrix_world)[:3, 3]
    body.evaluated_get(dg).to_mesh_clear()
    sp2 = arm.matrix_world @ arm.pose.bones["Bip01 Spine2"].head
    pel = arm.matrix_world @ arm.pose.bones["Bip01 Pelvis"].head
    band = (co_r[:, 2] > pel.z + z0) & (co_r[:, 2] < pel.z + z1) & (np.abs(co_r[:, 0] - sp2.x) < 0.2)
    return float(np.max(sp2.y - co_r[band, 1]))


def bind_curl(rig):
    """How far the little-finger tip sits on the palm side of the palm point in the bind pose (logged only: the held
    fingers are un-curled into the palm plane by inductor.build)."""
    bi_, rh_, MRr = rig["bi"], rig["rhead"] * rig["scale"], rig["MR"]
    curl = 0.0
    for x_ in ("L", "R"):
        hd_ = bi_[f"Bip01 {x_} Hand"]
        n_loc = rig["AT"][hd_].T @ (MRr.T @ np.array([0.0, 0.0, -1.0]))
        n_rest = rig["rest"][hd_] @ n_loc
        palm = rh_[hd_] + 0.55 * (rh_[bi_[f"Bip01 {x_} Finger2"]] - rh_[hd_])
        f41, f42 = rh_[bi_[f"Bip01 {x_} Finger41"]], rh_[bi_[f"Bip01 {x_} Finger42"]]
        tip = f42 + (f42 - f41) * 0.9
        curl = max(curl, float(np.dot(tip - palm, n_rest)))
    return curl


def station(x0, trunk_clear, palm_off=0.04, hold_back=None, free_hand="back", ind_surfaces=None):
    """The engine's station dict for the inductor at x0 (see inductor.Planner / build)."""
    TX = x0 + TDX
    RAIL_X = TX - TW / 2 - 0.02
    S_k = induct_start(x0)
    ind_surfaces = induct_qa_boxes(x0)[1] if ind_surfaces is None else ind_surfaces
    roll = (TY0 - TY1 - 0.15) / 0.4
    return dict(x=x0, belt_yaw=0.0, table_pt=(TX, STOP_Y + 0.12, TZ1 + 0.01),
                place_xy=tuple(S_k + IND_D * 0.22), induct_start=tuple(S_k), induct_dir=tuple(IND_D),
                induct_half_w=IND_HW, main_y=BELT_Y, clear_y=OP_Y - 0.10, grip_axis_yaw=-math.pi / 2,
                trunk_clear=trunk_clear, palm_off=palm_off, root_min_y=OP_Y - 0.13,
                refill_s=1.0 + roll if hold_back is None else 0.3 + min(hold_back, TY0 - TY1 - 0.15) / 0.4,
                divert_s=0.6 if hold_back is None else 0.3 + min(hold_back, TY0 - TY1 - 0.15) / 0.4,
                pick_root_max=(RAIL_X - max(0.26, trunk_clear - 0.035 + 0.06), 1e9),
                pick_grip_min_z=TZ1 + 0.045 + 0.05, table_align_x=RAIL_X + 0.02,
                surfaces=[(5.6, BELT_Y - BELT_HALF, 15.0, BELT_Y + BELT_HALF, BELT_TOP),
                          (TX - TW / 2, TY1 - 0.03, TX + TW / 2, TY0, TZ0),
                          (TX - TW / 2, STOP_Y - 0.03, TX + TW / 2, STOP_Y, TZ1 + 0.04)] + list(ind_surfaces),  # end stop
                place_x=(x0 - 0.4, x0 + 0.4), place_y_range=(BELT_Y - BELT_HALF + 0.05, BELT_Y + BELT_HALF - 0.05),
                belt_top=BELT_TOP, belt_speed=1.5, belt_dir=1.0, table_slope=SLOPE, free_hand=free_hand,
                roller_gaps_y=[TY0 + (TY1 - TY0) * (j + 0.5) / 8 for j in range(8)],  # 9 rollers, 5 cm, 9.1 cm pitch
                pinch_y_min=TY1 + 0.07,  # a far pinch keeps its fingers off the end stop (bench: the gap next to it)
                table_stop_y=STOP_Y,  # the end stop's face (a far-pinch bench parcel is set against it by its own size)
                brace_rail=dict(x=TX - TW / 2, y0=TY1 - 0.03, ym=(TY0 + TY1) / 2, y1=TY0, z_a=TZ1 + 0.045,
                                z_b=TZ0 + 0.03))
