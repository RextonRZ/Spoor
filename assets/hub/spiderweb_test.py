"""Rexton's 'spiderweb' at dock D01 (review mesh_hygiene): topology or moire? Same view rendered as the QA workbench
(texture + cavity, FXAA), workbench without textures, and EEVEE at 2 / 16 / 64 spp, plus 2 spp with the camera moved
5 cm. Lines fixed on the surface = topology; lines that change with samples / move with the camera = moire.

  blender -b --factory-startup build/hub_dressed_lit.blend -P assets/hub/spiderweb_test.py -- --out <dir>
"""
import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
OUT = Path(a.out)
OUT.mkdir(parents=True, exist_ok=True)
sc = bpy.context.scene
sc.render.image_settings.file_format = "PNG"
sc.render.resolution_x, sc.render.resolution_y = 960, 720
cam = bpy.data.objects.new("sw_cam", bpy.data.cameras.new("sw_cam"))
cam.data.lens = 24
sc.collection.objects.link(cam)
sc.camera = cam
target = Vector((0.15, 7.6, 2.2))  # the closed D01 shutter and its housing, seen from the hall at a grazing angle
eye = Vector((2.6, 4.9, 1.55))


def shoot(tag, move=Vector()):
    cam.location = eye + move
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = str(OUT / f"{tag}.png")
    bpy.ops.render.render(write_still=True)
    print("SW", tag, flush=True)


engine0 = sc.render.engine
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light, sh.color_type = "STUDIO", "TEXTURE"
sh.show_cavity, sh.cavity_type, sh.show_shadows = True, "BOTH", True
sc.display.render_aa = "FXAA"
shoot("wb_qa_texture_cavity")
sh.color_type = "MATERIAL"
shoot("wb_material_no_texture")
sh.color_type, sh.show_cavity = "TEXTURE", False
shoot("wb_texture_no_cavity")
sc.display.render_aa = "32"
shoot("wb_texture_32aa")
sc.render.engine = engine0 if engine0 != "BLENDER_WORKBENCH" else "BLENDER_EEVEE_NEXT"
for spp in (2, 16, 64):
    sc.eevee.taa_render_samples = spp
    shoot(f"eevee_{spp:02d}spp")
sc.eevee.taa_render_samples = 2
shoot("eevee_02spp_moved5cm", Vector((0.05, 0.0, 0.0)))
