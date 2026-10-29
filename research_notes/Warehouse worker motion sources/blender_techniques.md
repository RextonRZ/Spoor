# Blender techniques: hand-object contact, mocap retargeting, foot locking, procedural pick-and-place, NLA (Blender 4.2+ / 5.x, headless Python)

Scope note: the cited API and manual facts were checked against the official docs on docs.blender.org (the "current" docs are the 5.x line) and against the local copy of the API and manual RST files bundled with the Blender MCP server (`C:\Users\ooiru\tools\blender_mcp\mcp\blmcp\data\{api,manual}`). The code patterns under "Inferences" are implementation recommendations built from those documented APIs. They have **not** been run in this research pass, so test them in a scratch .blend before production use.

---

## Q1. What is the most reliable headless-Python way to attach a parcel to a hand from frame A to frame B and leave it at the release spot afterwards, without popping?

### Takeaway
The most reliable headless method skips live parenting entirely. Evaluate the hand's world matrix every frame and write `parcel.matrix_world = M_hand(f) @ grip_offset` as per-frame keys (a "matrix bake"). Before A and after B, hold constant keys at the pick-up and release poses. A Child Of constraint with keyed influence also works, but it has three classic pop sources: the inverse matrix, interpolated influence, and an un-keyed basis after release. If you use it, bake it to plain keys with `anim_utils.bake_action(..., do_visual_keying=True, do_constraint_clear=True)`.

### Cited Findings
- The Child Of constraint "transforms an object or bone as though it were a child of another object or bone". The manual says its main advantage over real parenting is "an animatable Influence, which makes it possible to switch to different parents over time". Influence can also mix several Child Of constraints into a weighted average of parents. — [Blender Manual: Child Of](https://docs.blender.org/manual/en/latest/animation/constraints/relationship/child_of.html) (also in the bundled manual RST)
- Manual on Set Inverse: "If the child's transform is correct with the constraint disabled but incorrect with the constraint enabled, click this button to fix it." Clear Inverse "tells the constraint that the child's current transform with the constraint disabled is its correct relative transform … applied as an offset to the parent". — [Blender Manual: Child Of](https://docs.blender.org/manual/en/latest/animation/constraints/relationship/child_of.html)
- The Python API exposes `ChildOfConstraint.inverse_matrix` (a 4x4 "Transformation matrix to apply before") and `set_inverse_pending` ("Set to true to request recalculation of the inverse matrix"). — [API: ChildOfConstraint](https://docs.blender.org/api/current/bpy.types.ChildOfConstraint.html); [4.3 API](https://docs.blender.org/api/4.3/bpy.types.ChildOfConstraint.html)
- Since a 2020 change, the Set Inverse operator "defers this computation to be performed during constraint evaluation by just setting a flag". The inverse is therefore only computed when the depsgraph next evaluates, at whatever frame is current then. — [Blender commit history, bl_constraints tests](https://projects.blender.org/archive/blender-archive/commits/commit/0cdc75ccd28c607677c302014cd40df542d85d35/tests/python/bl_constraints.py) (via search summary)
- Calling `bpy.ops.constraint.childof_set_inverse` from scripts is fragile. It needs the constraint in context, and developers say constraint operators "are not really that useful to be called from Python". Users also report `inverse_matrix` being set with no visible effect until a refresh. — [Blender tracker #39891](https://projects.blender.org/blender/blender-addons/issues/39891); [BlenderArtists: set inverse via Python](https://blenderartists.org/t/set-inverse-child-of-constraints-via-python/1133914); [BlenderArtists: why can't I execute set inverse](https://blenderartists.org/t/why-cant-i-execute-clear-set-inverse-of-child-of-constraints-with-python/1233025)
- A fix to Set Inverse for armature targets notes that the inverse "should also take the armature object's transform into account". For a bone subtarget, the parent matrix is `armature.matrix_world @ pose_bone.matrix`, not `pose_bone.matrix` alone. — (same commit history, via search summary)
- Baking API in the current docs: `bpy_extras.anim_utils.bake_action(obj, *, action, frames, bake_options)`, where `BakeOptions(only_selected, do_pose, do_object, do_visual_keying, do_constraint_clear, do_parents_clear, do_clean, do_location, do_rotation, do_scale, do_bbone, do_custom_props)`. The operator form is `bpy.ops.nla.bake(frame_start, frame_end, step, only_selected=True, visual_keying=False, clear_constraints=False, clear_parents=False, use_current_action=False, clean_curves=False, bake_types={'POSE'}, channel_types={...})`. — [API: bpy_extras.anim_utils](https://docs.blender.org/api/current/bpy_extras.anim_utils.html); [API: bpy.ops.nla](https://docs.blender.org/api/current/bpy.ops.nla.html)
- Built-in "Global Transform" tools (formerly the Copy Global Transform add-on) live at 3D Viewport > Sidebar > Animation > Global Transform, with operators `bpy.ops.object.copy_global_transform` and `bpy.ops.object.paste_transform`. They include "Paste and Bake" (paste and auto-key every frame between the first and last selected keys), "Relative" copy/paste against a chosen object, and "Fix to Camera". Limitation: "If there are constraints on the Object/Bone, the resulting visual transformation may not be the same as the pasted one". — [Manual: Global Transform](https://docs.blender.org/manual/en/latest/editors/3dview/animation/copy_global_transform.html); older add-on page: [4.2 manual](https://docs.blender.org/manual/en/4.2/addons/animation/copy_global_transform.html)
- Version note: Blender 5.0 removed the legacy `Action.fcurves`, `Action.groups` and `Action.id_root`. F-curves are now reached through slots and channelbags, e.g. `bpy_extras.anim_utils.action_ensure_channelbag_for_slot(action, slot)` and then `channelbag.fcurves.new/find/ensure`. 4.4 and 4.5 still have `fcurves` as a legacy property that only sees the first slot. — [API 5.0: Action](https://docs.blender.org/api/5.0/bpy.types.Action.html); [API 4.4: ActionFCurves](https://docs.blender.org/api/4.4/bpy.types.ActionFCurves.html); [Cinevva Blender 5 guide (third-party)](https://app.cinevva.com/es/guides/blender-5-for-game-artists); helper functions confirmed in [API: anim_utils](https://docs.blender.org/api/current/bpy_extras.anim_utils.html)
- Actions are organised into slots: "An animated data-block then specifies both an action and a slot within that action". Every action needs at least one slot. — [Manual: Actions › Action Slots](https://docs.blender.org/manual/en/latest/animation/actions.html)

### Inferences
**Recommended pattern A: matrix bake (no constraints; robust headless, no dependency cycles, multi-grab and hand-over safe).**
```python
import bpy
from mathutils import Matrix

def hand_world(arm, bone_name, depsgraph):
    ev = arm.evaluated_get(depsgraph)
    return ev.matrix_world @ ev.pose.bones[bone_name].matrix   # armature space -> world

def attach_bake(parcel, segments, f_start, f_end, scene):
    """segments: list of (frame_from, frame_to, arm, bone_name) in time order; parcel is free outside them.
    The parcel keeps its world pose at grab time relative to the hand (offset from the grab frame)."""
    parcel.rotation_mode = 'QUATERNION'
    keys = {}
    world = None
    for f in range(f_start, f_end + 1):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        seg = next((s for s in segments if s[0] <= f <= s[1]), None)
        if seg:
            A, B, arm, bone = seg
            if f == A:                                    # grab: freeze the offset, no pop
                cur = world if world is not None else parcel.matrix_world.copy()
                seg_offset = hand_world(arm, bone, dg).inverted() @ cur
                keys[('off', A)] = seg_offset
            world = hand_world(arm, bone, dg) @ keys[('off', A)]
        elif world is None:
            world = parcel.matrix_world.copy()            # before the first grab: rest where placed
        # after release, 'world' simply stays at the last carried value -> object left where released
        keys[f] = world.copy()
    prev_q = None
    for f in range(f_start, f_end + 1):
        loc, q, sc = keys[f].decompose()
        if prev_q is not None and prev_q.dot(q) < 0: q.negate()   # keep quaternion sign continuous
        prev_q = q
        parcel.location, parcel.rotation_quaternion = loc, q
        parcel.keyframe_insert('location', frame=f)
        parcel.keyframe_insert('rotation_quaternion', frame=f)
    # then set every key's interpolation to 'LINEAR' (or 'CONSTANT') via the channelbag (5.x) to avoid
    # Bezier overshoot between per-frame keys; the parcel must have no parent (or account for matrix_parent_inverse).
```
- Keying every frame removes all interpolation pops. A placement offset designed from a hand "socket" (see below) can replace the grab-frame offset, so the parcel snaps exactly into the palm. In that case make the reach animation end with the hand at the parcel and keep the parcel still, so nothing visibly snaps.
- For a hand-over (worker 1 to worker 2, or hand to conveyor), add a second segment that starts at the handover frame. The offset is recomputed from the parcel's current world matrix, so there is no pop. A conveyor is just another "parent" whose matrix is a translation along the belt.
- Release onto a surface: in the final carry frames, the hand IK target (Q4) should already place the box at its resting height. The per-frame world bake then leaves it there. Sanity check: assert `|world_after_B.translation - surface_point| < 5 mm`.

**Pattern B: Child Of with influence switching (use this if live editing in the UI matters). Pitfalls and fixes:**
1. Add the constraint (`target=arm, subtarget='Bip01 R Hand'`). Set `scene.frame_set(A)`, then set the inverse directly: `con.inverse_matrix = (arm.matrix_world @ arm.pose.bones[b].matrix).inverted()` (evaluated values), or set `con.set_inverse_pending = True` and then call `bpy.context.view_layer.update()` while the scene is at frame A. With `inverse = parent(A)^-1`, the result at A equals the parcel's own basis, so there is no pop at the grab.
2. Key `con.influence` 0 at A-1 and 1 at A, then 1 at B and 0 at B+1 (or the same frame). **Set those f-curve keys to CONSTANT interpolation.** Otherwise influence blends across frames and the parcel drifts toward or away from the hand.
3. The inverse is a single, non-animatable matrix. Each grab of the same parcel by a different hand, or at a different time, needs its own Child Of constraint (or use pattern A).
4. Release pop: when influence goes to 0, the object falls back to its own basis transform (where it was before the grab). Before zeroing, evaluate the visual matrix at B (`parcel.matrix_world` with the constraint active) and key the basis to that value at B. **Key the basis CONSTANT** too. Otherwise the basis interpolates from its pre-grab key to its post-release key during the carry, and that change multiplies through the Child Of result, so the parcel slides in the hand.
5. Finally, bake to plain keys and strip the constraint for render robustness: `anim_utils.bake_action(parcel, action=None, frames=range(f0,f1+1), bake_options=BakeOptions(only_selected=False, do_pose=False, do_object=True, do_visual_keying=True, do_constraint_clear=True, do_parents_clear=False, do_clean=False, do_location=True, do_rotation=True, do_scale=False, do_bbone=False, do_custom_props=False))`. Note `bpy.ops.nla.bake` defaults to `bake_types={'POSE'}`. Use `{'OBJECT'}` for props, and it needs a selection/context, which is awkward in background mode.
- "Hand attach point" empty: create an Empty, set `parent=arm, parent_type='BONE', parent_bone='Bip01 R Hand'`, then **set its `matrix_world` explicitly after parenting** to the palm centre / grip frame (−Z = palm normal, +Y = finger direction is a convenient convention). Bone parenting is relative to the bone's tail and uses `matrix_parent_inverse`, so setting `location` directly lands in the wrong place (inferred from parent-inverse behaviour in the [manual's parent page](https://docs.blender.org/manual/en/latest/scene_layout/object/editing/parent.html); not explicitly verified). The socket's `matrix_world` is then the `hand_world` in pattern A, and it also works as a Copy Transforms or IK target.
- Copy Transforms (prop follows socket) has the same influence-switch pop problem as Child Of, but no inverse matrix. It suits the "always in hand" case (phone, scanner). The project's existing `people.grip_device` already handles fingers for devices.
- Do **not** parent or constrain a box to the hand while the same hand's IK targets the box. That is a dependency cycle (see Q2).

### Gaps
- I found no official statement on whether `set_inverse_pending` is evaluated correctly in `blender -b` background mode without a viewport redraw. Setting `inverse_matrix` explicitly from evaluated matrices sidesteps the question.
- I could not access the Blender StackExchange threads directly. The Child Of pitfalls above are synthesised from the manual and API plus the BlenderArtists and tracker reports.

---

## Q2. How do you drive two-hand IK to the sides of a box that is itself moving, without elbows flipping (pole targets, per-rig pole angle)?

### Takeaway
Put two socket empties on the box (left and right side faces) and point an IK constraint on each forearm at its socket (`chain_count=2`). Add a Copy Rotation (or IK `use_rotation`) for the wrist. Pole-target empties sit behind and outside each elbow and are parented to the pelvis or torso, **not** to the box. Compute `pole_angle` per arm from the rest pose with the known StackExchange formula; never hard-code ±90°. The box must be driven by something other than the hands (keys, a carry empty on the torso, or the matrix bake) to avoid a cycle.

### Cited Findings
- `KinematicConstraint` exposes `chain_count`, `iterations` ("Maximum number of solving iterations", 0–10000), `pole_angle` ("Pole rotation offset", −π..π), `pole_subtarget`, `use_stretch`, `use_tail`, and `weight`. PoseBone has `ik_stretch` and `lock_ik_x/y/z`. — [API: KinematicConstraint](https://docs.blender.org/api/current/bpy.types.KinematicConstraint.html); [API: PoseBone](https://docs.blender.org/api/current/bpy.types.PoseBone.html)
- Blender has no automatic pole-angle setting. Brecht Van Lommel said in 2014 it "would be good" to compute it automatically, but it was never built. — [bf-animsys mailing list 2014](https://archive.blender.org/lists/bf-animsys/2014-January/000130.html)
- The community-standard pole-angle calculation is Jerryno's Blender StackExchange answer (question 19754). It was reposted as a script on BlenderArtists, packaged as an add-on (SE answer 79087 and "pole angle fix add-on"), and is now a "Bone Math" extension with a right-click operator on the pole angle field (first release December 2025, Blender 4.5 LTS+). — [BlenderArtists: help rigging IK legs](https://blenderartists.org/t/help-rigging-ik-legs-wrong-rotation-problem/696448); [BlenderArtists: pole angle fix add-on](https://blenderartists.org/t/pole-angle-fix-add-on/687920); [Bone Math extension](https://extensions.blender.org/add-ons/bone-math/)
- The reposted scripts use 2.7x-era API in places (e.g. `*` instead of `@` for matrices). — same BlenderArtists threads (search summary)

### Inferences
**Pole angle, computed per arm from the rest pose (port of Jerryno's SE 19754 formula to 2.8+ `@` syntax; verify on one arm visually):**
```python
def signed_angle(u, v, normal):
    a = u.angle(v)
    if u.cross(v).angle(normal) < 1: a = -a
    return a

def pole_angle(arm, base_name, ik_name, pole_world):
    # base = upper arm, ik = forearm; all in armature space
    b = arm.pose.bones[base_name]; i = arm.pose.bones[ik_name]
    pole = arm.matrix_world.inverted() @ pole_world
    pole_normal = (i.tail - b.head).cross(pole - b.head)
    proj_axis = pole_normal.cross(b.tail - b.head)
    return signed_angle(b.x_axis, proj_axis, b.tail - b.head)
```
Run it in the rest pose, or with the arm slightly bent toward the pole. Set `con.pole_angle` to the result, then check that the elbow does not move when the constraint is enabled at the grab frame.

**Two-hand box setup:**
- Sockets: `box_sock_L` and `box_sock_R` are Empties parented normally to the box. They sit at the side-face centres, about 2–3 cm outside the surface so the palm's skin does not intersect the box, at 40–60 % of the box height. Orient them so the hand's palm axis faces the box centre.
- IK: on `Bip01 L Forearm` / `Bip01 R Forearm` set `target=box_sock_L`, `chain_count=2`, `use_stretch=False`, `iterations=200–500`, `pole_target=pole_L`. Wrist: Copy Rotation on `Bip01 L Hand` targeting the socket (world space), or IK with `use_rotation=True` and `orient_weight`.
- Poles: `pole_L` and `pole_R` are parented to the pelvis or spine bone (or to a torso empty). Place each about 0.3–0.5 m behind and slightly outside and below its elbow. When the poles ride with the torso, elbows stay consistent as the body turns. Poles parented to the box would swing with it, and that is a common flip cause.
- Anti-flip rules: (1) keep the target within ~95 % of upper-arm plus forearm length. A fully straight arm makes the pole plane degenerate and the elbow can snap, so clamp the box-to-shoulder distance in the procedural path or move the torso closer. (2) Never let a pole cross the shoulder–wrist line. (3) Animate `con.influence` 0→1 over 4–8 frames during the reach rather than switching it hard.
- Moving box: the box's own motion comes from keys (on a conveyor), from a "carry" empty parented to the torso or root during the carry, or from the matrix bake in Q1 applied to a torso socket. Box→hand plus hand-IK→box is a cycle, so Blender reports a dependency cycle and evaluation lags a frame (the "jitter").
- After setup, bake the arm bones to keys (`bake_action(arm, ..., do_pose=True, do_visual_keying=True, do_constraint_clear=True, only_selected=False)`) so renders are deterministic.

### Gaps
- Exact Rocketbox arm bone names, and whether there are forearm twist bones between forearm and hand, were **not verified** from a source. Inspect `arm.data.bones` in the actual file; Biped exports usually have `Bip01 L UpperArm`, `Bip01 L Forearm`, `Bip01 L Hand`. If the twist bones are deform bones, the IK chain must skip them or `chain_count` must change.
- No source covered IK behaviour with Rocketbox's 0.01-scaled armature object. Test that the pole and target distances behave once the object scale is applied (see Q4).

---

## Q3. Which retargeting tools are free/open-source and scriptable in Blender 5.x, and which are paid? Does Blender ship a retargeter?

### Takeaway
Blender 4.x and 5.x do **not** ship an automatic armature-to-armature retargeter. Built-ins are limited to Global Transform copy/paste/bake, action slots, NLA, and constraints. Free options are the Rokoko Blender plugin, the KBS-DEV "Retarget" extension (GPL-3.0, 5.0+ only, has a Mixamo preset and root-motion transfer), igelbox/blender-retarget (MIT, older), ReNim (GPL-3.0), Mixaify (Mixamo→Rigify), and the free tier of Expy Kit. Auto-Rig Pro Remap is paid ($50 full package). For a one-day headless Python job, a ~100-line custom world-space-delta retarget script (Q4) is the most controllable choice. The add-ons are UI-driven and none documents a Python API.

### Cited Findings
- I found no official Blender 5.1 release-notes entry for built-in animation retargeting. 5.1 coverage mentions faster armature evaluation and a new Geometry Nodes "Bone Info" node exposing rest pose and length. Old `retarget.py` code in the Blender archive dates from 2011 (GSoC era) and is not current. — [Search summary of 5.1 coverage: learn3dtutorials](https://www.learn3dtutorials.com/?p=9239); [digitalproduction 5.1 tag](https://digitalproduction.com/tag/blender-5-1-release-notes); [archive retarget.py](https://projects.blender.org/archive/blender-archive/commits/commit/4ef1e67ce8245e03ff41c00a09be98d65dfe49f5/release/scripts/modules/retarget.py)
- Global Transform (copy/paste/"Paste and Bake"/relative/fix-to-camera) is a manual per-bone world-space tool, not a whole-skeleton retargeter. — [Manual: Global Transform](https://docs.blender.org/manual/en/latest/editors/3dview/animation/copy_global_transform.html)
- **Rokoko Studio Live for Blender (free):** Rokoko's support article says retargeting is not a paid feature and needs no premium account (the article returned 403 when fetched directly; claim via search summary). Its GitHub describes streaming, recording, and retargeting with an "Auto Detect" bone-list fill, and requires Blender 2.80+. Rokoko's own guide calls the feature fairly simple, "mainly for previewing mocap", and a third-party CGDive review says it lags behind Blender releases. — [Rokoko support: Retarget in Blender](https://support.rokoko.com/hc/en-us/articles/4410463481489-Retarget-an-animation-in-Blender); [Rokoko retargeting guide](https://support.rokoko.com/hc/en-us/articles/14843726304657); [GitHub fork of rokoko-studio-live-blender](https://github.com/Atlas-3D-Artist/rokoko-studio-live-blender); [CGDive add-on overview](https://cgdivetest.super.site/sub-categories/blender-retargeting-addons)
- **Retarget (KBS-DEV), extensions.blender.org:** GPL-3.0-or-later, "compatible only with Blender 5 and higher", latest version 5.2.0. Presets for Mixamo, Unreal, VRoid, MMD, Daz, Auto-Rig Pro; conversion to Rigify; "Add Root Bone" and "Transfer Root Motion"; "Bake Constrained Actions". Expy Kit presets can be reused by editing the preset's second line (`expykit_retarget` → `retarget_retarget`). One reviewer said it broke on 5.1 and the developer replied it works for them, which is unresolved. No Python API is documented. — [Blender Extensions: Retarget](https://extensions.blender.org/add-ons/retarget/); [reviews](https://extensions.blender.org/add-ons/retarget/reviews/)
- **Humanoid Remap Studio** (extensions.blender.org) requires Blender 5.1+ and two humanoid armatures. Licence not captured. — [Blender Extensions: Humanoid Remap Studio](https://extensions.blender.org/add-ons/humanoid-remap-studio/)
- **igelbox/blender-retarget:** MIT. Live "link rotation / link location" bone sync, then bake. Needs the target posed to match the source first. Supports 2.80+ except 2.82, and 5.x support is not stated. — [GitHub igelbox/blender-retarget](https://github.com/igelbox/blender-retarget)
- **ReNim:** retargeting add-on, GPL-3.0 per its README. — [GitHub anasrar/ReNim](https://github.com/anasrar/ReNim) (via search summary)
- **Mixaify:** community Mixamo→Rigify retarget: both rigs in rest pose, scale the Mixamo rig to match, use the panel, then bake. — [GitHub netherby/mixaify-retarget](https://github.com/netherby/mixaify-retarget)
- **Expy Kit:** distributed on Gumroad as a free `ExpyKit_v0.6.1.zip` plus a paid `..._premium.zip`. The licence was not stated in what I could retrieve. — [Gumroad: Expy Kit](https://ballsandninjas.gumroad.com/l/xotibs)
- **Auto-Rig Pro (paid):** the Remap tool is in the $50 full package (the $25 tier is core only; multi-seat $162/$227). "Retargeting of any armature action to another one, with different bone names and bone orientations". A listing shows Blender 2.93–5.1, and 5.0 users hit breakage on older ARP versions. — [Superhive: Auto-Rig Pro](https://superhivemarket.com/products/auto-rig-pro?variant=265)
- Copying actions between rigs with different bone names fails silently because F-curve paths are name-based (`pose.bones["Name"]...`). — [BlenderArtists: unable to copy animation](https://blenderartists.org/t/unable-to-copy-animation/1460941)

### Inferences
- Licence fit with the project rule (CC0/CC BY/MIT/OFL output): add-ons are tools rather than shipped assets, so their GPL licence does not affect rendered frames. Still, a custom script avoids add-on version drift, which matters given the Rokoko and ARP breakage reports on new Blender versions and the deadline.
- If an add-on is used anyway, the KBS-DEV Retarget extension is the best free candidate for 5.x: it has a Mixamo preset and root motion, is GPL, and is on the official platform. It would need a custom Bip01 preset, and since it is UI-operator based, headless use needs `temp_override` context work. Budget time to test this.

### Gaps
- Expy Kit's licence and its 5.x compatibility were not confirmed. Its GitHub repository was not found in search.
- Whether the Rokoko plugin currently works on Blender 5.x was not confirmed.
- No add-on documents a stable Python API for headless retargeting.

---

## Q4. How do you retarget Mixamo FBX / CMU BVH onto a 3ds Max Biped-style (Rocketbox `Bip01 …`) skeleton, and what are the known pitfalls?

### Takeaway
Retarget in **world/armature space with a reference-pose offset per mapped bone**: `R_tgt(t) = (R_src(t) @ R_src_ref⁻¹) @ R_tgt_ref`. Here `R_*_ref` are the bones' armature-space orientations **when both skeletons stand in the same body pose** (pose the Rocketbox rig into Mixamo's T-pose once and record it). Write the result with `pose_bone.matrix = …`, processing parents before children and updating between levels. The formula in the brief, `q_t = rest_t⁻¹ · rest_s · q_s`, is incomplete. The correct local-space form is the conjugation `q_t = (rest_t⁻¹ · rest_s) · q_s · (rest_s⁻¹ · rest_t)`, and it only holds when both rest poses are the same body pose and the parent chains map 1:1. Translation goes only on the root (hips → `Bip01`), scaled by the hip-height ratio.

### Cited Findings
- Microsoft Rocketbox: MIT licence (from 12/2020). 417 compatible animations in `Assets/Animations` (4/2022) and a separate Movebox library for animating the avatars. The Unity import tool "set[s] avatars into T-pose" and reorganises bones for the Unity humanoid, which implies the shipped bind pose is **not** a clean T-pose. The fix script `FixRocketboxMaxImport.cs` corrects 3ds Max materials. LODs are named hipoly/midpoly/lowpoly/ultralowpoly. The README has no Blender instructions and no scale notes. — [GitHub microsoft/Microsoft-Rocketbox](https://github.com/microsoft/Microsoft-Rocketbox)
- Blender FBX importer options relevant to Max/Biped rigs: `global_scale`, `use_manual_orientation`, `axis_forward='-Z'`, `axis_up='Y'`, `ignore_leaf_bones` (drop the end bones that only mark length), `force_connect_children`, `automatic_bone_orientation` ("try to align the major bone axis with the bone children"), `primary_bone_axis='Y'`, `secondary_bone_axis='X'`, `use_prepost_rot=True`, `use_anim`. `bake_space_transform` (Apply Transform) is "experimental … known to be broken with armatures/animations". — [API: bpy.ops.import_scene.fbx](https://docs.blender.org/api/current/bpy.ops.import_scene.html)
- Known FBX/Blender scale issues: armatures exported or imported with cm-based units get a 0.01 object scale ("the skeleton will be 0.01 the scale"), a 0.01 unit scene scale "causes a lot of issues … in addons", and some files import with bone scale not matching mesh scale. — [Blender issue #99075](https://developer.blender.org/T99075); [blender-addons #51704](https://projects.blender.org/blender/blender-addons/issues/51704); [blender-addons #104753](https://projects.blender.org/blender/blender-addons/issues/104753)
- Mixamo FBX into Blender typically arrives with a ×100 / 0.01 scale relationship that must be corrected. Mixamo bone names carry the `mixamorig:` prefix, so any bone map needs it. — [glTFRuntime retargeting doc](https://github.com/rdeioris/glTFRuntime-docs/blob/master/Tutorials/RetargetingRPMAndMixamo.md); [vrm-mixamo-retarget README](https://cdn.jsdelivr.net/npm/vrm-mixamo-retarget@1.0.3/README.md)
- `Object.convert_space(pose_bone=…, matrix=…, from_space, to_space)` converts matrices between WORLD/POSE/LOCAL spaces for bones. Use it, or assign `pose_bone.matrix` (armature space), instead of hand-deriving the parent chain. — [API: Object.convert_space](https://docs.blender.org/api/current/bpy.types.Object.html)
- Add-ons that retarget generally require posing the target to match the source first (igelbox) or putting both rigs in rest pose and matching scale (Mixaify). This is the same reference-pose requirement as the formula above. — [igelbox/blender-retarget](https://github.com/igelbox/blender-retarget); [Mixaify](https://github.com/netherby/mixaify-retarget)

### Inferences
**Headless retarget script outline (Mixamo FBX or BVH → Rocketbox Bip01):**
```python
MAP = {  # source -> target (verify names in both files!)
 'mixamorig:Hips':'Bip01 Pelvis', 'mixamorig:Spine':'Bip01 Spine', 'mixamorig:Spine1':'Bip01 Spine1',
 'mixamorig:Spine2':'Bip01 Spine2', 'mixamorig:Neck':'Bip01 Neck', 'mixamorig:Head':'Bip01 Head',
 'mixamorig:LeftShoulder':'Bip01 L Clavicle', 'mixamorig:LeftArm':'Bip01 L UpperArm',
 'mixamorig:LeftForeArm':'Bip01 L Forearm', 'mixamorig:LeftHand':'Bip01 L Hand',
 'mixamorig:LeftUpLeg':'Bip01 L Thigh', 'mixamorig:LeftLeg':'Bip01 L Calf', 'mixamorig:LeftFoot':'Bip01 L Foot',
 'mixamorig:LeftToeBase':'Bip01 L Toe0', ...mirror for Right..., fingers optional }
# 1) Import both; apply the armature object scale on a COPY or account for it via matrix_world (keep 0.01 if the mesh is bound to it).
# 2) Reference pose: put SOURCE at frame of its T-pose (Mixamo rest is T-pose; for BVH use frame 0 or a hand-built T-pose),
#    put TARGET into the same T-pose (rotate Bip01 UpperArms/Clavicles until arms are horizontal, legs straight), record
#    Rs_ref[b] = src.matrix_world @ src.pose.bones[b].matrix  (3x3 rotation part), Rt_ref[b] likewise (world space).
# 3) For each frame: frame_set(f); for target bones in hierarchy order (parents first):
#       Rs = (src.matrix_world @ src.pose.bones[s].matrix).to_3x3()
#       Rt = (Rs @ Rs_ref[s].inverted()) @ Rt_ref[t]           # world-space delta transfer
#       Mt_world = Matrix.LocRotScale(current_target_head_world, Rt.to_quaternion(), None)
#       tgt.pose.bones[t].matrix = tgt.matrix_world.inverted() @ Mt_world   # Blender solves the local basis
#       bpy.context.view_layer.update()   # needed so children see the new parent pose (per hierarchy level)
#       keyframe rotation_quaternion (make sign continuous)
#    Root: pelvis/Bip01 location = tgt_hip_ref + (src_hip(t) - src_hip_ref) * (tgt_hip_height / src_hip_height),
#    in world space -> convert; put XY on 'Bip01' (Biped COM root) and keep Z there too, Pelvis rotation only.
# 4) Unmapped target bones (twist bones, Bip01 Spine3 if present, ponytail, etc.) stay at rest/reference rotation.
```
- Why world-space delta beats the local-quaternion formula: Biped bones have different local axes (Max convention: bone length along local X) from Mixamo/Blender (along Y). Rocketbox also has extra or intermediate bones (`Bip01` → `Bip01 Pelvis` → `Bip01 Spine` …) and a non-T bind pose. The world-delta method is insensitive to bone roll and axis conventions, and handles intermediate bones as long as they stay at the reference pose.
- If you insist on local quaternions, use the conjugated form with **armature-space** rests (`bone.matrix_local`) and only when parent chains map 1:1: `C = rest_s⁻¹ @ rest_t`, `q_t = C⁻¹ @ q_s @ C`. The brief's `rest_t⁻¹·rest_s·q_s` leaves a constant rotation offset on every frame.
- Pitfalls to check (inferred, not source-confirmed for Rocketbox specifically):
  - **0.01 armature object scale and cm units.** World-space math through `matrix_world` handles this automatically, but anything written as `location` in bone-local space is scaled ×100. Root translation must be converted with `tgt.matrix_world.inverted()`, and IK distances or poles in Q2 are also affected. Don't "Apply Scale" on a skinned rig unless you also apply it to the mesh and re-check the Armature modifier.
  - **Bone roll / FBX axis options.** Importing with `automatic_bone_orientation=True` changes rest orientations, which is harmless for the world-delta method but changes local values. Keep `ignore_leaf_bones=True` on Mixamo files to avoid `_end` bones.
  - **Max pre/post-rotation.** Keep `use_prepost_rot=True` (default) or the bind pose comes in twisted.
  - **Quaternion sign flips** between frames when converting from matrices: negate when `dot(prev, q) < 0`.
  - **BVH (CMU):** `bpy.ops.import_anim.bvh` with `global_scale` (CMU units are roughly inches×(1/0.45), often scaled by 0.056). Rotation order is per-file Euler. The CMU skeleton's frame 0 is not a T-pose, so build the reference pose by hand.
  - **Mixamo "In Place"** clips remove hip XY, so root motion must come from the scene mover (the project already stores a per-frame `root_fwd` curve).
- Validate the retarget numerically: compare the source and target hand and foot world-position trajectories normalised by limb length (error under ~3 cm after scaling), and render a contact sheet.

### Gaps
- No primary source documents the Rocketbox skeleton for Blender (exact bone list, whether `Bip01 Spine3` / `Bip01 Neck1` / twist / `Bip01 Footsteps` bones exist, bind pose angles, 0.01 scale on import). Verify by inspecting an imported avatar. Microsoft's README only covers Unity and Unreal.
- No source confirmed whether Blender 5.x's FBX import is still the Python add-on or has moved to a new C++ importer with different option names. Check `bpy.ops.import_scene.fbx` versus `bpy.ops.wm.fbx_import` in the installed build.

---

## Q5. Foot locking, procedural pick-and-place layered over idle/locomotion, torso lean, NLA crossfades and loop matching

### Takeaway
Do all of this with constraints whose influence is keyed, then bake. **Foot lock**: detect stance frames (low foot height and speed), pin an IK target empty at the averaged stance position, and key the leg IK influence on during stance with 2–4-frame ramps. **Pick-and-place**: key an IK target empty through reach → grasp → lift (arc) → carry → place → release over an idle or walk clip, blend in via IK influence, and add a small keyed spine lean. **NLA**: `blend_type`, `blend_in/out`, `use_auto_blend`, `extrapolation` and per-strip `action_slot` handle crossfades and layering. Make loops seamless by picking matching frames or with Cycles modifiers.

### Cited Findings
- NLA strip properties available from Python include `action_slot`, `blend_in`, `blend_out`, `blend_type`, `extrapolation`, `use_auto_blend` and `use_sync_length` (plus `repeat` and `scale`). — [API: NlaStrip](https://docs.blender.org/api/current/bpy.types.NlaStrip.html)
- Since 4.4, actions carry slots, and an animated ID uses an action plus a slot, so NLA strips likewise reference an `action_slot`. — [Manual: Actions › Slots](https://docs.blender.org/manual/en/latest/animation/actions.html); [API: NlaStrip.action_slot](https://docs.blender.org/api/current/bpy.types.NlaStrip.html)
- "Fix to Camera" and "Paste and Bake" in Global Transform generate keys typed "Generated", which can be re-run and removed. The same idea applies to world-space locking of a bone (e.g. pinning a foot) across a key range. — [Manual: Global Transform](https://docs.blender.org/manual/en/latest/editors/3dview/animation/copy_global_transform.html)
- Constraint baking for pose bones: `BakeOptions(do_pose=True, do_visual_keying=True, do_constraint_clear=True)`. — [API: anim_utils](https://docs.blender.org/api/current/bpy_extras.anim_utils.html)

### Inferences
**Foot lock (post-process on the retargeted, baked clip):**
1. For each foot (`Bip01 L Foot`, or the toe for heel-off), sample the world position per frame. Mark stance where `z < z_min + 2 cm` and horizontal speed < ~0.15 m/s (tune), merging gaps of 1–2 frames.
2. For each stance interval, set the lock position to the mean XY at the stance-frame z.
3. Add IK on `Bip01 L Calf` (`chain_count=2`) with an empty target keyed to the lock position during stance and to the free foot position (from the clip) otherwise. Add a pole empty in front of the knee, parented to the pelvis, with the pole angle from Q2's formula. Key influence 0→1 over 2–3 frames before contact and 1→0 over 2–3 frames at heel-off. Add Copy Rotation on the foot to keep the sole orientation, or leave the clip's foot rotation alone.
4. Bake (`do_pose=True, do_visual_keying=True, do_constraint_clear=True`).
- With movers driven by `root_fwd`, sliding usually means mover speed ≠ stride/cycle. Check that stance-foot world speed is about 0 before reaching for IK. Retiming the mover is cheaper than IK fixing.

**Procedural pick-and-place over a base clip (one developer-day pattern):**
- Base layer: idle or walk on NLA track 0 (`blend_type='REPLACE'`). Arm IK constraints exist on the rig with influence keyed (0 outside the task, 1 during).
- Key the hand target empties (both hands for a box) at phase frames. Example for 30 fps, a 2 kg parcel from a belt to a cage:
  - reach: 12–18 frames, ease-in-out, ending 3–5 cm short of the socket;
  - grasp: 4–6 frames closing onto the socket (fingers curl via the project's grip solver);
  - lift: 8–12 frames, vertical first by about 5–10 cm;
  - carry: Bezier arc to the place point; keep the box within ~35 cm of the sternum;
  - place: 8–12 frames with a slow-in at the end;
  - release: 4–6 frames, hands back 5 cm and up, then IK influence back to 0 over 8–10 frames.
  These durations are design estimates, not sourced.
- The parcel follows the hand sockets via the matrix bake (Q1, pattern A). The parcel is "attached" only between the grasp end and the release start.
- Torso: key extra rotation on `Bip01 Spine` / `Spine1` / `Spine2` on a top NLA track with `blend_type='ADD'`, or 'COMBINE' for quaternion-correct additive layering. Use forward flexion of about 10–25° split across the spine bones for low reaches (belt height under ~80 cm), plus a pelvis drop and knee bend via the leg IK targets for floor lifts. Rotate toward the target about the spine Z to avoid pure arm reaching across the body. Also derived design guidance; validate visually against reference footage per the realism rule.
- Bake the whole stack per character to a single action for render determinism and speed.

**NLA crossfades and loops (Python):**
```python
ad = arm.animation_data or arm.animation_data_create()
t0 = ad.nla_tracks.new(); s0 = t0.strips.new('walk', 1, act_walk)
t1 = ad.nla_tracks.new(); s1 = t1.strips.new('pick', 90, act_pick)   # overlaps walk end
for s, a in ((s0, act_walk), (s1, act_pick)):
    if s.action_slot is None and a.slots: s.action_slot = a.slots[0]  # 4.4+/5.x: make sure a slot is bound
s1.blend_in = 10; s1.blend_out = 10; s1.blend_type = 'REPLACE'
s0.extrapolation = 'HOLD_FORWARD'    # keep base pose under the fade
s0.repeat = 4                        # loop a seamless walk window
ad.action = None                     # don't let the active action override the NLA stack
```
- Loop matching: choose a window whose first and last poses match (as was done with the Push frames 62–162 window). Compare all bone quaternions and hip height between candidate start/end frames and pick the minimum-error pair. Remove the last frame (it duplicates the first), and apply a Cycles F-modifier or `strip.repeat`. For residual mismatch, blend a linear correction over the last N frames.
- Crossfading two locomotion clips needs phase alignment: align the foot-contact frames of both clips before overlapping, or the feet scissor during the blend.

### Gaps
- I found no Blender-specific primary source for foot-lock or contact-detection thresholds, or for reach/carry phase durations. The numbers above are engineering estimates and should be validated against reference video, as the project's no-guessing rule requires.
- Not verified: whether `NlaStrip.action_slot` is auto-assigned by `strips.new()` in 5.x, so the code sets it defensively. Also not verified: whether 'COMBINE' blending behaves as expected for quaternion bones in 5.x.
- Academic work on procedural reaching (e.g. data-driven reach and grasp synthesis) was not surveyed in this pass. The IK-plus-keyed-target approach was chosen for one-day implementability.
