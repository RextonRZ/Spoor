"""The parcel as a real object in the Blender hub (reviewer 01:15, Rexton: "the carton must be IN the 3D scene, not a
sticker on top"). A marker of what the evidence says, not the simulation's own carton (that stays hidden with the
rest of Flow): the measured size from the tunnel (25.5 x 18.3 x 10.2 cm), cardboard a little brighter than the real
cartons, a white label and tape on top, a thin indigo rim so it reads at the drone's distance, and a soft contact
shadow on whatever it rests on (a belt, the floor; carried, the shadow falls on the floor below it).

Used by tour_render.py (it moves along route_path.py) and spin_render.py (it sits at the place's step).
"""
import math

import bpy

SIZE = (0.255, 0.183, 0.102)   # x along the heading, y across, z up (metres)
CARRIED_Z = 1.0                # the carton's middle when carried by hand
RIM = (0.39, 0.40, 0.95)       # indigo, the app's accent


def _mat(name, base, emit=None, strength=0.0, alpha=None, cull=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = 0.8
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    if alpha is not None:
        b.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    m.use_backface_culling = cull
    return m


def _box(name, size, loc, mat, parent):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    o.parent = parent
    return o


def make(collection=None):
    """An empty 'carton_rig' (move and turn this) with the carton, its rim and its shadow under it."""
    rig = bpy.data.objects.new("carton_rig", None)
    (collection or bpy.context.scene.collection).objects.link(rig)
    sx, sy, sz = SIZE
    card = _mat("carton_card", (0.86, 0.60, 0.32), emit=(0.86, 0.60, 0.32), strength=0.12)
    white = _mat("carton_label", (0.95, 0.95, 0.93), emit=(0.95, 0.95, 0.93), strength=0.2)
    tape = _mat("carton_tape", (0.93, 0.86, 0.70))
    body = _box("carton_body", (sx, sy, sz), (0, 0, 0), card, rig)
    _box("carton_tape", (sx * 1.002, 0.045, 0.004), (0, 0, sz / 2), tape, rig)
    _box("carton_label", (0.10, 0.07, 0.003), (0.05, 0.0, sz / 2 + 0.002), white, rig)
    # the rim: the body's shell pushed out a little, its inside faces only (an outline from any side)
    rim = body.copy()
    rim.data = body.data.copy()
    rim.name = "carton_rim"
    rim.data.materials.clear()
    rim.data.materials.append(_mat("carton_rim", RIM, emit=RIM, strength=2.2, cull=True))  # brighter turns white under AgX
    sol = rim.modifiers.new("shell", "SOLIDIFY")
    sol.thickness, sol.offset, sol.use_flip_normals = 0.026, 1.0, True
    (collection or bpy.context.scene.collection).objects.link(rim)
    rim.parent = rig
    # the contact shadow: a soft dark ellipse under the carton, on the surface it rests on
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    sh = bpy.context.active_object
    sh.name = "carton_shadow"
    sh.scale = (sx * 1.9, sy * 2.2, 1)
    bpy.ops.object.transform_apply(scale=True)
    m = bpy.data.materials.new("carton_shadow")
    m.use_nodes = True
    m.surface_render_method = "BLENDED"
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc, gr, ramp = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeTexGradient"), nt.nodes.new("ShaderNodeValToRGB")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = (-0.5, -0.5, 0)  # the gradient's centre on the plane's centre
    gr.gradient_type = "SPHERICAL"    # 1 at the middle, 0.5 at the plane's edge
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.5, 1.0
    ramp.color_ramp.elements[0].color, ramp.color_ramp.elements[1].color = (0, 0, 0, 1), (1, 1, 1, 1)
    tr, mix, black = nt.nodes.new("ShaderNodeBsdfTransparent"), nt.nodes.new("ShaderNodeMixShader"), nt.nodes.new("ShaderNodeEmission")
    black.inputs["Color"].default_value = (0, 0, 0, 1)
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation, inv.inputs[1].default_value = "MULTIPLY", 0.55
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], gr.inputs["Vector"])
    nt.links.new(gr.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], inv.inputs[0])      # darkest in the middle, gone at the edge, times 0.55
    nt.links.new(inv.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(black.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    sh.data.materials.append(m)
    sh.parent = rig
    return rig


def place(rig, x, y, z, yaw, support_z, scale=1.0):
    """Put the carton's middle at (x, y, z), turned to yaw (radians), its shadow on the surface at support_z."""
    rig.location = (x, y, z)
    rig.rotation_euler = (0, 0, yaw)
    rig.scale = (scale, scale, scale)
    for c in rig.children:
        if c.name.startswith("carton_shadow"):
            c.location = (0, 0, (support_z - z) / scale + 0.004)


def heading(a, b, default=0.0):
    return math.atan2(b[1] - a[1], b[0] - a[0]) if math.dist(a, b) > 1e-6 else default
