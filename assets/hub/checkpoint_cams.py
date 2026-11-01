"""Six close-up checkpoint CCTV cameras (Rexton 2 Nov, six_checkpoints_on_camera_0915.md addendum 6).

Real hubs put a camera at each scan station and dock door, close enough to see the carton and its label, besides the
wide ceiling cameras. One per checkpoint, placed from the site plan only (the scan point, the machine, the door, the
bay row), the way a hub would mount it, never from the truth or to dodge occlusion of any parcel:
  CHK_UNLOAD  truss drop-pole above door D05's telescopic conveyor, looking out at the door mouth (unload scan SP-IN-N)
  CHK_TUNNEL  on a gantry over the belt just past the tunnel, looking back up the belt at its exit (SP-TUNNEL)
  CHK_CHUTE   ceiling over the chute row, one camera for the bank C10-C12 + reject (vendors: ~1 camera per 3 chutes)
  CHK_CAGE_W  ceiling above the aisle in front of the west cage bays, all three (S11-S13, x 25-32.6) in view with
              margin (4.2 m over the aisle cut S11 at the frame edge), looking down at the bay fronts (SP-CAGE-W)
  CHK_STORE   on the rack frame above the exception store's gap, looking out at who comes in (SP-STORE-IN)
  CHK_DOCK    side-mounted on dock door D07's frame (the usual dock-door camera mount), across the door and its RFID gate
Lens: 4 mm on a 1/2.8" sensor (~84 deg horizontal; the wide cameras are 2.8 mm, 103 deg), 2688 x 1520, 10 fps, same
CCTV look and OSD. Each gets its own clock domain with a planted offset in render_truth.json (evaluator-only) that
Spoor has to fit like the others. The 19 wide cameras are not touched.

  py -X utf8 assets/hub/checkpoint_cams.py          # adds / updates them in hub_spec(_lineAb).json + render_truth.json
"""
import json
import math
from pathlib import Path

HUB = Path(__file__).resolve().parent
HFOV = 84.0
RES = (2688, 1520)

# id, zone, mount, eye (x, y, z), look-at (x, y, z), OSD label, scan point, what it is for
CAMS = [
    ("CHK_UNLOAD", "Z01", "truss drop-pole above the telescopic conveyor", (3.6, 24.4, 3.6), (0.2, 23.0, 1.0),
     "DOOR D05 UNLOAD", "SP-IN-N", "the carton handed off the truck at door D05 and its unload scan"),
    ("CHK_TUNNEL", "Z04", "gantry bracket over the belt just past the tunnel", (25.6, 10.2, 2.9), (22.2, 9.5, 1.5),
     "TUNNEL EXIT", "SP-TUNNEL", "every carton as it comes out of the scan tunnel, in order"),
    ("CHK_CHUTE", "Z06", "truss drop-pole over the chute row", (35.2, 17.6, 4.5), (31.0, 19.9, 1.2),
     "CHUTES C10-C12", "SP-DIV-C12", "diverts off the loop into chutes C10, C11, C12 and the reject chute"),
    ("CHK_CAGE_W", "Z10", "ceiling truss drop-pole over the cage aisle", (28.8, 27.6, 5.0), (28.8, 30.2, 0.9),
     "CAGE BAYS S11-S13", "SP-CAGE-W", "cartons on the west cage shelves, hands taking them, the cage scans"),
    ("CHK_STORE", "Z11", "bracket on the rack frame above the store's gap", (14.3, 33.8, 3.1), (14.6, 31.9, 1.0),
     "EXCEPTION STORE DOOR", "SP-STORE-IN", "who goes into or out of the exception store, and its SCAN IN"),
    ("CHK_DOCK", "Z12", "side mount on the dock door frame", (31.1, 39.75, 3.0), (29.0, 38.4, 1.0),
     "DOCK D07", "SP-RFID-D07", "cages through door D07 and its RFID gate"),
]
# planted clocks (evaluator-only), like the wide cameras': a few seconds off, a little drift
CLOCKS = {"CHK_UNLOAD": (1.6, 12), "CHK_TUNNEL": (-2.2, -9), "CHK_CHUTE": (0.9, 15), "CHK_CAGE_W": (-1.4, 8),
          "CHK_STORE": (2.3, -14), "CHK_DOCK": (-0.7, 11)}


def pose(eye, at):
    dx, dy, dz = at[0] - eye[0], at[1] - eye[1], at[2] - eye[2]
    heading = math.degrees(math.atan2(dy, dx)) % 360
    tilt = math.degrees(math.atan2(-dz, math.hypot(dx, dy)))
    return round(heading, 1), round(tilt, 1)


def entry(cid, zone, mount, eye, at, osd, sp, what):
    heading, tilt = pose(eye, at)
    vfov = math.degrees(2 * math.atan(math.tan(math.radians(HFOV / 2)) * RES[1] / RES[0]))
    dist = math.dist(eye, at)
    ppm = RES[0] / (2 * dist * math.tan(math.radians(HFOV / 2)))  # at the aim point
    return {"id": cid, "kind": "checkpoint", "zone": zone, "question": f"Checkpoint camera: {what}.",
            "detail_target": "identify", "target_ppm": 250, "position_m": [eye[0], eye[1]], "height_m": eye[2],
            "heading_deg": heading, "tilt_down_deg": tilt, "hfov_deg": HFOV, "vfov_deg": round(vfov, 1),
            "resolution": list(RES), "fps": 10, "mount": mount, "aim_m": list(at), "scan_point": sp,
            "aim_ppm": round(ppm), "clock_domain": f"clkd_{cid.lower()}", "osd_label": osd,
            "realism": {"lens": "4 mm on 1/2.8 inch (about 84 deg wide), mild barrel distortion; exact k1 in render_truth",
                        "codec": "as the wide cameras", "osd": "camera name + date/time from its OWN clock",
                        "clock": "own offset and drift, evaluator-only in render_truth; Spoor must fit them"}}


def main():
    rows = [entry(*c) for c in CAMS]
    for name in ("hub_spec_lineAb.json", "hub_spec.json"):
        p = HUB / name
        spec = json.loads(p.read_text(encoding="utf-8"))
        spec["cameras"] = [c for c in spec["cameras"] if c.get("kind") != "checkpoint"] + rows
        doms = [d for d in spec["clock_domains"] if not d["id"].startswith("clkd_chk_")]
        spec["clock_domains"] = doms + [{"id": r["clock_domain"], "kind": "camera", "devices": r["id"]} for r in rows]
        p.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    p = HUB / "render_truth.json"
    truth = json.loads(p.read_text(encoding="utf-8"))
    for cid, (off, ppm) in CLOCKS.items():
        truth["cameras"][cid] = {"clock_offset_s": off, "clock_drift_ppm": ppm, "lens_k1": -0.08, "mount_roll_deg": 0.0}
    p.write_text(json.dumps(truth, indent=1) + "\n", encoding="utf-8")
    for r in rows:
        print(f"{r['id']:<11} at ({r['position_m'][0]:.1f}, {r['position_m'][1]:.2f}) h {r['height_m']} m  heading "
              f"{r['heading_deg']:6.1f}  tilt {r['tilt_down_deg']:5.1f}  {r['aim_ppm']} px/m at the aim point")


if __name__ == "__main__":
    main()
