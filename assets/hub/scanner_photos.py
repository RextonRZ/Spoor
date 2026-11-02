"""The DWS tunnel's own camera (scan checkpoints C, Rexton 31 Oct): SCANNER_TUNNEL_A inside line A's tunnel, looking
straight down at the belt between the LED bars, as a DWS image camera does. NOT a CCTV camera: made here, used for
these stills only, never saved into a blend.

  blender -b <S2.blend> -P assets/hub/scanner_photos.py -- --all  [--res 1280x720] [--samples 16]
      one still per parcel with a tunnel read in the window -> assets/hub/build/scanner/<parcel_id>.jpg, plus the story
      parcel (read before the window: its own box and label put on the empty belt, marked "from recorded history");
      then scanner_photo is added to those tunnel records in events_scan_simulated_S2(.jsonl, _long.jsonl)
  py -X utf8 assets/hub/scanner_photos.py --finish
      (Blender's Python has no Pillow) stamps the stills from the manifest and writes scanner_photo into the logs
  blender -b <W1.blend> -P assets/hub/scanner_photos.py -- --replay --scenario W1
      the story parcel replayed in W1 rides the tunnel: its real still at its read (replaces the "from recorded
      history" stand-in; then --finish, which stamps it from the S2 log's record of that read)
  blender -b <S2.blend> -P assets/hub/scanner_photos.py -- --tile
      the DWS screen's camera tile: one window read (a kraft box), raw, + its record -> build/signs/dws_tile_A.png/.json
      (make_dws_screen.py puts both on the screen)

Each still carries the DWS stamp (unit, device time, barcode) as tunnel images do. Line B is unstaffed in S2 (no
reads), so SCANNER_TUNNEL_B is not made.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

try:
    import bpy
    from mathutils import Matrix, Vector
except ImportError:  # --finish (system Python)
    bpy = None

HUB = Path(__file__).resolve().parent
BUILD = HUB / "build"
ap = argparse.ArgumentParser()
ap.add_argument("--all", action="store_true")
ap.add_argument("--tile", action="store_true")
ap.add_argument("--finish", action="store_true")
ap.add_argument("--replay", action="store_true", help="W1/W2 blend: the replayed story parcel at its real read")
ap.add_argument("--scenario", default="S2")
ap.add_argument("--res", default="1280x720")
ap.add_argument("--samples", type=int, default=16)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
S = a.scenario
sc = bpy.context.scene if bpy else None
OUT = BUILD / "scanner"
OUT.mkdir(parents=True, exist_ok=True)
CAM_XY, CAM_Z = (20.95, 9.5), 2.75  # between the 3rd and 4th LED bar (x 20.7-20.9, 21.2-21.4), under the roof

log_p = BUILD / "sim" / f"events_scan_simulated_{S}.jsonl"
rows = [json.loads(l) for l in log_p.read_text(encoding="utf-8").splitlines() if l.strip()]
truth = [json.loads(l) for l in (BUILD / "truth" / f"events_truth_{S}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
assert len(rows) == len(truth)
ft = json.loads((BUILD / "truth" / f"flow_truth_{S}.json").read_text(encoding="utf-8"))
by_pid = {p["parcel_id"]: p for p in ft["parcels"] if p.get("parcel_id")}
scen = json.loads((BUILD / "truth" / f"scenario_{S}.json").read_text(encoding="utf-8"))
F_N = int(round(float(scen["seconds"]) * 10))


def camera():
    cam = bpy.data.objects.new("SCANNER_TUNNEL_A", bpy.data.cameras.new("SCANNER_TUNNEL_A"))
    cam.data.lens, cam.data.sensor_width, cam.data.clip_start = 40.0, 36.0, 0.05  # ~1.1 x 0.63 m of belt at 1.25 m
    cam.location = (*CAM_XY, CAM_Z)
    cam.rotation_euler = (0.0, 0.0, 0.0)  # straight down, belt travel (+x) across the picture
    sc.collection.objects.link(cam)
    sc.camera = cam
    rx, ry = (int(v) for v in a.res.split("x"))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
    sc.render.image_settings.file_format = "PNG"
    if hasattr(sc, "eevee"):
        sc.eevee.taa_render_samples = a.samples
    return cam


def under_camera(p, f_read):
    """The window frame its centre passes closest under the camera, at or before the exit read."""
    tr = {int(k): v for k, v in p["track"].items()}
    cand = [f for f in range(max(1, f_read - 40), min(F_N, f_read) + 1) if f in tr and abs(tr[f][1] - CAM_XY[1]) < 0.5]
    return min(cand, key=lambda f: abs(tr[f][0] - CAM_XY[0])) if cand else None


def stamp(png, jpg, lines, history=False):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(im)
    try:
        fnt = ImageFont.truetype("arial.ttf", 22)
        big = ImageFont.truetype("arialbd.ttf", 30)
    except OSError:
        fnt = big = ImageFont.load_default()
    d.rectangle([0, im.height - 40, im.width, im.height], fill=(0, 0, 0))
    d.text((12, im.height - 33), "   ".join(lines), font=fnt, fill=(235, 235, 235))
    if history:
        d.rectangle([0, 0, 560, 48], fill=(150, 20, 20))
        d.text((12, 8), "FROM RECORDED HISTORY", font=big, fill=(255, 255, 255))
    im.save(jpg, quality=90)


def render(path):
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def reads_in_window():
    out = []
    for r, t in zip(rows, truth):
        if r["event"] == "tunnel_read" and r.get("scan_point") == "SP-TUNNEL" and r.get("parcel_id") in by_pid \
                and 0.0 <= t["true_t_s"] <= F_N / 10.0:
            out.append((r, 1 + int(round(t["true_t_s"] * 10))))
    return out


def story_still(cam):
    """The story parcel's own box and label on the empty belt under the camera (it was read 20 min before the
    window: no frame of the window shows it in the tunnel)."""
    pid, obn = scen["story_parcel"], scen["story_object"]
    rec = next((r for r in rows if r["event"] == "tunnel_read" and r.get("parcel_id") == pid), None)
    ob = sc.objects.get(obn)
    if rec is None or ob is None:
        return None
    # a window frame with nothing in the camera's patch of belt
    tracks = [{int(k): v for k, v in p["track"].items()} for p in ft["parcels"]]
    f = next(f for f in range(1, F_N + 1) if all(not (f in t and abs(t[f][0] - CAM_XY[0]) < 0.9 and abs(t[f][1] - CAM_XY[1]) < 0.6)
                                                 for t in tracks))
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ok, loc, *_ = sc.ray_cast(dg, Vector((*CAM_XY, 2.6)), Vector((0, 0, -1)), distance=2.0)
    belt_z = loc.z if ok else 1.5
    keep = (ob.matrix_world.copy(), ob.hide_render, ob.animation_data.action if ob.animation_data else None)
    if ob.animation_data:
        ob.animation_data.action = None
    ob.hide_render = False
    ob.matrix_world = Matrix.Translation((CAM_XY[0] + 0.05, CAM_XY[1] - 0.04, belt_z)) @ Matrix.Rotation(0.12, 4, "Z") \
        @ keep[0].to_3x3().normalized().to_4x4()  # (its own pose's tilt kept: a carton lies flat)
    bpy.context.view_layer.update()
    lo = min((ob.matrix_world @ Vector(c)).z for c in ob.bound_box)
    ob.matrix_world = Matrix.Translation((0, 0, belt_z - lo)) @ ob.matrix_world
    render(OUT / f"_{pid}.png")
    ob.matrix_world, ob.hide_render = keep[0], keep[1]
    if keep[2] is not None:
        ob.animation_data.action = keep[2]
    return pid


def finish():
    """Stamp the rendered stills (manifest) and write scanner_photo on those tunnel records, both logs."""
    man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    rec = {r["parcel_id"]: r for r in rows if r["event"] == "tunnel_read" and r.get("parcel_id")}
    made = {}
    for pid, hist in man.items():
        raw = OUT / f"_{pid}.png"
        if not raw.exists() or pid not in rec:
            continue
        stamp(raw, OUT / f"{pid}.jpg", ["DWS-01", rec[pid]["time"].replace("T", " ")[:23], pid], history=hist)
        raw.unlink()
        made[pid] = f"scanner/{pid}.jpg"
    for lp in (log_p, BUILD / "sim" / f"events_scan_simulated_{S}_long.jsonl"):
        if not lp.exists():
            continue
        out, n = [], 0
        for l in lp.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                if r["event"] == "tunnel_read" and r.get("parcel_id") in made:
                    r["scanner_photo"] = made[r["parcel_id"]]
                    n += 1
                l = json.dumps(r)
            out.append(l)
        lp.write_text("\n".join(out) + "\n", encoding="utf-8")
        print("LOG", lp.name, "scanner_photo on", n, "records")
    print("SCANNER stills", len(made))


if a.finish:
    finish()
    sys.exit(0)
cam = camera()
if a.tile:
    cands = [(r, f) for r, f in reads_in_window() if by_pid[r["parcel_id"]].get("kind") == "box"]
    r, f_read = cands[len(cands) // 2]
    f = under_camera(by_pid[r["parcel_id"]], f_read)
    sc.frame_set(f)
    render(BUILD / "signs" / "dws_tile_A.png")
    (BUILD / "signs" / "dws_tile_A.json").write_text(json.dumps({k: r.get(k) for k in (
        "parcel_id", "barcode", "time", "weight_kg", "length_cm", "width_cm", "height_cm", "dim_weight_kg",
        "destination_chute", "dims_mm", "weight_g")} | {"truth_chute": by_pid[r["parcel_id"]].get("target_chute")},
        indent=1), encoding="utf-8")
    print("TILE", r["parcel_id"], "frame", f, flush=True)
elif a.replay:  # the replayed logged parcel (truth/replay_<S>.json) physically rides the tunnel: its real still
    rp = json.loads((BUILD / "truth" / f"replay_{S}.json").read_text(encoding="utf-8"))
    pid = rp["parcel"]
    f = under_camera(by_pid[pid], 1 + int(round(rp["events"]["tunnel_read"]["physical_s"] * 10)))
    sc.frame_set(f)
    render(OUT / f"_{pid}.png")
    (OUT / "manifest.json").write_text(json.dumps({pid: False}, indent=1), encoding="utf-8")
    print("STILL (replay)", pid, "frame", f, "-> run: py -X utf8 assets/hub/scanner_photos.py --finish", flush=True)
elif a.all:
    man = {}
    for r, f_read in reads_in_window():
        pid = r["parcel_id"]
        f = under_camera(by_pid[pid], f_read)
        if f is None:
            print("SKIP (never under the camera in the window)", pid, flush=True)
            continue
        sc.frame_set(f)
        render(OUT / f"_{pid}.png")
        man[pid] = False
        print("STILL", pid, "frame", f, flush=True)
    sp = story_still(cam)
    if sp:
        man[sp] = True
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1), encoding="utf-8")
    print("SCANNER rendered", len(man), "-> run: py -X utf8 assets/hub/scanner_photos.py --finish", flush=True)
