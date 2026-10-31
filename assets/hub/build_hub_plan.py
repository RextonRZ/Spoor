"""Spoor parcel hub (fictional) — 2D plan generator and coverage checker. No Blender.

Writes, next to this file:
  hub_spec.yaml       build spec: zones, structure, machines, assets, cameras, scan points, checks
  render_truth.yaml   EVALUATOR-ONLY: per-camera clock offsets / lens values used when rendering. Spoor's runtime
                      must never read it (PRD §8.1): Spoor has to *estimate* these.
  hub_plan.svg        top-down plan at 1:200
  CREDITS.md          third-party assets and licences

Run:  cd backend && uv run --with pyyaml python ../assets/hub/build_hub_plan.py

Frame: metres, X east, Y north, Z up; origin = south-west outside corner of the building.
Every number tagged `assumption` has no published source; see `assumptions` in the output.
"""

import json
import math
from pathlib import Path

import yaml

HERE = Path(__file__).parent
BW, BD = 60.0, 40.0  # building footprint (assumption A1)
EAVES = 11.0  # 10–12 m eaves per pack (Shah Alam shed lists 12 m clear)
DECK = 1.5  # sorter deck height (assumption A5, owner-approved: 1.5 m so chutes slope convincingly)

# ----------------------------------------------------------------------------------------------- camera model (pack)
IMG_W, IMG_H, HFOV, VFOV = 2688, 1520, 103.0, 58.0  # 4MP 2.8 mm dome spec copied from a datasheet
SENSOR_MAX_FPS = 15  # what the camera can do
FPS = 10  # what the recorder keeps: owner decision 2026-10-28 (render budget); 10–12 fps is common NVR practice
TAN_H, TAN_V = math.tan(math.radians(HFOV / 2)), math.tan(math.radians(VFOV / 2))
PPM_K = IMG_W / (2 * TAN_H)  # PPM at depth d = PPM_K / d  (≈1069 / d)
TARGET_PPM = {"detect": 25, "observe": 62, "recognise": 125}


def depth_for(ppm: float) -> float:
    return PPM_K / ppm


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# ----------------------------------------------------------------------------------------------- zones (Z01–Z14)
# id, name, kind, polygon, realism {wear, clutter, signs, lighting}
ZONES = [
    ("Z01", "Inbound dock (telescopic conveyors)", "dock", rect(0.2, 4.0, 5.6, 30.0),
     {"wear": "tyre marks and oil stains at each door; dock plates scuffed bare at the edges",
      "clutter": "torn stretch wrap, a crooked roll cage, empty sacks kicked against the wall",
      "signs": "rigid metal number boards 01–06 (white on dark blue) above the doors, 'PENERIMAAN / RECEIVING' over the row; 'AWAS - KENDERAAN' (caution vehicles)",
      "lighting": "brightest zone: open doors spill hard daylight (overcast HDRI); 5000 K high-bays inside"}),
    ("Z02", "Bag opening", "work", rect(5.6, 17.0, 13.0, 29.0),
     {"wear": "cut-tie offcuts and scuffed floor around benches",
      "clutter": "pile of opened woven sacks, a bin of cable ties, a box cutter on each bench",
      "signs": "'BUKA BEG DI SINI' (open bags here) board", "lighting": "high-bay grid, one light 10% dimmer"}),
    ("Z03", "Induction", "work", rect(5.6, 6.5, 17.5, 12.5),
     {"wear": "anti-fatigue mats worn through where inductors stand",
      "clutter": "a standing fan, a stool, a few parcels waiting beside the belt",
      "signs": "'LABEL MENGHADAP ATAS' (label facing up) above the belt", "lighting": "even high-bays"}),
    ("Z04", "Scan tunnel (DWS)", "machine", rect(17.5, 7.5, 23.0, 11.5),
     {"wear": "fingerprints and tape residue on the tunnel housing",
      "clutter": "cable trays to a control cabinet", "signs": "machine number plate 'DWS-01' (fictional)",
      "lighting": "white LED light bars glowing inside the tunnel mouth"}),
    ("Z05", "Cross-belt loop (one raised level)", "machine", rect(23.0, 6.5, 54.6, 19.5),
     {"wear": "galvanised frame dulled; scuffs on guard rails at forklift height",
      "clutter": "maintenance walkway inside the loop, a ladder, a spare carrier on the floor",
      "signs": "'DILARANG MASUK - ZON MESIN' (no entry - machine zone)", "lighting": "high-bays; loop shadows the floor"}),
    ("Z06", "Chutes + bagging (C01–C12)", "work", rect(30.0, 19.5, 49.6, 24.6),
     {"wear": "polished chute ends; bag-frame feet scuffed",
      "clutter": "full sacks waiting to be tied, spare empty sacks hung on frames",
      "signs": "destination boards above each chute (Pulau Pinang, Johor Bahru, Kuching...)",
      "lighting": "high-bays; chutes cast stripes of shadow"}),
    ("Z07", "Reject chute (no-read / exception)", "machine", rect(28.6, 19.5, 30.0, 22.4),
     {"wear": "dented chute end", "clutter": "a blue crate of rework parcels under the chute",
      "signs": "red 'REJECT / NO READ' board", "lighting": "as Z06"}),
    ("Z08", "Exception bench (rework / relabel / damage hold)", "work", rect(23.0, 20.0, 28.6, 24.6),
     {"wear": "label backing paper on the floor", "clutter": "label printer, tape guns, one LOCKED roll cage for damaged parcels",
      "signs": "'BARANG ROSAK' (damaged goods) on the locked cage", "lighting": "fluorescent task light over the bench"}),
    ("Z09", "Oversize / non-conveyable area", "work", rect(5.6, 0.2, 17.5, 6.5),
     {"wear": "pallet-jack wheel tracks", "clutter": "stretch-wrapped pallets, big boxes, a hand pallet jack",
      "signs": "yellow floor box 'OVERSIZE'", "lighting": "even high-bays"}),
    ("Z10", "Cage staging", "staging", rect(24.0, 25.2, 53.0, 32.4),
     {"wear": "faded yellow bay lines, bay numbers half rubbed off",
      "clutter": "roll cages in numbered bays, some half full; one cage parked crooked",
      "signs": "bay numbers S01..S20 painted on the floor", "lighting": "high-bays, slightly uneven"}),
    ("Z11", "Empty cage / bag store (inside corner of the L)", "store", rect(0.2, 30.0, 24.0, 39.8),
     {"wear": "dust in corners, faded lines", "clutter": "empty cages nested tightly, folded sacks on steel shelves",
      "signs": "'SANGKAR KOSONG' (empty cages)", "lighting": "one high-bay off — darkest corner of the hall"}),
    ("Z12", "Outbound dock", "dock", rect(24.0, 32.4, 54.0, 39.8),
     {"wear": "tyre marks, oil stains at doors, dock plate edges bare",
      "clutter": "cages queued at each door, a pallet jack", "signs": "rigid metal number boards 07–12 above the doors, 'PENGHANTARAN / DISPATCH' over the row",
      "lighting": "daylight from open doors; cooler/brighter than the hall"}),
    ("Z13", "Supervisor office", "office", rect(54.6, 0.2, 59.8, 6.0),
     {"wear": "scuffed door", "clutter": "desk, monitor, paperwork", "signs": "'PEJABAT PENYELIA' (supervisor office)",
      "lighting": "mounted fluorescent lights; glass wall facing the floor"}),
    ("Z14", "Truck yard (outside west + north walls)", "yard", None,
     {"wear": "patched asphalt, oil stains", "clutter": "cones, concrete barriers, a parked lorry",
      "signs": "fictional brand on lorries", "lighting": "overcast daylight HDRI"}),
]
YARD_WEST, YARD_NORTH = rect(-18.0, 0.0, 0.0, 34.0), rect(20.0, 40.0, 60.0, 58.0)

# blind corner: deliberate, written down, inside corner of the L (NW), behind 3 m sack racks
RACKS = [(0.2, 33.0, 13.4, 33.6), (15.2, 33.0, 15.8, 39.8)]  # 3 m steel racking (folded sacks, nested cages)
RACK_H = 3.0
BENCHES = [("bag-opening bench 1", (6.2, 19.0, 8.0, 22.0)), ("bag-opening bench 2", (6.2, 24.0, 8.0, 27.0)),
           ("exception bench", (23.6, 21.2, 28.0, 22.6))]  # plan rects, 0.9 m high
CAGE_BAY = 2.2  # square floor bay, yellow corner marks
STORE_SHELVES = [(16.9, 39.2), (18.9, 39.2)]  # CC0 steel shelving in the empty-cage store (Z11), against the wall
CAGE_BAYS = [(25.0 + (i % 10) * 2.7, 26.0 if i < 10 else 29.5) for i in range(20)]  # SW corners, S01..S20
BLIND = {"id": "BLIND_NW", "zone": "Z11", "polygon": rect(0.2, 33.6, 15.2, 39.8),
         "why": "inside corner of the L-flow, behind 3 m sack racks (entrance gap at x 13.4–15.2 facing south); "
                "no camera is aimed here and the racks block oblique views",
         "used_by": "scenario 'removal into blind spot': last seen entering Z11 from Z10; Spoor must say 'no coverage'"}

# ----------------------------------------------------------------------------------------------- structure & machines
COLUMNS = [[x, y] for x in (0.0, 12.0, 24.0, 36.0, 48.0, 60.0) for y in (0.0, 40.0)] + \
          [[x, 25.0] for x in (12.0, 24.0, 36.0, 48.0)] + [[0.0, 20.0], [60.0, 20.0]]  # fmt: skip
EXIT_SIGN = "lit green running-man 'KELUAR' (exit) sign above the door"
DOORS = [{"id": f"D{i + 1:02d}", "board": f"{i + 1:02d}", "kind": "dock", "wall": "W", "centre": [0.0, y],
          "width": 3.0, "height": 3.0,
          "dock_height": 1.2} for i, y in enumerate((7.0, 11.0, 15.0, 19.0, 23.0, 27.0))] + \
        [{"id": f"D{i + 7:02d}", "board": f"{i + 7:02d}", "kind": "dock", "wall": "N", "centre": [x, 40.0],
          "width": 3.0, "height": 3.0,
          "dock_height": 1.2} for i, x in enumerate((29.0, 33.0, 37.0, 41.0, 45.0, 49.0))] + \
        [{"id": "STAFF-1", "kind": "staff", "wall": "E", "centre": [60.0, 12.0], "width": 1.0, "height": 2.1,
          "dock_height": 0.0, "sign": EXIT_SIGN}] + \
        [{"id": fid, "kind": "fire_exit", "wall": w, "centre": c, "width": 1.0, "height": 2.1, "dock_height": 0.0,
          "sign": EXIT_SIGN, "hardware": "push bar, opens outward, alarmed"}
         for fid, w, c in (("FE-1", "S", [30.0, 0.0]), ("FE-2", "S", [46.0, 0.0]), ("FE-3", "E", [60.0, 28.0]))]  # fmt: skip
LOOP = {"south_y": 11.0, "north_y": 19.0, "radius": 4.0, "west_cx": 28.0, "east_cx": 50.0, "cy": 15.0,
        "direction": "south straight eastbound, north straight westbound (counter-clockwise from above)",
        "deck_height": DECK, "carrier": "850 x 440 mm at 700 mm pitch (FORTNA option 2)", "speed_mps": 2.0,
        "speed_note": "owner cap 2.0 m/s: 0.2 m per frame at 10 fps, well under one 0.7 m carrier pitch, so a "
                      "tracker never has to guess which carrier a parcel jumped to between frames"}
LOOP_LEN = 2 * (LOOP["east_cx"] - LOOP["west_cx"]) + 2 * math.pi * LOOP["radius"]
# line A layout (reviews 014b / 015 / 016): "a" = the shared feed run at y 10.85 (current flow + stations);
# "b" = one induct point per inductor: the feed line moves north to y 12.25 (x 5-13), 4 roller tables, 4 induct
# belts at 45 deg into the induction belt, D02's boom joins through a stub into the feed corner. build_hub builds
# the line-A pieces from "line_a"; flow / stations follow at M5 (assets/hub/mocap/M5_PLAN.md).
LINE_A_LAYOUT = "b"  # rendered layout (builder note 1040: the canonical spec is layout b)
LINE_A_FEED_Y = 12.25
CONVEYORS = [
    {"id": "telescopic_D%02d" % (i + 1), "kind": "telescopic", "path": [[-3.0, y], [4.4, y]], "height": 1.0}
    for i, y in enumerate((7.0, 11.0, 15.0, 19.0, 23.0, 27.0))
] + [  # fmt: skip
    # the collector turns east into a slow accumulation (feed) belt that stops at its end; inductors stand between
    # it and the induction belt, take parcels off the queue and place them label-up into gaps (stations.py)
    {"id": "collector", "kind": "belt", "path": [[5.0, 28.0], [5.0, 10.85], [9.2, 10.85]] if LINE_A_LAYOUT == "a" else
     [[5.0, 28.0], [5.0, LINE_A_FEED_Y], [13.0, LINE_A_FEED_Y]], "height": 1.0},
    {"id": "induction", "kind": "belt", "path": [[5.6, 9.5], [17.5, 9.5]], "height": 1.0},
    {"id": "tunnel_line", "kind": "belt", "path": [[17.5, 9.5], [23.0, 9.5]], "height": DECK},
    {"id": "merge", "kind": "belt", "path": [[23.0, 9.5], [27.6, 9.5], [30.0, 11.0]], "height": DECK},
    # induction line B (B2 pre-review #4: a 2nd induction line, 30-35 % carrier occupancy): a manual induction
    # workstation on the free floor between the forklift lane (y <= 5) and the loop - two inductors take parcels from
    # bulk gaylords (brought in by forklift) onto belt B, which ramps up to the deck through DWS arch B and merges
    # diagonally onto the south straight 16.6 m east of the main merge. Crosses no walkway or lane; starts 0.5 m
    # east of the XO-1 south stair (from x 39.6 its first 0.7 m ran into the stair at 0.9 m: stairs_clear check).
    {"id": "induction_B", "kind": "belt", "path": [[40.8, 7.6], [44.0, 7.6], [45.6, 9.2], [46.6, 11.0]],
     "height": 1.0, "heights": [1.0, 1.0, DECK, DECK]},
] + ([{"id": "d02_stub", "kind": "belt", "path": [[5.0, 10.6], [5.0, LINE_A_FEED_Y - 0.45]], "height": 1.0,
       "note": "D02's boom joins here and runs north into the feed corner (line A layout b)"}]
     if LINE_A_LAYOUT == "b" else [])
# C01 first after the east curve (westbound); a 2.8 m gap between C06 and C07 lands crossover XO-1
CHUTE_X = [48.6 - 1.5 * k for k in range(6)] + [38.3 - 1.5 * k for k in range(6)]
DESTS = ["Pulau Pinang", "Kedah / Perlis", "Perak (Ipoh)", "Klang", "Kuala Lumpur", "Negeri Sembilan", "Melaka",
         "Johor Bahru", "Pahang (Kuantan)", "Kelantan / Terengganu", "Sabah (Kota Kinabalu)", "Sarawak (Kuching)"]
BAG_FRAME = (1.0, 0.8, 0.9)  # w x d x rim height (assumption A18)
CHUTE_LIP_Z = 1.0  # 0.1 m above the bag rim; chute drops 0.45 m over 1.3 m (19°, above cardboard-on-steel ~17°)
CHUTES = [{"id": f"C{i + 1:02d}", "x": round(x, 2), "mouth_y": 19.6, "end_y": 20.9, "lip_z": CHUTE_LIP_Z,
           "width": 1.0, "bag_frame_y": 20.6} for i, x in enumerate(CHUTE_X)] + \
         [{"id": "REJECT", "x": 29.3, "mouth_y": 19.6, "end_y": 20.9, "lip_z": 0.9, "width": 1.0, "bag_frame_y": None,
           "bin": {"y": [20.6, 21.2], "size_m": [0.8, 0.6, 0.6], "what": "blue rework bin"}}]  # fmt: skip
# ----------------------------------------------------------------------------------------------- circulation
# Owner change request 2026-10-28: crossovers, fire exits, yellow walkways, forklift lane Z09 -> outbound docks.
CROSSOVERS = [
    {"id": "XO-1", "x": 39.7, "width": 1.2, "deck_m": 3.3, "south_stair_y": [6.6, 10.2], "bridge_y": [10.2, 19.6],
     "north_stair_y": [19.6, 23.2], "crosses": "cross-belt loop, both straights; lands in the gap between C06 and C07",
     "why": "south aisle / office / Z09 to the chutes and bagging aisle without walking round the loop"},
    {"id": "XO-2", "x": 16.5, "width": 1.2, "deck_m": 2.4, "south_stair_y": [5.4, 8.0], "bridge_y": [8.0, 11.0],
     "north_stair_y": [11.0, 13.6], "crosses": "induction belt (1.0 m high)",
     "why": "south aisle / Z09 to the bag-opening area, exception bench and chutes (west side)"},
]
WALKWAYS = [  # id, rect (x0, y0, x1, y1), purpose — 1.2 m wide, yellow edge lines
    ("W1", (5.8, 0.4, 54.4, 1.6), "south wall: Z09, office door, fire exits FE-1 / FE-2, crossover feet"),
    ("W2", (58.5, 6.0, 59.7, 39.6), "east wall: office, staff door, FE-3, outbound dock"),
    ("W3", (13.2, 23.2, 58.5, 24.4), "bagging aisle: bag opening <-> exception bench <-> all 12 chutes <-> east aisle"),
    ("W4", (15.9, 13.6, 17.1, 23.2), "crossover XO-2 north foot up to W3"),
    ("W5", (0.4, 28.6, 14.4, 29.8), "inbound dock north end <-> bag opening (round the end of the collector belt)"),
    ("W5b", (13.2, 24.4, 14.4, 28.6), "joins W5 to W3"),
    ("W6", (24.0, 32.0, 58.5, 33.2), "between cage staging and the forklift lane"),
]
LANE_W = 3.0
LANE = [[9.0, 3.5], [52.0, 3.5], [52.0, 8.0], [56.7, 8.0], [56.7, 34.9], [25.5, 34.9]]  # centreline, Z09 -> Z12
ZEBRAS = [  # where people cross the forklift lane
    ("ZX1", (39.1, 1.6, 40.3, 6.6), "W1 <-> XO-1 south foot"),
    ("ZX2", (15.9, 1.6, 17.1, 5.4), "W1 <-> XO-2 south foot"),
    ("ZX3", (55.2, 23.2, 58.2, 24.4), "W3 <-> W2 across the east lane"),
    ("ZX4", (55.2, 32.0, 58.2, 33.2), "W6 <-> W2 across the east lane"),
    ("ZX5", (32.2, 33.2, 33.9, 36.6), "cage staging -> doors D07/D08 across the lane (roll cages)"),
    ("ZX6", (40.2, 33.2, 41.9, 36.6), "doors D09/D10 -> cage staging (empty cages back)"),
    ("ZX7", (44.2, 33.2, 45.9, 36.6), "cage staging -> doors D11/D12 across the lane (roll cages)"),
]
CIRCULATION_REALISM = {
    "walkways": "100 mm yellow edge lines, worn through at forklift turns; walking-man stencils every ~10 m",
    "lane": "yellow-black hazard edge on the lane; 'AWAS FORKLIFT' (caution forklift) signs at each zebra; "
            "tyre marks on the turns; a convex mirror at the NE turn (x 56.7, y 34.9)",
    "zebras": "white-yellow stripes, paint scuffed in the middle",
    "crossovers": "galvanised stairs and grating, yellow handrails, 'GUNA JAMBATAN' (use the bridge) sign at each foot",
    "fire_exits": "push-bar doors, lit KELUAR signs, fire-door keep-clear hatching; in some clips FE-2 is propped "
                  "open with a box (a real-world violation and a theft route)",
}


def lane_rects():
    h = LANE_W / 2
    return [(min(a[0], b[0]) - h, min(a[1], b[1]) - h, max(a[0], b[0]) + h, max(a[1], b[1]) + h)
            for a, b in zip(LANE, LANE[1:])]


SORT_PLANS = [{"version": "SP-v1", "valid_from": "scenario start (set per scenario)", "valid_to": None,
               "chutes": {f"C{i + 1:02d}": d for i, d in enumerate(DESTS)} | {"REJECT": "no-read / exception"}}]

# ----------------------------------------------------------------------------------------------- scan points
SCAN_POINTS = [  # id, device kind, zone, xyz, clock domain, event kinds
    ("SP-IN-S", "handheld", "Z01", (3.5, 11.0, 1.1), "clkd_handheld", "arrived_facility (bag/parcel unload scan)"),
    ("SP-IN-N", "handheld", "Z01", (3.5, 23.0, 1.1), "clkd_handheld", "arrived_facility"),
    ("SP-BAGOPEN", "handheld", "Z02", (7.5, 23.0, 1.1), "clkd_handheld", "container_remove (bag opened)"),
    ("SP-INDUCT", "sorter_plc", "Z03", (12.0, 9.5, 1.1), "clkd_wcs", "inducted (photo-eye)"),
    ("SP-INDUCT-B", "sorter_plc", "Z05", (42.0, 7.6, 1.1), "clkd_wcs", "inducted (photo-eye, line B)"),
    ("SP-TUNNEL-B", "tunnel", "Z05", (45.6, 9.2, DECK + 0.2), "clkd_wcs",
     "tunnel_read / tunnel_no_read on line B (DWS arch at the top of the ramp)"),
    ("SP-TUNNEL", "tunnel", "Z04", (22.2, 9.5, DECK + 0.2), "clkd_wcs",
     "tunnel_read / tunnel_no_read (read point = tunnel exit); weight + dims from the weigh section are merged "
     "into this one event"),
    ("SP-OVERSIZE", "handheld", "Z09", (11.0, 3.5, 1.1), "clkd_handheld", "inducted (manual, non-conveyable)"),
] + [(f"SP-DIV-{c['id']}", "sorter_plc", "Z07" if c["id"] == "REJECT" else "Z06",
      (c["x"], 19.8, DECK + 0.2), "clkd_wcs", "divert_confirmed") for c in CHUTES] + \
    [(f"SP-BAG-{c['id']}", "handheld", "Z06", (c["x"], 21.9, 1.1), "clkd_handheld", "container_add (parcel into bag)")
     for c in CHUTES if c["id"] != "REJECT"] + [  # fmt: skip
    ("SP-REWORK", "handheld", "Z08", (25.5, 22.5, 1.1), "clkd_handheld", "manual_encoded / relabeled / damage_hold"),
    ("SP-CAGE-W", "handheld", "Z10", (31.0, 28.0, 1.1), "clkd_handheld", "container_add (bag into cage)"),
    ("SP-CAGE-E", "handheld", "Z10", (46.0, 28.0, 1.1), "clkd_handheld", "container_add (bag into cage)"),
] + [(f"SP-LOAD-D{i + 7:02d}", "handheld", "Z12", (x, 37.5, 1.1), "clkd_handheld", "container_loaded (cage onto truck)")
     for i, x in enumerate((29.0, 33.0, 37.0, 41.0, 45.0, 49.0))] + \
    [(f"SP-RFID-D{i + 7:02d}", "rfid_portal", "Z12", (x, 39.4, 1.5), "clkd_wcs", "departed_facility (cage RFID, can cross-read)")
     for i, x in enumerate((29.0, 33.0, 37.0, 41.0, 45.0, 49.0))]  # fmt: skip

# ----------------------------------------------------------------------------------------------- cameras
# Cameras are placed, not guessed: each has a DUTY AREA it must cover at its detail level, a few real mount points
# (column, truss drop-pole, wall bracket) with a yaw centre, and candidate heights. place_cameras() searches
# height / yaw (±45° of centre) / tilt for the pose that covers the most of the duty area at the target PPM, with
# occlusion, and must also see the scan points inside the duty area.
# id, zone, duty (x0, y0, x1, y1, parcel height z), mounts [(x, y, yaw centre)], heights, detail, mount, question,
# extra must-see points [(x, y, z, need)]
CAMERA_SPECS = [
    ("CAM_01", "Z01", (0.2, 4.0, 5.6, 18.0, 1.0),
     [(6.5, 0.6, 110), (7.5, 2.0, 115), (9.0, 3.0, 135), (10.5, 4.0, 150), (8.5, 1.0, 125)], (5.0, 6.0, 7.0), "observe",
     "south wall bracket / truss drop-pole", "Which truck and bag did the parcel arrive in (doors 01–03)?", [],
     {"max_wall": 0.25}),
    ("CAM_02", "Z01", (0.2, 16.0, 5.6, 30.0, 1.0), [(6.5, 31.5, 250), (7.5, 30.5, 245)], (5.0, 6.0, 7.0), "observe",
     "truss drop-pole", "Which truck and bag did the parcel arrive in (doors 04–06)?", []),
    ("CAM_03", "Z02", (5.6, 17.5, 9.5, 28.5, 1.0), [(11.5, 23.0, 180), (12.0, 20.0, 160)], (4.0, 5.0, 6.0),
     "recognise", "truss drop-pole", "Did every parcel from the opened bag reach the belt?", []),
    # cctv_setup_0025 #2: framed for line A layout b (tables / induct belts x 6-13, y 9-12.6, M5); from (18.5, 3.0) the
    # XO-2 stair filled the middle and the old duty area (layout a) left the new line in a corner
    ("CAM_04", "Z03", (5.6, 8.8, 15.0, 13.0, 1.0), [(18.5, 3.0, 125)],
     (7.0,), "observe", "truss drop-pole",
     "Was the parcel put on the belt, and when (incl. oversize manual scan)?", [(19.4, 9.5, 1.0, "detect"), (17.6, 9.5, DECK + 0.2, "observe")],
     # four poses rendered (qa/review/cctv_reaim): west of the stair loses the weigh section, on it the stair fills
     # the middle; from the old mount aimed at line A (b) the stair sits in the right third
     {"pose": {"yaw": 125, "tilt": 45}}),
    ("CAM_05", "Z04", (21.5, 8.0, 27.6, 11.0, DECK + 0.2), [(25.0, 6.5, 150), (26.0, 7.0, 155)], (3.5, 4.0, 4.5),
     "recognise", "truss drop-pole", "Which parcel left the tunnel at the scan time? (clock anchor for the WCS)", []),
    ("CAM_06", "Z05", (23.0, 6.5, 35.0, 20.0, DECK + 0.2), [(29.0, 3.0, 90), (29.0, 5.0, 90)], (6.5, 7.5, 8.5),
     "observe", "truss drop-pole", "Did a parcel fall off or get stuck between carriers (west curve, merge)?",
     [(29.3, 19.0, DECK + 0.3, "detect"), (CHUTE_X[11], 19.0, DECK + 0.3, "detect")]),
    # cctv_setup_0025 #3: off the XO-1 bridge's axis (x 39.7; from x 39.0 the bridge ran through the frame centre)
    ("CAM_07", "Z05", (33.0, 6.5, 45.5, 20.0, DECK + 0.2), [(36.0, 4.0, 75), (42.8, 4.0, 105), (36.0, 2.0, 80), (42.8, 2.0, 100), (37.0, 1.5, 85)],
     (6.5, 7.5, 8.5), "observe", "truss drop-pole",
     "Did a parcel fall off or get stuck between carriers (middle straights)?", [], {"min_roof": 0.05}),
    ("CAM_08", "Z05", (43.5, 6.5, 54.6, 20.0, DECK + 0.2), [(49.0, 3.0, 90), (49.0, 5.0, 90)], (6.5, 7.5, 8.5),
     "observe", "truss drop-pole", "Did a parcel fall off or get stuck between carriers (east curve)?",
     [(CHUTE_X[0], 19.0, DECK + 0.3, "detect")]),
    ("CAM_09", "Z07", (28.4, 19.6, 30.4, 22.8, 1.2), [(32.0, 23.8, 205), (31.5, 25.4, 215), (29.4, 24.4, 270), (31.0, 23.0, 200)], (3.5, 4.0, 4.5, 5.0),
     "recognise", "truss drop-pole", "Which no-read parcel came out of the reject chute?",
     [(29.3, 19.8, DECK + 0.2, "detect")]),
    ("CAM_10", "Z06", (39.5, 19.4, 49.8, 25.0, 1.2), [(44.5, 26.6, 270), (48.3, 25.4, 240), (50.5, 25.5, 225)],
     (4.5, 5.5, 6.5, 7.5), "observe", "truss drop-pole / column (48, 25)", "Which bag did the parcel go into (C01–C06)?",
     [(CHUTE_X[0], 19.8, DECK + 0.2, "detect"), (46.0, 25.6, 1.0, "detect")]),
    ("CAM_11", "Z06", (29.8, 19.4, 40.6, 25.0, 1.2), [(35.0, 26.6, 270), (36.3, 25.4, 240), (40.5, 26.6, 250), (30.5, 26.0, 300)],
     (4.5, 5.5, 6.5, 7.5), "observe", "truss drop-pole / column (36, 25)", "Which bag did the parcel go into (C07–C12)?",
     [(CHUTE_X[11], 19.8, DECK + 0.2, "detect"), (34.0, 25.6, 1.0, "detect")]),
    ("CAM_12", "Z08", (23.0, 20.0, 28.6, 24.6, 1.0), [(24.4, 25.4, 290), (26.0, 25.6, 270)], (3.5, 4.0, 4.5),
     "recognise", "column (24, 25)", "Was it relabelled at the bench, and with what?", []),
    ("CAM_13", "Z10", (24.0, 25.2, 39.5, 32.4, 1.0), [(36.3, 25.4, 165), (37.0, 33.0, 195), (40.0, 31.0, 180)],
     (6.0, 7.0, 8.0), "observe", "column (36, 25) / truss drop-pole",
     "Which cage did the bag go into, and where did the cage go (west half)?",
     [(17.0, 32.0, 1.0, "detect"), (34.0, 25.6, 1.0, "detect")], {"min_roof": 0.05}),
    ("CAM_14", "Z10", (37.5, 25.2, 53.0, 32.4, 1.0),
     [(53.5, 28.8, 180), (53.5, 25.6, 170), (58.8, 25.6, 160), (58.8, 30.5, 195), (55.5, 27.0, 170)], (6.0, 7.0, 8.0),
     "observe", "truss drop-pole (east aisle)",
     "Which cage did the bag go into, and where did the cage go (east half)? Also films fire exit FE-3.",
     [(46.0, 25.6, 1.0, "detect"), (59.0, 28.0, 1.2, "detect")]),
    ("CAM_15", "Z12", (24.0, 32.4, 39.5, 39.8, 1.2),
     [(24.4, 33.0, 30), (24.4, 31.0, 40), (26.5, 31.6, 50), (28.0, 31.8, 65), (25.5, 32.2, 40)], (5.0, 6.0, 7.0),
     "observe", "column bracket / truss drop-pole", "Which cage went onto which truck (doors 07–09)?", [],
     {"max_near_block": 0.10, "min_duty_fill": 0.55}),
    ("CAM_16", "Z12", (38.5, 32.4, 54.0, 39.8, 1.2), [(53.6, 33.0, 150), (54.5, 31.0, 140)], (5.0, 6.0, 7.0),
     "observe", "wall bracket", "Which cage went onto which truck (doors 10–12)?", []),
    ("CAM_17", "Z14", (24.0, 40.5, 54.0, 52.0, 1.5), [(56.0, 40.4, 160), (22.0, 40.4, 20)], (6.0, 7.0), "detect",
     "outside north wall", "Which truck came and left, and when (outbound yard)? Trucks only — no plates/faces.", []),
    ("CAM_18", "AISLE_S", (17.5, 0.4, 54.4, 6.4, 1.2), [(53.0, 6.2, 225)], (5.0,), "detect", "truss drop-pole",
     "Which forklift carried which pallet along the south aisle (oversize route), and who used FE-1 / FE-2?",
     [(30.0, 1.0, 1.2, "detect"), (46.0, 1.0, 1.2, "detect")]),
    # the exception store's entrance (scenarios_v2 S2 #1, 31 Oct): the only way into or out of BLIND_NW is the 1.8 m
    # gap; CAM_01 / CAM_06 only had it at their frame top (cut by the lens remap). TAPA FSR 2023 7.4.15-16: CCTV on a
    # high-value cage's entrance; "if the HVC is too small to locate a camera inside, camera coverage of the entrance
    # is sufficient". Aimed at the doorway from the south-west: what it sees through the gap runs along the east rack,
    # while the way into the store turns west behind the south rack (from the south-east the view through the gap
    # ran along that way; the first pose search framed mostly floor with the gap in a corner: whole gap required)
    # 3.5 m: from 4.0 m it saw over the 3 m south rack into the store's north band (raycast, 31 Oct)
    # review 019 #1: doorway in the middle third AND the floor approach from cage S11 in the lower half (one shot shows
    # "walks in carrying it" and "walks out empty-handed"): the duty area runs east along the approach
    ("CAM_19", "Z10", (13.0, 30.8, 20.0, 33.6, 1.0), [(12.0, 29.0, 65), (11.5, 28.5, 60)],
     (3.5,), "observe", "truss drop-pole",
     "Who went into or came out of the exception store (the only way in or out of BLIND_NW)?",
     [(13.45, 33.3, 1.9, "observe"), (15.15, 33.3, 1.9, "observe"), (13.45, 33.3, 0.1, "observe"),
      (15.15, 33.3, 0.1, "observe"), (19.0, 32.2, 1.0, "observe"), (14.3, 33.3, 2.3, "observe")],
     # the search framed it at tilt 20 (top third wall) or 40 (doorway cut at the top, half the frame empty floor):
     # aimed at 30 so the doorway + its sign fill the middle and the approach the lower half
     {"pose": {"yaw": 65, "tilt": 30}}),
]

# ----------------------------------------------------------------------------------------------- geometry helpers


def sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def basis(yaw, tilt):
    y, t = math.radians(yaw), math.radians(tilt)
    f = [math.cos(y) * math.cos(t), math.sin(y) * math.cos(t), -math.sin(t)]
    r = [math.sin(y), -math.cos(y), 0.0]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    return f, r, u


def cam_coords(cam, p):
    f, r, u = basis(cam["yaw"], cam["tilt"])
    v = sub(p, cam["pos"])
    return dot(v, r), dot(v, u), dot(v, f)


def in_fov(cam, p):
    x, y, z = cam_coords(cam, p)
    return z > 0.1 and abs(x / z) <= TAN_H and abs(y / z) <= TAN_V, z


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def boxes():
    """Occluders (axis-aligned): columns, raised loop deck + rails, chutes, scan tunnel, office walls, sack racks."""
    out = [(x - 0.2, y - 0.2, 0.0, x + 0.2, y + 0.2, EAVES, "column") for x, y in COLUMNS]
    L = LOOP
    for yc in (L["south_y"], L["north_y"]):
        out.append((L["west_cx"], yc - 0.6, 0.0, L["east_cx"], yc + 0.6, DECK + 0.5, "loop straight"))
    for cx, sgn in ((L["west_cx"], -1), (L["east_cx"], 1)):
        for k in range(9):
            a = math.radians(-90 + 22.5 * k)
            x, y = cx + sgn * L["radius"] * math.cos(a), L["cy"] + L["radius"] * math.sin(a)
            out.append((x - 0.7, y - 0.7, 0.0, x + 0.7, y + 0.7, DECK + 0.5, "loop curve"))
    for c in CHUTES:
        out.append((c["x"] - 0.5, c["mouth_y"], 0.0, c["x"] + 0.5, c["end_y"], DECK, "chute"))
    out.append((54.6, 0.2, 0.0, 54.8, 6.0, 3.0, "office wall"))
    out.append((54.6, 5.8, 0.0, 59.8, 6.0, 3.0, "office wall"))
    for xo in CROSSOVERS:  # open steel stairs: only side stringers + top rails block; the bridge deck is solid
        x0, x1 = xo["x"] - xo["width"] / 2, xo["x"] + xo["width"] / 2
        for (ya, yb), up in ((xo["south_stair_y"], True), (xo["north_stair_y"], False)):
            for k in range(4):
                lo, hi = ya + (yb - ya) * k / 4, ya + (yb - ya) * (k + 1) / 4
                t = xo["deck_m"] * ((k + 1) / 4 if up else (4 - k) / 4)  # tread height at the top of this slice
                for sx0, sx1 in ((x0, x0 + 0.08), (x1 - 0.08, x1)):
                    out.append((sx0, lo, max(0.0, t - 0.3 - xo["deck_m"] / 4), sx1, hi, t, f"{xo['id']} stringer"))
                    out.append((sx0, lo, t + 0.9, sx1, hi, t + 1.1, f"{xo['id']} handrail"))
        out.append((x0, xo["bridge_y"][0], xo["deck_m"] - 0.2, x1, xo["bridge_y"][1], xo["deck_m"], f"{xo['id']} deck"))
        for sx0, sx1 in ((x0, x0 + 0.08), (x1 - 0.08, x1)):
            out.append((sx0, xo["bridge_y"][0], xo["deck_m"] + 0.9, sx1, xo["bridge_y"][1], xo["deck_m"] + 1.1,
                        f"{xo['id']} handrail"))
    out.append((19.5, 8.6, 0.0, 22.0, 10.4, DECK + 1.4, "scan tunnel"))  # parcels inside the tunnel are hidden
    out += [(x0, y0, 0.0, x1, y1, RACK_H, "sack rack") for x0, y0, x1, y1 in RACKS]
    out.append((16.6, 33.6, 0.0, 22.2, 37.6, 1.8, "nested empty cages"))
    out += [(x - 0.5, y - 0.25, 0.0, x + 0.5, y + 0.25, 2.0, "store shelving") for x, y in STORE_SHELVES]
    out += [(r[0], r[1], 0.0, r[2], r[3], 0.9, "bench") for _, r in BENCHES]
    return out


OCCLUDERS = boxes()


def ray_hits_box(o, p, b):
    lo, hi = b[:3], b[3:6]
    d = sub(p, o)
    t0, t1 = 0.0, 1.0
    for i in range(3):
        if abs(d[i]) < 1e-12:
            if o[i] < lo[i] or o[i] > hi[i]:
                return False
        else:
            ta, tb = (lo[i] - o[i]) / d[i], (hi[i] - o[i]) / d[i]
            ta, tb = min(ta, tb), max(ta, tb)
            t0, t1 = max(t0, ta), min(t1, tb)
            if t0 > t1:
                return False
    return t1 > 1e-6 and t0 < 1 - 1e-3


def contains(b, p, pad=0.05):
    return all(b[i] - pad <= p[i] <= b[i + 3] + pad for i in range(3))


def occluded(cam, p):
    for b in OCCLUDERS:
        if contains(b, p) or contains(b, cam["pos"]):
            continue
        if ray_hits_box(cam["pos"], p, b):
            return b[6]
    return None


def sees(cam, p, need="detect"):
    """(visible, ppm, reason). Indoor cameras can't see outside except through the doors; the yard camera only sees out."""
    inside_pt = 0 <= p[0] <= BW and 0 <= p[1] <= BD
    inside_cam = 0 <= cam["pos"][0] <= BW and 0 <= cam["pos"][1] <= BD
    if inside_pt != inside_cam:  # only through an open north dock door, and only just either side of it
        through = abs(p[1] - BD) <= 1.0 and any(
            d["wall"] == "N" and abs(p[0] - d["centre"][0]) <= d["width"] / 2 for d in DOORS)
        if not through:
            return False, 0.0, "wall"
    ok, depth = in_fov(cam, p)
    if not ok:
        return False, 0.0, "out of view"
    ppm = PPM_K / depth
    if ppm < TARGET_PPM[need]:
        return False, ppm, f"too far ({ppm:.0f} PPM < {TARGET_PPM[need]})"
    if (o := occluded(cam, p)) is not None:
        return False, ppm, f"blocked by {o}"
    return True, ppm, "ok"


def clip(poly, keep):
    """Sutherland–Hodgman clip of a polygon by a half-plane predicate with intersection function."""
    inside, inter = keep
    out = []
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]
        ia, ib = inside(a), inside(b)
        if ib:
            if not ia:
                out.append(inter(a, b))
            out.append(b)
        elif ia:
            out.append(inter(a, b))
    return out


def footprint(cam, ppm):
    """Floor area (z = 0.9 m, parcel height) where the camera sees at >= ppm: frustum ∩ depth limit ∩ area."""
    zf = 0.9
    f, r, u = basis(cam["yaw"], cam["tilt"])
    pts = []
    border = [(-1 + 2 * k / 12, -1) for k in range(12)] + [(1, -1 + 2 * k / 12) for k in range(12)] + \
             [(1 - 2 * k / 12, 1) for k in range(12)] + [(-1, 1 - 2 * k / 12) for k in range(12)]  # fmt: skip
    for a, b in border:
        d = [f[i] + a * TAN_H * r[i] + b * TAN_V * u[i] for i in range(3)]
        if d[2] < -1e-6:
            t = (zf - cam["pos"][2]) / d[2]
            t = min(t, 80.0)
        else:
            t = 80.0
        pts.append([cam["pos"][0] + t * d[0], cam["pos"][1] + t * d[1]])
    dmax = depth_for(ppm)

    def depth(p):
        return dot(sub([p[0], p[1], zf], cam["pos"]), f)

    def inter(a, b):
        da, db = depth(a), depth(b)
        s = (dmax - da) / (db - da)
        return [a[0] + s * (b[0] - a[0]), a[1] + s * (b[1] - a[1])]

    poly = clip(pts, (lambda p: depth(p) <= dmax, inter))
    inside_cam = 0 <= cam["pos"][0] <= BW and 0 <= cam["pos"][1] <= BD
    bounds = (0, 0, BW, BD) if inside_cam else (YARD_NORTH[0][0], YARD_NORTH[0][1], YARD_NORTH[2][0], YARD_NORTH[2][1])
    for axis, val, keep_le in ((0, bounds[0], False), (0, bounds[2], True), (1, bounds[1], False), (1, bounds[3], True)):
        def ins(p, axis=axis, val=val, keep_le=keep_le):
            return p[axis] <= val if keep_le else p[axis] >= val

        def itx(a, b, axis=axis, val=val):
            s = (val - a[axis]) / (b[axis] - a[axis])
            return [a[0] + s * (b[0] - a[0]), a[1] + s * (b[1] - a[1])]

        if poly:
            poly = clip(poly, (ins, itx))
    return poly


# ----------------------------------------------------------------------------------------------- checks


def on_crossover(x, y):
    """Floor under a crossover footprint holds no parcels; leave it out of coverage grids."""
    return any(abs(x - xo["x"]) <= xo["width"] / 2 and xo["south_stair_y"][0] <= y <= xo["north_stair_y"][1]
               for xo in CROSSOVERS)


def duty_points(spec, n=12):
    """Grid over the duty area (weight 1) + scan points inside it and extra must-see points (weight 5)."""
    cid, zone, (x0, y0, x1, y1, z), mounts, heights, detail, mount, q, extras = spec[:9]
    need = TARGET_PPM[detail]
    pts = [((x0 + (x1 - x0) * (i + 0.5) / n, y0 + (y1 - y0) * (j + 0.5) / n, z), 1, need)
           for i in range(n) for j in range(n)]
    pts = [q_ for q_ in pts if not on_crossover(q_[0][0], q_[0][1])]
    pts += [(xyz, 5, min(need, TARGET_PPM["observe"])) for _, _, _, xyz, _, _ in SCAN_POINTS
            if x0 <= xyz[0] <= x1 and y0 <= xyz[1] <= y1]
    pts += [((x, y, zz), 5, TARGET_PPM[nd]) for x, y, zz, nd in extras]
    return pts


def pose_score(cam, pts, occl):
    f, r, u = basis(cam["yaw"], cam["tilt"])
    pos = cam["pos"]
    score, ppm_sum = 0, 0.0
    for p, w, need in pts:
        v = (p[0] - pos[0], p[1] - pos[1], p[2] - pos[2])
        z = v[0] * f[0] + v[1] * f[1] + v[2] * f[2]
        if z <= 0.1 or abs((v[0] * r[0] + v[1] * r[1]) / z) > TAN_H:
            continue
        if abs((v[0] * u[0] + v[1] * u[1] + v[2] * u[2]) / z) > TAN_V or PPM_K / z < need:
            continue
        if occl and occluded(cam, list(p)) is not None:
            continue
        score += w
        ppm_sum += PPM_K / z
    return score, ppm_sum


OSD_LABELS = {"CAM_01": "DOCK 01-03", "CAM_02": "DOCK 04-06", "CAM_03": "BAG OPENING", "CAM_04": "INDUCTION",
              "CAM_05": "SCAN TUNNEL EXIT", "CAM_06": "SORTER WEST", "CAM_07": "SORTER MID", "CAM_08": "SORTER EAST",
              "CAM_09": "REJECT CHUTE", "CAM_10": "CHUTES C01-C06", "CAM_11": "CHUTES C07-C12",
              "CAM_12": "EXCEPTION BENCH", "CAM_13": "CAGE STAGING W", "CAM_14": "CAGE STAGING E",
              "CAM_15": "DOCK 07-09", "CAM_16": "DOCK 10-12", "CAM_17": "YARD NORTH", "CAM_18": "SOUTH AISLE",
              "CAM_19": "EXCEPTION STORE"}
CAMERA_VIEW = {}
CAMERA_DUTY = {s_[0]: s_[2][:4] for s_ in CAMERA_SPECS}


def place_camera(spec):
    """Search mount x height x yaw (±45° of centre, 5° steps) x tilt (15–65°) for the best duty coverage."""
    pts = duty_points(spec)
    if len(spec) > 9:
        CAMERA_VIEW[spec[0]] = spec[9]
    poses = [{"pos": [mx, my, h], "yaw": (yc + dy) % 360, "tilt": t}
             for mx, my, yc in spec[3] for h in spec[4] for dy in range(-45, 46, 5) for t in range(15, 66, 5)]
    view = spec[9] if len(spec) > 9 else {}
    if view.get("pose"):  # framed by hand (an installer's aim, reviewed on a still): no search
        mx, my, h = spec[3][0][0], spec[3][0][1], spec[4][0]
        return {"pos": [mx, my, h], "yaw": view["pose"]["yaw"] % 360, "tilt": view["pose"]["tilt"]}
    coarse = sorted(poses, key=lambda c: pose_score(c, pts, False), reverse=True)[:25]
    scored = [(pose_score(c, pts, True), c) for c in coarse]
    best = max(scored, key=lambda t: t[0])
    if not view:
        return best[1]
    # framing wishes are honoured only if coverage stays within 5 % of the best unconstrained pose
    pool = poses
    if view.get("min_roof"):  # the top of the frame must rise above the horizon to show the roof
        pool = [c for c in poses if c["tilt"] <= VFOV / 2 - 6]
    cand = sorted(pool, key=lambda c: pose_score(c, pts, False), reverse=True)[:60]
    ok = [(sc, c) for sc, c in ((pose_score(c, pts, True), c) for c in cand)
          if sc[0] >= 0.95 * best[0][0] and view_ok(c | {"id": spec[0]}, view)]
    if not ok:
        return best[1] | {"view_unmet": True}
    return max(ok, key=lambda t: (t[0], view_fractions(t[1] | {"id": spec[0]}).get("duty_fill", 0)))[1]


def ray_box_t(o, d, b):
    t0, t1 = 0.0, 1e9
    for i in range(3):
        if abs(d[i]) < 1e-12:
            if o[i] < b[i] or o[i] > b[i + 3]:
                return None
        else:
            ta, tb = (b[i] - o[i]) / d[i], (b[i + 3] - o[i]) / d[i]
            ta, tb = min(ta, tb), max(ta, tb)
            t0, t1 = max(t0, ta), min(t1, tb)
            if t0 > t1:
                return None
    return t0 if t0 > 1e-3 else None


def wall_boxes():
    """Building walls with door openings (mirrors build_hub.py), for what-the-camera-sees checks."""
    out = []
    for side in ("S", "N", "W", "E"):
        horiz = side in ("S", "N")
        length, fixed = (BW if horiz else BD), {"S": 0.0, "N": BD - 0.2, "W": 0.0, "E": BW - 0.2}[side]
        ops = sorted((d["centre"][0 if horiz else 1] - d["width"] / 2, d["centre"][0 if horiz else 1] + d["width"] / 2,
                      d["height"]) for d in DOORS if d["wall"] == side)
        cur, pieces = 0.0, []
        for a, b, hgt in ops + [(length, length, 0)]:
            if a > cur:
                pieces.append((cur, a, -1.2, EAVES))
            if b > a:
                pieces += [(a, b, -1.2, 0.0), (a, b, hgt, EAVES)]
            cur = b
        for a, b, z0, z1 in pieces:
            out.append((a, fixed, z0, b, fixed + 0.2, z1) if horiz else (fixed, a, z0, fixed + 0.2, b, z1))
    return out


WALLS = wall_boxes()


def view_fractions(cam, nx=24, ny=14, near_m=8.0):
    """Cast a grid of image rays; first hit decides: floor / wall / roof / outside / a nearby object blocking."""
    f, r, u = basis(cam["yaw"], cam["tilt"])
    o = cam["pos"]
    tally = {"floor": 0, "wall": 0, "roof": 0, "outside": 0, "near_block": 0, "object": 0}
    duty = CAMERA_DUTY.get(cam.get("id"))
    fill = 0
    for i in range(nx):
        for j in range(ny):
            a, b = (2 * (i + 0.5) / nx - 1) * TAN_H, (1 - 2 * (j + 0.5) / ny) * TAN_V
            d = [f[k] + a * r[k] + b * u[k] for k in range(3)]
            best, kind = 1e9, "outside"
            if d[2] < -1e-9:
                t = -o[2] / d[2]
                hx, hy = o[0] + t * d[0], o[1] + t * d[1]
                if 0 <= hx <= BW and 0 <= hy <= BD:
                    best, kind = t, "floor"
            if d[2] > 1e-9:
                t = (EAVES - 1.2 - o[2]) / d[2]  # truss bottom chords
                if t < best:
                    best, kind = t, "roof"
            for bx in WALLS:
                t = ray_box_t(o, d, bx)
                if t is not None and t < best:
                    best, kind = t, "wall"
            for bx in OCCLUDERS:
                t = ray_box_t(o, d, bx)
                if t is not None and t < best:
                    best, kind = t, ("near_block" if t * math.sqrt(sum(x * x for x in d)) < near_m else "object")
            tally[kind] += 1
            if duty and best < 1e8:  # where the ray lands, in plan: is it the camera's own duty area?
                hx, hy = o[0] + best * d[0], o[1] + best * d[1]
                fill += duty[0] - 0.3 <= hx <= duty[2] + 0.3 and duty[1] - 0.3 <= hy <= duty[3] + 0.3
    n = nx * ny
    out = {k: round(v / n, 3) for k, v in tally.items()}
    if duty:
        out["duty_fill"] = round(fill / n, 3)
    return out


def view_ok(cam, view):
    vf = view_fractions(cam)
    return (vf["wall"] <= view.get("max_wall", 1.0) and vf["near_block"] <= view.get("max_near_block", 1.0)
            and vf["roof"] >= view.get("min_roof", 0.0) and vf.get("duty_fill", 1.0) >= view.get("min_duty_fill", 0.0))


def duty_report(cam, spec):
    """Coverage of the duty area at the target PPM, and the PPM at the far edge (lowest-PPM point seen)."""
    x0, y0, x1, y1, z = spec[2]
    need = TARGET_PPM[spec[5]]
    seen, worst, total = 0, None, 0
    for i in range(20):
        for j in range(20):
            p = [x0 + (x1 - x0) * (i + 0.5) / 20, y0 + (y1 - y0) * (j + 0.5) / 20, z]
            if on_crossover(p[0], p[1]):
                continue
            total += 1
            ok, ppm, _ = sees(cam, p, "detect")
            if ok and ppm >= need:
                seen += 1
            if ok and (worst is None or ppm < worst[1]):
                worst = (p, ppm)
    return seen / total, worst


ZONE_EVAL = {"Z05": DECK + 0.2}  # loop: parcels ride on the deck; elsewhere parcel ~1 m (trolley / belt / bench)


def zone_coverage(cams):
    rows = {}
    for zid, name, kind, poly, _ in ZONES:
        if poly is None or zid in ("Z11", "Z13"):  # Z11 partly blind by design; Z13 office has no camera (privacy)
            continue
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        z = ZONE_EVAL.get(zid, 1.0)
        n = det = obs = 0
        for i in range(24):
            for j in range(24):
                p = [min(xs) + (max(xs) - min(xs)) * (i + 0.5) / 24, min(ys) + (max(ys) - min(ys)) * (j + 0.5) / 24, z]
                if zid == "Z04" and 19.5 <= p[0] <= 22.0 and 8.6 <= p[1] <= 10.4:
                    continue  # inside the closed tunnel: nobody can see in (bridged by the tunnel scan)
                if on_crossover(p[0], p[1]):
                    continue
                n += 1
                best = 0.0
                for c in cams:
                    ok, ppm, _ = sees(c, p, "detect")
                    if ok:
                        best = max(best, ppm)
                det += best >= TARGET_PPM["detect"]
                obs += best >= TARGET_PPM["observe"]
        rows[zid] = {"detect": round(det / n, 2), "observe": round(obs / n, 2)}
    return rows


def overlap(a, b, eps=1e-6):
    """Intersection of two (x0, y0, x1, y1) rects, or None (touching edges don't count)."""
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return (x0, y0, x1, y1) if x1 - x0 > eps and y1 - y0 > eps else None


def loop_distance(x, y):
    L = LOOP
    if L["west_cx"] <= x <= L["east_cx"]:
        return min(abs(y - L["south_y"]), abs(y - L["north_y"]))
    cx = L["west_cx"] if x < L["west_cx"] else L["east_cx"]
    return abs(math.hypot(x - cx, y - L["cy"]) - L["radius"])


def floor_obstacles():
    """Things people and forklifts must not walk / drive through (plan rects)."""
    obs = [((x - 0.2, y - 0.2, x + 0.2, y + 0.2), "column") for x, y in COLUMNS]
    obs.append(((54.6, 0.2, 59.8, 6.0), "office"))
    obs += [((c["x"] - 0.5, c["mouth_y"], c["x"] + 0.5, c["end_y"]), f"chute {c['id']}") for c in CHUTES]
    obs += [((c["x"] - 0.5, c["bag_frame_y"], c["x"] + 0.5, c["bag_frame_y"] + 0.8), f"bag frame {c['id']}")
            for c in CHUTES if c["bag_frame_y"]]
    for cv in CONVEYORS:
        hw = 0.3 if cv["kind"] == "telescopic" else 0.4
        for a, b in zip(cv["path"], cv["path"][1:]):
            obs.append(((min(a[0], b[0]) - hw, min(a[1], b[1]) - hw, max(a[0], b[0]) + hw, max(a[1], b[1]) + hw),
                        f"conveyor {cv['id']}"))
    obs.append(((19.5, 8.6, 22.0, 10.4), "scan tunnel"))
    obs += [(r, "sack rack") for r in RACKS]
    obs += [(r, name) for name, r in BENCHES]
    obs.append(((40.75, 5.6, 44.05, 7.2), "line B workstation (inductors + gaylords, stations.LINE_B)"))
    if LINE_A_LAYOUT == "b":  # the 4 induct points: tables, inductors and induct belts between feed and induction belt
        obs.append(((6.4, 9.95, 13.1, LINE_A_FEED_Y - 0.45), "line A workstation (tables, inductors, induct belts)"))
    return obs


def hits_loop(r, clearance):
    for i in range(13):
        for j in range(13):
            x, y = r[0] + (r[2] - r[0]) * i / 12, r[1] + (r[3] - r[1]) * j / 12
            if loop_distance(x, y) < 0.6 + clearance:
                return True
    return False


def circulation_checks(cams):
    res = {}
    obs = floor_obstacles()
    lanes = lane_rects()
    stairs = [((xo["x"] - xo["width"] / 2, ya, xo["x"] + xo["width"] / 2, yb), f"{xo['id']} stair")
              for xo in CROSSOVERS for ya, yb in (xo["south_stair_y"], xo["north_stair_y"])]
    # walkways: clear of machines and fixtures, never through the loop
    bad = [f"{wid} x {name}" for wid, r, _ in WALKWAYS for o, name in obs if overlap(r, o)]
    bad += [f"{wid} x loop" for wid, r, _ in WALKWAYS if hits_loop(r, 0.1)]
    res["walkways_clear"] = {"pass": not bad, "conflicts": bad}
    # crossover stairs: clear of machines and fixtures (belt B started inside the XO-1 south stair)
    bad = [f"{sn} x {name}" for sr, sn in stairs for o, name in obs if overlap(sr, o)]
    res["stairs_clear"] = {"pass": not bad, "conflicts": bad}
    # forklift lane: clear of everything, >= 0.5 m from the loop guard, crosses walkways only at zebras
    bad = [f"lane x {name}" for lr in lanes for o, name in obs + stairs if overlap(lr, o)]
    bad += ["lane x loop (< 0.5 m)" for lr in lanes if hits_loop(lr, 0.5)]
    crossings = []
    for wid, r, _ in WALKWAYS:
        for lr in lanes:
            ov = overlap(r, lr)
            if ov:
                z = next((zid for zid, zr, _ in ZEBRAS if all(
                    zr[k] - 1e-6 <= ov[k] for k in (0, 1)) and all(ov[k] <= zr[k] + 1e-6 for k in (2, 3))), None)
                crossings.append({"walkway": wid, "zebra": z})
                if z is None:
                    bad.append(f"lane x {wid} outside a zebra")
    res["forklift_lane_clear"] = {"pass": not bad, "conflicts": bad, "walkway_crossings": crossings,
                                  "route": "Z09 -> south aisle -> east aisle -> outbound dock Z12", "width_m": LANE_W}
    # crossovers: enough headroom over carriers + the biggest parcel; both feet land on a walkway or zebra
    rows = []
    for xo, base in ((CROSSOVERS[0], DECK), (CROSSOVERS[1], 1.0)):
        head = round(xo["deck_m"] - 0.2 - (base + 0.7), 2)  # 0.2 m deck structure, 0.7 m max parcel height
        feet = []
        for y in (xo["south_stair_y"][0], xo["north_stair_y"][1]):
            foot = (xo["x"] - 0.6, y - 0.1, xo["x"] + 0.6, y + 0.1)
            feet.append(any(overlap(foot, r) for _, r, _ in WALKWAYS) or any(overlap(foot, r) for _, r, _ in ZEBRAS))
        rows.append({"id": xo["id"], "clearance_over_max_parcel_m": head, "feet_on_walkway": feet,
                     "stair_angle_deg": round(math.degrees(math.atan2(xo["deck_m"],
                                                                      xo["south_stair_y"][1] - xo["south_stair_y"][0])))})
    ok = all(r["clearance_over_max_parcel_m"] >= 0.5 and all(r["feet_on_walkway"]) and r["stair_angle_deg"] <= 45
             for r in rows)
    res["crossovers"] = {"pass": ok, "detail": rows}
    # every chute's bag frame opens onto the bagging walkway W3
    w3 = next(r for wid, r, _ in WALKWAYS if wid == "W3")
    aisle = {c["id"]: round(w3[1] - (c["bag_frame_y"] + BAG_FRAME[1]), 2) for c in CHUTES if c["bag_frame_y"]}
    far = [k for k, v in aisle.items() if not 1.2 <= v <= 2.5]
    res["chutes_reachable"] = {"pass": not far, "bad": far,
                               "note": "every bag frame faces a bagging aisle 1.2–2.5 m deep that opens onto W3",
                               "aisle_depth_m": sorted(set(aisle.values()))}
    # every chute lip sits over a bag mouth (or the reject bin), above the rim, steep enough to slide
    rows, bad = [], []
    for c in CHUTES:
        if c["bag_frame_y"]:
            y0, y1, rim = c["bag_frame_y"], c["bag_frame_y"] + BAG_FRAME[1], BAG_FRAME[2]
        else:
            (y0, y1), rim = c["bin"]["y"], c["bin"]["size_m"][2]
        slope = math.degrees(math.atan2(DECK - 0.05 - c["lip_z"], c["end_y"] - c["mouth_y"]))
        ok = y0 + 0.1 <= c["end_y"] <= y1 - 0.1 and 0.05 <= c["lip_z"] - rim <= 0.35 and slope >= 17
        rows.append({"chute": c["id"], "lip_y": c["end_y"], "mouth_y": [y0, y1], "lip_above_rim_m": round(c["lip_z"] - rim, 2),
                     "slope_deg": round(slope, 1), "pass": ok})
        if not ok:
            bad.append(c["id"])
    res["chute_lips_over_bag_mouths"] = {"pass": not bad, "failed": bad, "detail": rows}
    # fire exits open onto a walkway
    rows, bad = [], []
    for d in DOORS:
        if d["kind"] not in ("fire_exit", "staff"):
            continue
        cx, cy = d["centre"]
        probe = (cx - 0.5, cy - 0.6, cx + 0.5, cy + 0.6) if d["wall"] in ("S", "N") else (cx - 0.6, cy - 0.5,
                                                                                           cx + 0.6, cy + 0.5)
        on = [wid for wid, r, _ in WALKWAYS if overlap(probe, r)]
        rows.append({"door": d["id"], "walkway": on})
        if not on:
            bad.append(d["id"])
    res["fire_exits_on_walkway"] = {"pass": not bad, "failed": bad, "detail": rows}
    # ADVISORY: fire exits filmed from inside (a fire exit is the classic theft route)
    fe = {}
    for d in DOORS:
        if d["kind"] in ("fire_exit", "staff"):
            cx, cy = d["centre"]
            p = [cx, cy + 1.0, 1.2] if d["wall"] == "S" else [cx - 1.0, cy, 1.2]
            fe[d["id"]] = [c["id"] for c in cams if sees(c, p, "detect")[0]]
    res["advisory_fire_exits_filmed"] = {"pass": all(fe.values()), "detail": fe}
    # ADVISORY: forklift lane coverage (oversize parcels travel the lane, not the belts)
    pts_, seen = [], []
    for a, b in zip(LANE, LANE[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1])))
        for k in range(n):
            p = [a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n, 1.2]
            pts_.append(p)
            seen.append(any(sees(c, p, "detect")[0] for c in cams))
    gaps, run = [], []
    for p, s_ in zip(pts_ + [None], seen + [True]):  # samples are ~1 m apart, so len(run) ≈ metres unseen
        if not s_:
            run.append(p)
            continue
        if len(run) >= 3:
            gaps.append({"from_m": [round(v, 1) for v in run[0][:2]], "to_m": [round(v, 1) for v in run[-1][:2]],
                         "length_m": len(run)})
        run = []
    res["advisory_forklift_lane_filmed"] = {"pass": not gaps, "fraction_seen": round(sum(seen) / len(seen), 2),
                                            "unseen_stretches_over_3m": gaps}
    return res


def known_gaps(checks):
    """Everything no camera sees, written down so Spoor's 'no coverage' answers can be scored against it."""
    gaps = [
        {"where": "BLIND_NW", "kind": "deliberate", "bridged_by": "nothing — Spoor must answer 'no coverage'"},
        {"where": "inside the scan tunnel (x 19.5–22.0)", "kind": "closed machine", "bridged_by": "SP-TUNNEL event"},
        {"where": "0.6 m between carrier and chute mouth, every chute", "kind": "deck rail hides it",
         "bridged_by": "SP-DIV-* divert-confirm events"},
    ]
    lane = checks["advisory_forklift_lane_filmed"]
    for g in lane["unseen_stretches_over_3m"]:
        gaps.append({"where": f"forklift lane {g['from_m']} -> {g['to_m']} ({g['length_m']} m)", "kind": "advisory",
                     "bridged_by": "SP-OVERSIZE and SP-LOAD-OUT-* scans either side"})
    for door, cams_ in checks["advisory_fire_exits_filmed"]["detail"].items():
        if not cams_:
            gaps.append({"where": f"fire exit {door}", "kind": "advisory", "bridged_by": "door alarm only"})
    for cid in checks["advisory_cameras_watch_each_other"]["unwatched"]:
        gaps.append({"where": f"{cid} mount", "kind": "advisory (tamper)", "bridged_by": "video-loss / scene-change"})
    return gaps


def bearing(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def run_checks(cams):
    res = {}
    by_id = {c["id"]: c for c in cams}
    # 1. every scan point visible to >= 1 camera at observe level
    sp_rows, failed = [], []
    for sid, kind, zone, xyz, dom, ev in SCAN_POINTS:
        seen = []
        for c in cams:
            ok, ppm, _ = sees(c, list(xyz), "observe")
            if ok:
                seen.append({"camera": c["id"], "ppm": round(ppm)})
        sp_rows.append({"id": sid, "visible_by": seen})
        if not seen:
            failed.append(sid)
    res["scan_points_visible"] = {"pass": not failed, "failed": failed}
    # 2. overlap at zone handoffs: the same point seen from both sides, or (hidden segment) exit and entry points
    #    each seen, with the gap bridged by a scan of known transit time
    lp = DECK + 0.2
    handoffs = [
        ("Z01 south <-> north", (3.0, 17.0, 1.0), None, ["CAM_01"], ["CAM_02"]),
        ("Z02 bench -> collector belt", (5.2, 22.0, 1.0), None, ["CAM_03"], ["CAM_02"]),
        ("Z01 collector -> Z03 induction", (5.6, 9.5, 1.0), None, ["CAM_01"], ["CAM_04"]),
        ("Z09 oversize -> Z03 (same camera)", (12.0, 6.5, 1.0), None, ["CAM_04"], ["CAM_04"]),
        ("Z03 -> Z04 -> loop (closed tunnel, bridged by SP-TUNNEL)", (19.4, 9.5, 1.0), (22.1, 9.5, lp),
         ["CAM_04"], ["CAM_05"]),
        ("Z04 exit -> Z05 merge", (27.6, 9.5, lp), None, ["CAM_05"], ["CAM_06"]),
        ("Z05 west <-> middle (south straight)", (34.0, 11.0, lp), None, ["CAM_06"], ["CAM_07"]),
        ("Z05 west <-> middle (north straight)", (34.0, 19.0, lp), None, ["CAM_06"], ["CAM_07"]),
        ("Z05 middle <-> east (south straight)", (44.5, 11.0, lp), None, ["CAM_07"], ["CAM_08"]),
        ("Z05 middle <-> east (north straight)", (44.5, 19.0, lp), None, ["CAM_07"], ["CAM_08"]),
        ("Z05 -> Z06 divert into C01 (rail hides 0.6 m; bridged by SP-DIV-C01)", (CHUTE_X[0], 19.0, lp + 0.1),
         (CHUTE_X[0], 19.8, lp), ["CAM_08"], ["CAM_10"]),
        ("Z05 -> Z06 divert into C12 (bridged by SP-DIV-C12)", (CHUTE_X[11], 19.0, lp + 0.1), (CHUTE_X[11], 19.8, lp),
         ["CAM_06", "CAM_07"], ["CAM_11"]),
        ("Z06 C06 | C07 boundary (XO-1 foot)", ((CHUTE_X[5] + CHUTE_X[6]) / 2, 23.8, 1.1), None, ["CAM_10"],
         ["CAM_11"]),
        ("Z05 -> Z07 divert into reject (bridged by SP-DIV-REJECT)", (29.3, 19.0, lp + 0.1), (29.3, 19.8, lp),
         ["CAM_06"], ["CAM_09"]),
        ("Z07 -> Z08 crate to bench", (28.4, 22.0, 1.0), None, ["CAM_09"], ["CAM_12"]),
        ("Z08 -> Z03 walk back to induction", (21.0, 13.5, 1.0), None, ["CAM_12", "CAM_06"], ["CAM_04", "CAM_05"]),
        ("Z06 -> Z10 bags carried to cages (west)", (34.0, 25.6, 1.0), None, ["CAM_11", "CAM_09"], ["CAM_13"]),
        ("Z06 -> Z10 bags carried to cages (east)", (46.0, 25.6, 1.0), None, ["CAM_10"], ["CAM_14"]),
        ("Z10 west <-> east", (38.5, 29.0, 1.0), None, ["CAM_13"], ["CAM_14"]),
        ("Z10 -> Z12 cages to doors (west)", (32.0, 33.0, 1.0), None, ["CAM_13"], ["CAM_15"]),
        ("Z10 -> Z12 cages to doors (east)", (46.0, 33.0, 1.0), None, ["CAM_14"], ["CAM_16"]),
        ("Z12 door 12 -> Z14 yard (through the door)", (49.0, 39.5, 1.5), (49.0, 40.9, 1.5), ["CAM_16"],
         ["CAM_17"]),
    ]
    rows, failed = [], []
    for name, pa, pb, a_ids, b_ids in handoffs:
        pb_ = pb or pa
        a = [i for i in a_ids if sees(by_id[i], list(pa), "detect")[0]]
        b = [i for i in b_ids if sees(by_id[i], list(pb_), "detect")[0]]
        ok = bool(a) and bool(b)
        rows.append({"handoff": name, "point_a": list(pa), "point_b": list(pb_), "side_a": a, "side_b": b, "pass": ok})
        if not ok:
            failed.append(name)
    res["handoff_overlap"] = {"pass": not failed, "failed": failed, "detail": rows}
    # 3. reject chute covered at recognise level
    rej = [c["id"] for c in cams if sees(c, [29.3, 21.6, 1.0], "recognise")[0]]
    res["reject_chute_camera"] = {"pass": bool(rej), "cameras_at_recognise": rej}
    # 4. dock doors filmed from inside at an angle: the door's own dock camera looks at it >= 25° off the door
    #    normal (not straight out into daylight). Other cameras that catch a door nearly head-on are listed as glare.
    rows, failed = [], []
    for d in DOORS:
        if d["kind"] != "dock":
            continue
        normal = {"W": 180.0, "N": 90.0}[d["wall"]]
        inward = [1.0, d["centre"][1], 1.5] if d["wall"] == "W" else [d["centre"][0], BD - 1.0, 1.5]
        viewers = []
        for c in cams:
            if c["zone"] == "Z14" or not sees(c, inward, "detect")[0]:
                continue
            ang = abs((bearing(c["pos"], d["centre"]) - normal + 180) % 360 - 180)
            viewers.append({"camera": c["id"], "angle_off_normal_deg": round(ang),
                            "dock_camera": c["zone"] in ("Z01", "Z12")})
        ok = any(v["dock_camera"] and v["angle_off_normal_deg"] >= 25 for v in viewers)
        glare = [v["camera"] for v in viewers if v["angle_off_normal_deg"] < 25]
        rows.append({"door": d["id"], "viewers": viewers, "glare_risk": glare, "pass": ok})
        if not ok:
            failed.append(d["id"])
    res["dock_doors_inside_angled"] = {"pass": not failed, "failed": failed, "detail": rows}
    # 5. blind corner really blind (<= 5 % of it seen at detect level by anything) and its approach is filmed
    pts, seen = 0, 0
    bp = BLIND["polygon"]
    for i in range(1, 19):
        for j in range(1, 13):
            p = [bp[0][0] + (bp[1][0] - bp[0][0]) * i / 19, bp[0][1] + (bp[2][1] - bp[0][1]) * j / 13, 0.9]
            pts += 1
            seen += any(sees(c, p, "detect")[0] for c in cams)
    entry = [c["id"] for c in cams if sees(c, [17.0, 32.0, 1.0], "detect")[0]]
    res["blind_corner"] = {"pass": seen / pts <= 0.05 and bool(entry), "fraction_seen": round(seen / pts, 3),
                           "approach_seen_by": entry}
    # 6. ADVISORY (pack rule, not in the owner's checklist): cameras watch each other, so tampering is filmed
    watched = {c["id"]: [o["id"] for o in cams if o is not c and sees(o, list(c["pos"]), "detect")[0]] for c in cams}
    res.update(circulation_checks(cams))
    weigh = {x: [c["id"] for c in cams if sees(c, [x, 9.5, DECK + 0.2], "observe")[0]] for x in (17.6, 18.25, 18.9)}
    res["weigh_section_filmed"] = {"pass": all(weigh.values()), "detail": weigh,
                                   "note": "not a scan point (see machines.scan_tunnel.weigh_section); filmed anyway"}
    res["advisory_cameras_watch_each_other"] = {
        "pass": all(watched.values()), "unwatched": [k for k, v in watched.items() if not v],
        "note": "high-mounted cameras tilted down rarely see each other's mounts; tampering shows up instead as "
                "video loss / scene change, which the backend records as a coverage gap"}
    return res, sp_rows


# ----------------------------------------------------------------------------------------------- assets
PH, ACG, SF, QT = "https://polyhaven.com/a/", "https://ambientcg.com/view?id=", "https://sketchfab.com/3d-models/", ""
CC0, BY = "CC0", "CC BY 4.0"
ASSETS = [  # zone, item, source name, url, licence, found/build, author (CC BY credit)
    ("shell", "Wall + roof cladding", "Box Profile Metal Sheet", PH + "box_profile_metal_sheet", CC0, "found", "Poly Haven"),
    ("shell", "Cladding alt.", "Corrugated Steel 005", ACG + "CorrugatedSteel005", CC0, "found", "ambientCG"),
    ("shell", "Painted steel (columns, rails)", "Painted Metal 016 / 006", ACG + "PaintedMetal016", CC0, "found", "ambientCG"),
    ("shell", "Floor", "Smooth Concrete Floor (low roughness for epoxy look)", PH + "smooth_concrete_floor", CC0, "found", "Poly Haven"),
    ("shell", "Floor alt.", "Concrete 047 A", ACG + "Concrete047A", CC0, "found", "ambientCG"),
    ("shell", "Floor markings", "Road Lines 001 (reference) + built decal", ACG + "RoadLines001", CC0, "found", "ambientCG"),
    ("shell", "Dock door shutter", "Rolling Shutter", SF + "rolling-shutter-bd01deecf45d4b429e97c0cb23116f06", BY, "found", "Origicube"),
    ("shell", "Shutter texture", "Painted Metal Shutter", PH + "painted_metal_shutter", CC0, "found", "Poly Haven"),
    ("shell", "Steel frame reference", "Metal Frame of the Warehouse", SF + "metal-frame-of-the-warehouse-05937c3272b548dfaef68b2094a97786", BY, "found (reference)", "vkmd24"),
    ("shell", "Columns + trusses", "I-beam profiles", None, None, "build", None),
    ("shell", "Dock plate / leveller", "flat steel plate", None, None, "build", None),
    ("shell", "High-bay LED lights", "disc + emission", None, None, "build", None),
    ("shell", "Outside light", "Overcast Industrial Courtyard (HDRI)", PH + "overcast_industrial_courtyard", CC0, "found", "Poly Haven"),
    ("shell", "Outside light alt.", "Factory Yard (HDRI)", PH + "factory_yard", CC0, "found", "Poly Haven"),
    ("shell", "Inside light reference", "Empty Warehouse 01 (HDRI)", PH + "empty_warehouse_01", CC0, "found (reference)", "Poly Haven"),
    ("shell", "Fire extinguisher", "Korean Fire Extinguisher 01", PH + "korean_fire_extinguisher_01", CC0, "found", "Poly Haven"),
    ("shell", "Wet floor sign", "simple folded sign", None, None, "build", None),
    ("shell", "Crossover stairs + bridge (XO-1, XO-2)", "steel stair, grating deck, yellow handrails", None, None, "build", None),
    ("shell", "Fire exit doors + KELUAR signs", "push-bar door + emissive green sign", None, None, "build", None),
    ("shell", "Walkway / forklift lane / zebra markings", "floor decals", None, None, "build", None),
    ("shell", "Convex safety mirror", "chrome sphere cap on a bracket", None, None, "build", None),
    ("Z01", "Telescopic conveyor", "2–3 nested belt sections", None, None, "build", None),
    ("Z01", "Belt surface", "Rubber 001", ACG + "Rubber001", CC0, "found", "ambientCG"),
    ("Z02", "Bag-opening bench", "Steel Frame Shelves 01", PH + "steel_frame_shelves_01", CC0, "found", "Poly Haven"),
    ("Z03", "Straight belts", "Belt Conveyor", SF + "belt-conveyor-b789d1fda888440387ae7750c852ade3", BY, "found", "jemi_inovasi"),
    ("Z03", "Straight belts alt.", "Simple rubber conveyor", SF + "simple-rubber-conveyor-0819b51c59c3407cb98f0e2c75029e30", BY, "found", "scailman"),
    ("Z03", "Belt modules alt.", "Conveyor Modular Pack", SF + "conveyor-modular-pack-bf86b7433e824efeba77166d01f5e368", BY, "found", "chaschinkaa"),
    ("Z04", "Scan tunnel (DWS)", "sheet-metal box + light bars + weigh section", None, None, "build", None),
    ("Z04", "Roller section", "Industrial Conveyer Roller (modular)", SF + "industrial-conveyer-roller-modular-4736d0c18e7047969639988883f0ad56", BY, "found", "parabatharva4"),
    ("Z04", "Curve into the loop", "Curved conveyor belt system", SF + "curved-conveyor-belt-system-39ff85715a134cd2a09f6e78a9dce232", BY, "found", "ooowedyn"),
    ("Z05", "Cross-belt loop", "curve path + repeated carrier (Array + Curve)", None, None, "build", None),
    ("Z05", "Loop frame", "Galvanized Sheet Metal", PH + "galvanized_sheet_metal", CC0, "found", "Poly Haven"),
    ("Z06", "Chutes", "bent plane + solidify (refs: SF Chute, chute 3D)", None, None, "build", None),
    ("Z06", "Chute reference", "Chute", SF + "chute-98d4616410b347439ed0f7457424fec3", BY, "found (reference)", "Amine115"),
    ("Z06", "Chute reference", "chute 3D", SF + "chute-3d-d5202c88124f41bdad4b6cf9ef61d03b", BY, "found (reference)", "marcosprojetos"),
    ("Z06", "Bag frame", "steel tube frame + sack", None, None, "build", None),
    ("Z06", "Sacks", "Compost Bags (shape) / Cement Bag", PH + "compost_bags", CC0, "found", "Poly Haven"),
    ("Z06", "Sacks alt.", "big bag, großer Sack", SF + "big-bag-groer-sack-8db0bd844c68446ca0afcaf32078aaa7", BY, "found", "frtmngl"),
    ("Z06", "Mail bag", "Mail Bag", SF + "mail-bag-1310de4c577b4e17ace4e2cafd6fdf97", BY, "found", "TiesG"),
    ("Z06", "Handheld scanners", "Handheld Barcode Scanner with Keypad", SF + "handheld-barcode-scanner-with-keypad-79d132dc44b344f7a019921e1b31c1b6", BY, "found", "cygnos"),
    ("Z07", "Reject chute + crate", "built chute + crate", None, None, "build", None),
    ("Z08", "Exception desk", "Metal Office Desk", PH + "metal_office_desk", CC0, "found", "Poly Haven"),
    ("Z08", "Tool cart", "Tool Cart", PH + "tool_cart", CC0, "found", "Poly Haven"),
    ("Z08", "Cabinet", "Drawer Cabinet", PH + "drawer_cabinet", CC0, "found", "Poly Haven"),
    ("Z08", "Label printer", "small box with paper slot", None, None, "build", None),
    ("Z09", "Pallets", "Euro Pallet", SF + "euro-pallet-a38a3c7ac5894db6957bebcd400a7e75", BY, "found", "jkvarel1701"),
    ("Z09", "Pallets alt.", "Plastic Pallet", SF + "plastic-pallet-0699da1b0dd04c13b5c6731c8dda75d1", BY, "found", "billyNG"),
    ("Z09", "Hand pallet jack", "Hand pallet jack", SF + "hand-pallet-jack-9db0a4f5bd6e4b35b46f86ff272387c1", BY, "found", "Cry11y"),
    ("Z09", "Electric pallet jack", "Electric Pallet Jack with Controls", SF + "electric-pallet-jack-with-controls-acc0b7593fc9469f9ee3fd5949cd6909", BY, "found", "cygnos"),
    ("Z10", "Roll cage 0.72 x 0.80 x 1.80 m", "tube frame + Fence 006 mesh", ACG + "Fence006", CC0, "build (+ found texture)", "ambientCG"),
    ("Z11", "Folded-sack shelves", "Steel Frame Shelves 02 / 03", PH + "steel_frame_shelves_02", CC0, "found", "Poly Haven"),
    ("Z13", "Office chair", "Plastic Monobloc Chair 01", PH + "plastic_monobloc_chair_01", CC0, "found", "Poly Haven"),
    ("Z13", "Computer desk + monitor", "Computer Desk and Monitor", SF + "computer-desk-and-monitor-cdb5226d2c3a4fc89e9b422307f81ce5", BY, "found", "limlam"),
    ("Z13", "Office lights", "Mounted Fluorescent Lights", PH + "mounted_fluorescent_lights", CC0, "found", "Poly Haven"),
    ("Z14", "Barriers", "Concrete Road Barrier / 02", PH + "concrete_road_barrier", CC0, "found", "Poly Haven"),
    ("Z14", "Cones", "Traffic Cones", SF + "traffic-cones-822f8e30bad4469e808b8c32d9c8aa10", BY, "found", "hgowl22"),
    ("Z14", "Cone alt.", "Traffic Cone", SF + "traffic-cone-e9c9c21db7c44c4fb901e0c55bb86934", BY, "found", "MrScanMan"),
    ("Z14", "Bollards", "steel cylinders", None, None, "build", None),
    ("Z14", "Lorry (3–5 t box)", "Box Truck [Game Asset]", SF + "box-truck-game-asset-959e25ad21014bcf9066d3f6f7e7ecb2", BY, "found (check: no real badges)", "jsabbott"),
    ("Z14", "Lorry alt.", "Lorry", SF + "lorry-3fb4343374304f51ae190d2a3625a302", BY, "found (check: no real badges)", "businessyuen"),
    ("Z14", "Lorry alt.", "Lorry / Truck (with cargo container)", SF + "lorry-truck-with-cargo-container-f3651bc895224e6199eace68efa14144", BY, "found (check: no real badges)", "SRI_LABS"),
    ("Z14", "Trailer (linehaul)", "Truck Trailer FREE", SF + "truck-trailer-free-575958a53e3d4e9f8bcfb1ee2cef67bf", BY, "found", "NLM-Group"),
    ("Z14", "Delivery van", "European Delivery Van (remove maker badges)", SF + "european-delivery-van-0b2f1ad95a79419f9a092420024d329c", BY, "found", "evan.hiltz"),
    ("all", "CCTV bullet (hooded)", "Security Camera 02", PH + "security_camera_02", CC0, "found", "Poly Haven"),
    ("all", "CCTV wall mount", "Security Camera 01", PH + "security_camera_01", CC0, "found", "Poly Haven"),
    ("all", "CCTV dome", "Dome Camera [FREE]", SF + "dome-camera-free-ab8d2a64d3894deba9af23203ba0368d", BY, "found", "MiguelNevesRamos"),
    ("props", "Cardboard boxes", "Cardboard Box 01", PH + "cardboard_box_01", CC0, "found", "Poly Haven"),
    ("props", "Cardboard boxes (sizes)", "Cardboard Boxes Pack - Taped, 100 Sizes", SF + "cardboard-boxes-set-16-sizes-e2bfa6f3822241a49553b44c55ef3082", BY, "found", "alex-human"),
    ("props", "Cardboard texture", "Cardboard 001 / 004", ACG + "Cardboard001", CC0, "found", "ambientCG"),
    ("props", "Poly flyers", "cloth-sim pillow, several sizes", None, None, "build", None),
    ("props", "Shipping labels 10 x 15 cm", "decal: fictional brand, fake barcode", None, None, "build", None),
    ("props", "Forklift (electric)", "Forklift Truck", SF + "forklift-truck-1567f5f71c1a40eebe487b1b8f570250", BY, "found (licence confirmed in the .glb metadata: CC-BY-4.0)", "Kray Ewan (sketchfab.com/kraysdzine)"),
    ("props", "Forklift alt.", "forklift", SF + "forklift-4438235cea46432aa9ce0c6bdacbc848", BY, "not used (Forklift Truck chosen)", "leoxx300"),
    ("people", "Workers (realistic)", "Construction Worker in Safety Vest", SF + "construction-worker-in-safety-vest-0ee4e54dc78b45f9bb7e26fb0d000f7e", BY, "found (rigged on Mixamo; decimated to 30k tris; shirt / vest colour variants)", "Nitoktris (sketchfab.com/mr.sinankaba)"),
    ("people", "Workers (rigged)", "Worker Man Rigged", SF + "worker-man-rigged-ca5d218c51e04c3ba96929dbe8f9b68e", BY, "not used (unclothed base body; kept out of renders)", "aayushbhattarai"),
    ("people", "Workers (CC0 base)", "Quaternius Universal Base Characters", "https://quaternius.com/packs/universalbasecharacters.html", CC0, "not used (Rocketbox chosen)", "Quaternius"),
    ("people", "Workers: 11 adults (F01, F04, F06, F07, F09, F13, F17, M04, M05, M09, M12; only flat-shoed ones work the floor) + 24 clips", "Microsoft Rocketbox avatars and animations", "https://github.com/microsoft/Microsoft-Rocketbox", "MIT", "found", "Microsoft (Rocketbox)"),
    ("people", "Worker handling motion (reach / pick / carry / place), retargeted; per-file list in assets/mocap/sources.csv", "AndyData-lab-onePerson (Xsens BVH + action/posture labels)", "https://zenodo.org/records/3254403 (doi:10.5281/zenodo.3254403)", BY, "found", "Maurice, Malaisé, Ivaldi, Rochel, Amiot, Paris, Richard, Fritzsche (2019)"),
    ("people", "Worker walking / backward walk / idle, retargeted", "100STYLE (BVH, Neutral style)", "https://zenodo.org/records/8127870 (doi:10.1145/3522618)", BY, "found", "Ian Mason, Sebastian Starke, Taku Komura (2022)"),
    ("signs", "Dock door number font", "Barlow Condensed Bold", "https://github.com/jpt/barlow", "OFL 1.1", "found", "The Barlow Project Authors"),
]  # fmt: skip
EXCLUDED = [  # url, licence found, reason
    ("Dome Security Camera", SF + "dome-security-camera-a5c49eefb2564c76b09aba0dc7a4d203", "CC BY-NC", "non-commercial"),
    ("Loading dock", SF + "loading-dock-84a7db0502a34121a0d2c8e481345b08", "CC BY-NC-SA", "non-commercial"),
    ("Loading Docks", SF + "loading-docks-da3471de4c7740aab2af9a06ef3c25b3", "CC BY-NC-SA", "non-commercial"),
    ("Office Chair", SF + "office-chair-95160ce5a52f4e379f66527d2735d96c", "CC BY-NC", "non-commercial"),
    ("Bollards", SF + "bollards-b5ae04dfd20b404f8a3d2e887f997c8b", "Sketchfab Free Standard", "not CC0 / CC BY"),
    ("[CC0] Free Cardboard Box", SF + "cc0-free-cardboard-box-e7a46c7b163c477296a3986323ccc826", "Sketchfab Free Standard", "title says CC0 but the licence field is Free Standard"),
    ("Nissan Caravan Detailed 3D Van Model", SF + "nissan-caravan-detailed-3d-van-model-bfddc35e8b40441cbaa291ef0b120935", "Sketchfab Free Standard", "not CC0 / CC BY; real brand"),
    ("Steel Beam A", SF + "steel-beam-a-3e20dd0a445f4ce49aa6495d08641f19", "Sketchfab Free Standard", "not CC0 / CC BY (I-beams are built instead)"),
    ("Container Trailer Chassis", SF + "container-trailer-chassis-4179e400ef464b958bcf8416e11f87df", "CC BY-SA", "ShareAlike; CC BY alternative exists"),
    ("Wooden Pallets - CC0 Game Asset", SF + "wooden-pallets-cc0-game-asset-a9f841eab92b460f939a115dab968351", "CC BY-SA", "title says CC0 but licence is BY-SA; CC BY alternatives exist"),
    ("Workbench", SF + "workbench-1f749d9458d7497e956991033ba827e2", "CC BY-SA", "ShareAlike; Poly Haven CC0 alternative exists"),
    ("Wet Floor Sign 01 (Poly Haven)", PH + "wet_floor_sign_01", "—", "not found on Poly Haven; built instead"),
]  # fmt: skip

OTHER_TERMS = [  # used in renders under non-CC terms; raw files never committed or redistributed
    ("Mixamo animations: walk, carry box, lift box, idle, push cart", "https://www.mixamo.com",
     "Adobe Mixamo terms (free with an Adobe account; not CC)",
     "animate the two CC BY workers in renders; raw FBX stay in assets/hub/build/third_party/mixamo/ (gitignored)"),
]
ASSUMPTIONS = [
    ("A1", "Building footprint", "60 x 40 m, demo scale", "pack assumption; small enough for ~18 cameras; real Malaysian hubs are 6–10x bigger"),
    ("A2", "Column grid", "12 m bays along X; interior column line at Y = 25 m (spans 25 m + 15 m)", "owner-approved pushback: keeps columns out of the sorter and chutes and gives camera mounts between bagging and staging"),
    ("A3", "Eaves height", "11 m", "within the pack's 10–12 m (a Shah Alam shed lists 12 m clear)"),
    ("A4", "Dock doors", "3.0 x 3.0 m, centres 4.0 m apart, dock height 1.2 m", "centre spacing within Blue Giant's 3.7–4.3 m; opening and dock height are assumptions; leveller plate covers lorry/trailer deck differences"),
    ("A5", "Sorter deck height", "1.5 m", "owner-approved: chutes need enough drop (1.5 -> 1.0 m over 2 m) to slide convincingly"),
    ("A6", "Loop size", f"straights 22 m, radius 4 m, length {LOOP_LEN:.1f} m (~{LOOP_LEN / 0.7:.0f} carriers at 0.7 m)", "radius per FORTNA minimum; length chosen for 12 chutes + reject on one side (Skynet Hounslow-style, chutes one side)"),
    ("A18", "Bag frame", f"{BAG_FRAME[0]} x {BAG_FRAME[1]} m, rim {BAG_FRAME[2]} m; chutes 1.3 m long, lip {CHUTE_LIP_Z} m", "no published size found; sized so each chute lip sits 0.1 m above the rim over the bag mouth at a 19° slope (cardboard on steel slides from ~17°), leaving a 1.8 m bagging aisle before walkway W3"),
    ("A7", "Chute width / pitch", "1.0 m wide at 1.5 m pitch; 2.8 m gap between C06 and C07", "width owner-approved (max parcel 1.0 x 0.7 x 0.7 m); pitch cut from 1.6 to 1.5 m so a crossover (XO-1) can land between C06 and C07 while C12 still clears the reject chute"),
    ("A8", "Camera poses", "searched per camera", "height / yaw / tilt picked by a search over real mount points (column, drop-pole, wall bracket) to cover each camera's duty area at its PPM target, with occlusion — not guessed"),
    ("A14", "Crossovers", "1.2 m wide; deck 3.3 m over the loop, 2.4 m over the induction belt; stairs ~42°", "deck = carrier/belt height + 0.7 m max parcel + 0.2 m structure + clearance; industrial stairs stay at or under 45°"),
    ("A15", "Fire exits", "3 x 1.0 m push-bar doors (FE-1, FE-2 south; FE-3 east) + staff door", "positions per owner; egress distances NOT checked against Malaysian UBBL / Bomba rules — fictional hub, not a compliant design"),
    ("A16", "Walkways and forklift lane", "walkways 1.2 m; one forklift lane 3.0 m; 4 zebra crossings", "common warehouse practice, no Malaysian source; lane keeps >= 0.5 m from the loop guard"),
    ("A17", "Supervisor office", "5.2 x 5.8 m (was 5.2 x 8.8 m)", "shortened so the forklift lane can pass between the office and the loop's east curve"),
    ("A13", "Sack racks", "3.0 m high around the NW store", "screen the deliberate blind corner; steel racking of folded sacks and nested empty cages is normal in hubs"),
    ("A9", "Floor lines", "100 mm yellow", "pack assumption"),
    ("A10", "Labels", "10 x 15 cm", "the common 4 x 6 in thermal shipping-label size (industry standard, not a measured Malaysian figure)"),
    ("A11", "Truck yard depth", "18 m outside each dock wall", "room for a 12 m lorry plus manoeuvring; assumption"),
    ("A12", "Camera spec", f"{IMG_W} x {IMG_H}, {HFOV} x {VFOV} deg; sensor up to {SENSOR_MAX_FPS} fps, recorded at {FPS} fps", "sensor figures copied from a real 4MP 2.8 mm dome datasheet (brand kept off the model); recording at 10 fps is an owner decision to fit the render budget and is common NVR practice"),
]  # fmt: skip

CAMERA_REALISM = {
    "codec": "H.265, ~2 Mbps at 2688 x 1520 / 15 fps (low bitrate: smeared static background), keyframe every 30 frames",
    "noise": "sensor grain before encoding, stronger in dark corners; temporal denoise ghosting on moving people",
    "lens": "mild barrel distortion + vignette + soft edges (2.8 mm wide lens); exact k1 per camera in render_truth.yaml",
    "exposure": "fixed per camera",
    "osd": "camera name + date/time burned in top-left, from the camera's OWN drifting clock",
    "clock": "own offset and drift per camera — evaluator-only values in render_truth.yaml; Spoor must estimate them",
}
SPECIAL_REALISM = {
    "CAM_01": {"exposure": "auto exposure: dims and shifts white balance when a door opens (1–2 s)", "defect": "dome smudge"},
    "CAM_02": {"exposure": "auto exposure on door openings"},
    "CAM_06": {"rolling_shutter": "slight skew on fast carriers"},
    "CAM_07": {"rolling_shutter": "slight skew on fast carriers"},
    "CAM_08": {"rolling_shutter": "slight skew on fast carriers", "mount_defect": "tilted 1.5 deg (horizon slightly off)"},
    "CAM_15": {"exposure": "auto exposure on door openings"},
    "CAM_16": {"exposure": "auto exposure on door openings", "defect": "spider web on dome (some clips)"},
    "CAM_17": {"exposure": "outdoor; would switch to IR B/W only in a night scenario"},
    "CAM_18": {"exposure": "daylight bloom when FE-2 is propped open", "defect": "long view down the aisle: soft far end"},
}
RENDER_TRUTH_CLOCKS = {  # evaluator-only (seconds offset, ppm drift, lens k1)
    "CAM_01": (+3.2, 12), "CAM_02": (-1.8, -8), "CAM_03": (+0.6, 5), "CAM_04": (+7.4, 40), "CAM_05": (-2.5, 15),
    "CAM_06": (+1.1, -20), "CAM_07": (+4.9, 30), "CAM_08": (-0.7, 6), "CAM_09": (+2.3, -12), "CAM_10": (-3.6, 18),
    "CAM_11": (+0.2, 4), "CAM_12": (+5.5, -25), "CAM_13": (-1.2, 9), "CAM_14": (+2.8, 14), "CAM_15": (-4.1, -30),
    "CAM_16": (+6.0, 22), "CAM_17": (-2.2, 10), "CAM_18": (+1.6, -14), "CAM_19": (-2.9, -17),
}

SCENARIOS = [  # name, zones, cameras in play (the evidence), note
    ("Control path", "Z01→Z03→Z04→Z05→Z06→Z10→Z12",
     ["CAM_01", "CAM_02", "CAM_04", "CAM_05", "CAM_06", "CAM_07", "CAM_08", "CAM_10", "CAM_11", "CAM_13", "CAM_14",
      "CAM_15", "CAM_16"], "rendered on all cameras"),
    ("No-read rework (loops, exits at reject chute)", "Z04→Z05→Z07→Z08→Z03",
     ["CAM_04", "CAM_05", "CAM_06", "CAM_07", "CAM_08", "CAM_09", "CAM_12"], ""),
    ("Relabel at exception bench", "Z08", ["CAM_12"], ""),
    ("Wrong bag at bagging", "Z06", ["CAM_10", "CAM_11"], ""),
    ("Left in chute", "Z06", ["CAM_10", "CAM_11"], ""),
    ("Phantom containment (scanned into bag, left beside it)", "Z06→Z10", ["CAM_10", "CAM_11", "CAM_13", "CAM_14"], ""),
    ("Mis-load onto wrong truck (RFID cross-read)", "Z10→Z12", ["CAM_13", "CAM_14", "CAM_15", "CAM_16", "CAM_17"], ""),
    ("Look-alike pair", "Z03→Z05", ["CAM_04", "CAM_05", "CAM_06"], ""),
    ("Camera outage", "Z10", ["CAM_13"], "CAM_13 rendered with a 20 min video-loss gap"),
    ("Removal into blind spot", "Z10→Z11 BLIND_NW", ["CAM_13", "CAM_19"],
     "CAM_13 films the cage, CAM_19 the store entrance (the only way in or out); nothing inside"),
    ("Return-to-sender (re-induct with new label)", "Z01→Z03", ["CAM_01", "CAM_02", "CAM_04", "CAM_05"], ""),
    ("Mixed up while opening an inbound bag", "Z02", ["CAM_02", "CAM_03"], ""),
    ("Stuck on the cover plate between carriers", "Z05", ["CAM_06", "CAM_07", "CAM_08"], ""),
    ("Two parcels on one carrier", "Z04→Z05→Z06", ["CAM_05", "CAM_06", "CAM_07", "CAM_08", "CAM_10", "CAM_11"], ""),
]
SCENARIO_SECONDS = 30  # owner decision 2026-10-28; each scenario script may use less
PER_CAM_S = {"CAM_01": 8.5, "CAM_02": 9.3, "CAM_03": 10.1, "CAM_04": 9.4, "CAM_05": 9.7, "CAM_06": 8.5, "CAM_07": 8.9,
             "CAM_08": 8.6, "CAM_09": 9.7, "CAM_10": 9.2, "CAM_11": 10.2, "CAM_12": 8.3, "CAM_13": 16.3,
             "CAM_14": 10.1, "CAM_15": 9.1, "CAM_16": 7.8, "CAM_17": 6.0, "CAM_18": 10.0}  # measured 2026-10-28, dressed hub


def render_plan(cams, checks):
    """Per scenario: cameras in play + 2–3 neighbours (3 when <= 4 in play); the control path on every camera.
    Neighbours = most handoff links to the cameras in play, then nearest; they give Spoor realistic distractors."""
    pos = {c["id"]: c["pos"] for c in cams}
    links = {c["id"]: set() for c in cams}
    for row in checks["handoff_overlap"]["detail"]:
        for a in row["side_a"]:
            for b in row["side_b"]:
                if a != b:
                    links[a].add(b)
                    links[b].add(a)
    rows, total = [], 0
    for name, zones, play, note in SCENARIOS:
        if name == "Control path":
            nb = [c["id"] for c in cams if c["id"] not in play]
        else:
            k = 3 if len(play) <= 4 else 2
            cx = sum(pos[i][0] for i in play) / len(play)
            cy = sum(pos[i][1] for i in play) / len(play)
            cand = [c["id"] for c in cams if c["id"] not in play]
            cand.sort(key=lambda i: (-len(links[i] & set(play)), math.hypot(pos[i][0] - cx, pos[i][1] - cy)))
            nb = cand[:k]
        render = sorted(play + nb)
        frames = len(render) * SCENARIO_SECONDS * FPS
        total += frames
        rows.append({"scenario": name, "cameras_in_play": play, "neighbours": nb, "render": render,
                     "camera_count": len(render), "frames": frames} | ({"note": note} if note else {}))
    return {"rule": "cameras in play + 2–3 neighbours (3 when <= 4 in play, else 2); control path on all cameras",
            "seconds_per_scenario": SCENARIO_SECONDS, "fps": FPS,
            "scenarios": rows, "total_frames": total,
            "all_cameras_every_scenario_would_be": len(SCENARIOS) * len(cams) * SCENARIO_SECONDS * FPS,
            "timing": {
                "status": "MEASURED 2026-10-28 on the DRESSED hub (no animated workers / parcels yet: re-time once "
                          "scenarios exist)",
                "machine": "laptop: Intel i7-1355U (15 W), Intel Iris Xe integrated GPU, 32 GB RAM; Blender 5.2.3 LTS",
                "seconds_per_frame": {"measured_steady_state": PER_CAM_S, "planning": 9.4,
                                      "settings": "EEVEE 2688 x 1520 (full resolution, owner rule), 8 samples, "
                                                  "spot high-bays, shadows only from pools the camera sees within "
                                                  "22 m, 5 cm shadow texels, 2 shadow steps, max shadow pool, PNG "
                                                  "write; ray tracing costs ~nothing here",
                                      "history": "timing-test slice 9.1 s; blockout 5.2 s; dressed (area lights, "
                                                 "16 spp) 11–16 s; spot lights at default 1 mm shadow texels "
                                                 "20–51 s; coarse shadows + 22 m cap 7.8–16.3 s"},
                "hours_for_total": round(9.4 * total / 3600, 1),
                "priority_batch": {"scenarios": "control path + no-read rework, phantom containment, mis-load, "
                                                "blind spot", "frames": 13500, "hours": 36.5,
                                   "owner_cap_hours": 40, "shadow_cuts_needed": False,
                                   "note": "no-shadow saves only ~0–10 % per frame now; rule kept in reserve"},
                "keep_awake": "the render script holds SetThreadExecutionState for as long as Blender runs; on AC "
                              "power this PC already never sleeps (lid must stay open)"}}


HACKATHON = {
    "theme_push_the_frontier": "a real physical system (loop sorter, reject chute, bag→cage→truck nesting, relabels) that Spoor reconstructs from video + scans, and states where it cannot know (BLIND_NW, camera outage)",
    "theme_build_for_your_world": "Klang Valley setting, Malay/English signs, chutes to Malaysian destinations, fictional brand",
    "impact": "every scenario copies a real loss point (no-read, wrong bag, wrong truck, relabel, fall-off, stuck carrier)",
    "meta_ai_tooling": "look-alikes, occlusion under the raised loop, cross-camera handoffs and the outage scenario need SAM 3.1 tracking + Muse Spark reasoning; nothing is generated by Muse Image",
    "technical_depth": "exact camera poses and parcel paths from Blender → measured tracking/timing/location error; per-camera drifting clocks test fit_clock()",
    "demo": "the plan supports a cinematic fly-through (separate camera) + multi-camera CCTV wall + 3D path replay",
    "rules": "CC0 / CC BY only (NC, Free Standard and ShareAlike dropped), fictional brand, no AI-generated models, footage labelled 'synthetic footage of a fictional hub'",
}

# ----------------------------------------------------------------------------------------------- SVG (1:200)
XMIN, XMAX, YMIN, YMAX = -20.0, 68.0, -8.0, 60.0
MM_PER_M = 5.0  # 1:200
KIND_FILL = {"dock": "#dbe9ff", "work": "#fff4d6", "machine": "#ffe1d6", "staging": "#e3f4e3", "store": "#eeeeee",
             "office": "#f1e4f7", "yard": "#e9e9e4"}


def X(x):
    return round(x - XMIN, 3)


def Y(y):
    return round(YMAX - y, 3)


def pts(poly):
    return " ".join(f"{X(x)},{Y(y)}" for x, y in poly)


def svg(cams, checks) -> str:
    w, h = XMAX - XMIN, YMAX - YMIN
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * MM_PER_M}mm" height="{h * MM_PER_M}mm" '
         f'viewBox="0 0 {w} {h}" font-family="Arial, Helvetica, sans-serif">',
         '<defs><pattern id="hatch" width="0.8" height="0.8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         '<line x1="0" y1="0" x2="0" y2="0.8" stroke="#555" stroke-width="0.12"/></pattern>'
         '<marker id="arr" markerWidth="4" markerHeight="4" refX="2" refY="2" orient="auto" markerUnits="strokeWidth">'
         '<path d="M0,0 L4,2 L0,4 z" fill="#c62828"/></marker>'
         '<marker id="arrg" markerWidth="4" markerHeight="4" refX="2" refY="2" orient="auto" markerUnits="strokeWidth">'
         '<path d="M0,0 L4,2 L0,4 z" fill="#6a1b9a"/></marker>'
         '<marker id="arro" markerWidth="4" markerHeight="4" refX="2" refY="2" orient="auto" markerUnits="strokeWidth">'
         '<path d="M0,0 L4,2 L0,4 z" fill="#e65100"/></marker>'
         '<pattern id="zebra" width="0.6" height="0.6" patternUnits="userSpaceOnUse">'
         '<rect width="0.6" height="0.6" fill="white"/><rect width="0.3" height="0.6" fill="#fbc02d"/></pattern></defs>',
         f'<rect x="0" y="0" width="{w}" height="{h}" fill="white"/>']  # fmt: skip
    for poly in (YARD_WEST, YARD_NORTH):
        o.append(f'<polygon points="{pts(poly)}" fill="{KIND_FILL["yard"]}" stroke="#aaa" stroke-width="0.08"/>')
    o.append(f'<text x="{X(-17)}" y="{Y(32.5)}" font-size="0.9" fill="#555">Z14 Truck yard (west)</text>')
    o.append(f'<text x="{X(21)}" y="{Y(56.5)}" font-size="0.9" fill="#555">Z14 Truck yard (north)</text>')
    for d in DOORS:  # lorries at a few doors
        if d["id"] in ("D02", "D05"):
            o.append(f'<rect x="{X(-12.5)}" y="{Y(d["centre"][1] + 1.25)}" width="12" height="2.5" fill="#cfd8dc" stroke="#78909c" stroke-width="0.08"/>')
        if d["id"] in ("D08", "D11"):
            o.append(f'<rect x="{X(d["centre"][0] - 1.25)}" y="{Y(52)}" width="2.5" height="12" fill="#cfd8dc" stroke="#78909c" stroke-width="0.08"/>')
    for zid, name, kind, poly, _ in ZONES:
        if poly is None:
            continue
        o.append(f'<polygon points="{pts(poly)}" fill="{KIND_FILL[kind]}" stroke="#9e9e9e" stroke-width="0.06"/>')
    o.append(f'<polygon points="{pts(BLIND["polygon"])}" fill="url(#hatch)" stroke="#424242" stroke-width="0.1" stroke-dasharray="0.4 0.3"/>')
    # circulation: forklift lane, walkways, zebras
    for x0, y0, x1, y1 in lane_rects():
        o.append(f'<rect x="{X(x0)}" y="{Y(y1)}" width="{x1 - x0}" height="{y1 - y0}" fill="#ffcc80" fill-opacity="0.45"/>')
    o.append(f'<polyline points="{pts(LANE)}" fill="none" stroke="#e65100" stroke-width="0.12" stroke-dasharray="0.8 0.6"/>')
    for wid, (x0, y0, x1, y1), _ in WALKWAYS:
        o.append(f'<rect x="{X(x0)}" y="{Y(y1)}" width="{x1 - x0}" height="{y1 - y0}" fill="#fff176" fill-opacity="0.7" stroke="#f9a825" stroke-width="0.1"/>')
    for zid, (x0, y0, x1, y1), _ in ZEBRAS:
        o.append(f'<rect x="{X(x0)}" y="{Y(y1)}" width="{x1 - x0}" height="{y1 - y0}" fill="url(#zebra)" stroke="#f9a825" stroke-width="0.06"/>')
    # cameras: cones (target PPM solid, detect PPM faint)
    for c in cams:
        fp_t = footprint(c, TARGET_PPM[c["detail"]])
        if len(fp_t) > 2:
            o.append(f'<polygon points="{pts(fp_t)}" fill="#7e57c2" fill-opacity="0.10" stroke="#5e35b1" stroke-opacity="0.6" stroke-width="0.06"/>')
    # building shell
    o.append(f'<rect x="{X(0)}" y="{Y(BD)}" width="{BW}" height="{BD}" fill="none" stroke="#212121" stroke-width="0.3"/>')
    for d in DOORS:
        cx, cy = d["centre"]
        hw = d["width"] / 2
        if d["wall"] == "W":
            o.append(f'<line x1="{X(0)}" y1="{Y(cy - hw)}" x2="{X(0)}" y2="{Y(cy + hw)}" stroke="white" stroke-width="0.4"/>')
            o.append(f'<line x1="{X(0)}" y1="{Y(cy - hw)}" x2="{X(0)}" y2="{Y(cy + hw)}" stroke="#1565c0" stroke-width="0.25" stroke-dasharray="0.3 0.2"/>')
            o.append(f'<text x="{X(-2.6)}" y="{Y(cy) + 0.3}" font-size="0.75" fill="#1565c0">{d["id"]}</text>')
        elif d["wall"] == "N":
            o.append(f'<line x1="{X(cx - hw)}" y1="{Y(BD)}" x2="{X(cx + hw)}" y2="{Y(BD)}" stroke="white" stroke-width="0.4"/>')
            o.append(f'<line x1="{X(cx - hw)}" y1="{Y(BD)}" x2="{X(cx + hw)}" y2="{Y(BD)}" stroke="#1565c0" stroke-width="0.25" stroke-dasharray="0.3 0.2"/>')
            o.append(f'<text x="{X(cx - 1.4)}" y="{Y(BD + 1.0)}" font-size="0.75" fill="#1565c0">{d["id"]}</text>')
        else:
            green = "#2e7d32"
            label = d["id"] if d["kind"] == "fire_exit" else "STAFF-1"
            if d["wall"] == "E":
                o.append(f'<line x1="{X(BW)}" y1="{Y(cy - hw)}" x2="{X(BW)}" y2="{Y(cy + hw)}" stroke="white" stroke-width="0.4"/>')
                o.append(f'<line x1="{X(BW)}" y1="{Y(cy - hw)}" x2="{X(BW)}" y2="{Y(cy + hw)}" stroke="{green}" stroke-width="0.3"/>')
                o.append(f'<rect x="{X(BW + 0.3)}" y="{Y(cy + 0.35)}" width="0.7" height="0.7" fill="{green}"/>')
                o.append(f'<text x="{X(BW + 1.2)}" y="{Y(cy) + 0.25}" font-size="0.6" fill="{green}" font-weight="bold">{label} KELUAR</text>')
            else:  # south wall
                o.append(f'<line x1="{X(cx - hw)}" y1="{Y(0)}" x2="{X(cx + hw)}" y2="{Y(0)}" stroke="white" stroke-width="0.4"/>')
                o.append(f'<line x1="{X(cx - hw)}" y1="{Y(0)}" x2="{X(cx + hw)}" y2="{Y(0)}" stroke="{green}" stroke-width="0.3"/>')
                o.append(f'<rect x="{X(cx - 0.35)}" y="{Y(-0.3)}" width="0.7" height="0.7" fill="{green}"/>')
                o.append(f'<text x="{X(cx)}" y="{Y(-1.6)}" font-size="0.6" fill="{green}" font-weight="bold" text-anchor="middle">{label} KELUAR</text>')
    for x, y in COLUMNS:
        o.append(f'<rect x="{X(x - 0.25)}" y="{Y(y + 0.25)}" width="0.5" height="0.5" fill="#212121"/>')
    # conveyors
    for cv in CONVEYORS:
        wdt = 0.8 if cv["kind"] != "telescopic" else 0.6
        col = "#607d8b" if cv["kind"] != "telescopic" else "#90a4ae"
        o.append(f'<polyline points="{pts(cv["path"])}" fill="none" stroke="{col}" stroke-width="{wdt}" stroke-linejoin="round"/>')
    L = LOOP
    path = (f'M {X(L["west_cx"])} {Y(L["south_y"])} L {X(L["east_cx"])} {Y(L["south_y"])} '
            f'A {L["radius"]} {L["radius"]} 0 0 0 {X(L["east_cx"])} {Y(L["north_y"])} '
            f'L {X(L["west_cx"])} {Y(L["north_y"])} A {L["radius"]} {L["radius"]} 0 0 0 {X(L["west_cx"])} {Y(L["south_y"])} Z')
    o.append(f'<path d="{path}" fill="none" stroke="#e65100" stroke-width="1.2"/>')
    o.append(f'<path d="{path}" fill="none" stroke="#ffcc80" stroke-width="0.25" stroke-dasharray="0.35 0.35"/>')
    o.append(f'<text x="{X(31.0)}" y="{Y(15.2)}" font-size="0.75" fill="#bf360c" text-anchor="middle">cross-belt loop, deck {DECK} m, {LOOP_LEN:.0f} m, CCW</text>')
    for c in CHUTES:
        col = "#c62828" if c["id"] == "REJECT" else "#2e7d32"
        o.append(f'<rect x="{X(c["x"] - 0.5)}" y="{Y(c["end_y"])}" width="1.0" height="{c["end_y"] - c["mouth_y"]}" fill="{col}" fill-opacity="0.55" stroke="{col}" stroke-width="0.05"/>')
        if c["bag_frame_y"]:
            o.append(f'<rect x="{X(c["x"] - 0.5)}" y="{Y(c["bag_frame_y"] + 0.8)}" width="1.0" height="0.8" fill="none" stroke="#33691e" stroke-width="0.06"/>')
        o.append(f'<text x="{X(c["x"])}" y="{Y(c["end_y"] + 0.15) - 0.2}" font-size="0.42" text-anchor="middle" fill="{col}">{c["id"].replace("REJECT", "REJ")}</text>')
    # crossovers (drawn over the loop)
    for xo in CROSSOVERS:
        x0 = xo["x"] - xo["width"] / 2
        ya, yb = xo["south_stair_y"][0], xo["north_stair_y"][1]
        o.append(f'<rect x="{X(x0)}" y="{Y(yb)}" width="{xo["width"]}" height="{yb - ya}" fill="#90a4ae" stroke="#37474f" stroke-width="0.08"/>')
        for (s0, s1) in (xo["south_stair_y"], xo["north_stair_y"]):
            for k in range(int((s1 - s0) / 0.3)):
                yy = s0 + 0.3 * (k + 0.5)
                o.append(f'<line x1="{X(x0)}" y1="{Y(yy)}" x2="{X(x0 + xo["width"])}" y2="{Y(yy)}" stroke="#37474f" stroke-width="0.04"/>')
        o.append(f'<text x="{X(xo["x"] + 0.9)}" y="{Y((xo["bridge_y"][0] + xo["bridge_y"][1]) / 2)}" font-size="0.55" font-weight="bold" fill="#263238">{xo["id"]}</text>')
    # tunnel box + benches
    o.append(f'<rect x="{X(19.5)}" y="{Y(10.4)}" width="2.5" height="1.8" fill="#ffab91" stroke="#bf360c" stroke-width="0.08"/>')
    o.append(f'<text x="{X(20.75)}" y="{Y(10.6) - 0.1}" font-size="0.5" text-anchor="middle" fill="#bf360c">DWS</text>')
    for _, (x0, y0, x1, y1) in BENCHES:
        o.append(f'<rect x="{X(x0)}" y="{Y(y1)}" width="{x1 - x0}" height="{y1 - y0}" fill="#d7ccc8" stroke="#6d4c41" stroke-width="0.05"/>')
    for bx, by in CAGE_BAYS:
        o.append(f'<rect x="{X(bx)}" y="{Y(by + CAGE_BAY)}" width="{CAGE_BAY}" height="{CAGE_BAY}" fill="none" stroke="#f9a825" stroke-width="0.07"/>')
    for x0, y0, x1, y1 in RACKS:
        o.append(f'<rect x="{X(x0)}" y="{Y(y1)}" width="{x1 - x0}" height="{y1 - y0}" fill="#9e9e9e" stroke="#616161" stroke-width="0.05"/>')
    o.append(f'<text x="{X(7)}" y="{Y(32.5)}" font-size="0.45" fill="#424242" text-anchor="middle">3 m sack racks (folded sacks, nested empty cages)</text>')
    # zone labels
    for zid, name, kind, poly, _ in ZONES:
        if poly is None:
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        if zid == "Z05":
            cy = 8.0
        if zid == "Z06":
            cy = 24.0
        if zid == "Z07":
            cx, cy = 29.3, 23.0
        if zid == "Z08":
            cy = 21.4
        o.append(f'<text x="{X(cx)}" y="{Y(cy)}" font-size="0.9" font-weight="bold" text-anchor="middle" fill="#263238">{zid}</text>')
        short = name.split(" (")[0]
        fs = 0.5 if (max(xs) - min(xs)) < 7 else 0.6
        o.append(f'<text x="{X(cx)}" y="{Y(cy) + 0.75}" font-size="{fs}" text-anchor="middle" fill="#37474f">{short}</text>')
    o.append(f'<text x="{X(10.3)}" y="{Y(37.6)}" font-size="0.65" text-anchor="middle" fill="#212121" font-weight="bold">BLIND_NW</text>')
    o.append(f'<text x="{X(10.3)}" y="{Y(37.6) + 0.7}" font-size="0.45" text-anchor="middle" fill="#212121">deliberate blind corner</text>')
    # flow arrows (main flow red, exception purple)
    main = [[2.5, 22.0], [4.6, 22.0], [4.6, 12.0], [9.0, 12.0], [26.0, 12.6], [44.0, 12.6], [52.5, 15.0], [46.0, 17.5],
            [44.5, 22.8], [44.5, 27.5], [44.5, 33.0], [45.0, 41.5]]
    o.append(f'<polyline points="{pts(main)}" fill="none" stroke="#c62828" stroke-width="0.3" stroke-opacity="0.85" stroke-dasharray="1.2 0.5" marker-end="url(#arr)"/>')
    exc = [[31.0, 17.6], [29.6, 20.6], [26.5, 22.2], [21.5, 16.5], [16.0, 11.0]]
    o.append(f'<polyline points="{pts(exc)}" fill="none" stroke="#6a1b9a" stroke-width="0.22" stroke-dasharray="0.6 0.4" marker-end="url(#arrg)"/>')
    o.append(f'<text x="{X(19.5)}" y="{Y(16.8)}" font-size="0.5" fill="#6a1b9a">rework → re-induct</text>')
    ovs = [[11.0, 3.5]] + LANE[1:] + [[33.0, 34.9], [33.0, 38.0]]
    o.append(f'<polyline points="{pts(ovs)}" fill="none" stroke="#e65100" stroke-width="0.28" stroke-dasharray="1.0 0.5" marker-end="url(#arro)"/>')
    o.append(f'<text x="{X(30)}" y="{Y(3.1)}" font-size="0.55" fill="#bf360c">forklift lane 3 m — oversize route Z09 → outbound</text>')
    # scan points
    for sid, kind, zone, xyz, dom, ev in SCAN_POINTS:
        fill = "#ff9800" if kind != "handheld" else "#ffe082"
        o.append(f'<circle cx="{X(xyz[0])}" cy="{Y(xyz[1])}" r="0.28" fill="{fill}" stroke="#e65100" stroke-width="0.06"/>')
    # cameras on top
    for c in cams:
        x, y, hgt = c["pos"]
        dx, dy = math.cos(math.radians(c["yaw"])), math.sin(math.radians(c["yaw"]))
        o.append(f'<line x1="{X(x)}" y1="{Y(y)}" x2="{X(x + 1.6 * dx)}" y2="{Y(y + 1.6 * dy)}" stroke="#4527a0" stroke-width="0.14" marker-end="url(#arrg)"/>')
        o.append(f'<circle cx="{X(x)}" cy="{Y(y)}" r="0.42" fill="#5e35b1" stroke="white" stroke-width="0.1"/>')
        o.append(f'<text x="{X(x)}" y="{Y(y) - 0.65}" font-size="0.55" text-anchor="middle" font-weight="bold" fill="#311b92">{c["id"].replace("CAM_", "C")}</text>')
    # scale bar, north arrow, title block, legend
    o.append(f'<rect x="{X(-18)}" y="{Y(-2.5)}" width="10" height="0.35" fill="#212121"/>')
    o.append(f'<rect x="{X(-18)}" y="{Y(-2.5)}" width="5" height="0.35" fill="white" stroke="#212121" stroke-width="0.05"/>')
    o.append(f'<text x="{X(-18)}" y="{Y(-3.6)}" font-size="0.6">0      5      10 m   (scale 1:200 when printed at 100 %)</text>')
    o.append(f'<path d="M {X(-9)} {Y(46)} L {X(-8)} {Y(43)} L {X(-9)} {Y(43.8)} L {X(-10)} {Y(43)} Z" fill="#212121"/>')
    o.append(f'<text x="{X(-9)}" y="{Y(46.5)}" font-size="0.9" text-anchor="middle" font-weight="bold">N</text>')
    tb = [("CONTOH EXPRESS DEMO HUB — 2D PLAN v2 (owner changes applied)", 1.0, True),
          ("Fictional hub, Klang Valley. L-flow: inbound west wall → outbound north wall.", 0.6, False),
          (f"Building {BW:.0f} x {BD:.0f} m, eaves {EAVES} m. Cross-belt loop on one raised level ({DECK} m) + reject chute.", 0.6, False),
          (f"{len(cams)} cameras ({IMG_W}x{IMG_H}, {HFOV}° HFOV, {FPS} fps). Cone = floor area at the camera's target", 0.6, False),
          ("detail (62 PPM observe / 125 recognise); 25 PPM detect reach is in hub_spec.yaml. Cones ignore occlusion; the checks don't.", 0.6, False),
          ("Red dashed = main parcel flow. Purple dashed = no-read / rework flow. Orange dot = fixed scanner,", 0.6, False),
          ("yellow dot = handheld scan point. Hatched = BLIND_NW (deliberate, recorded in hub_spec.yaml).", 0.6, False),
          ("Yellow = walkway; orange band + orange dashed = forklift lane / oversize route; striped = zebra;", 0.6, False),
          ("grey bridge = crossover (XO); green = fire exit / staff door with lit KELUAR sign.", 0.6, False),
          ("Labels: synthetic footage of a fictional hub. Generated by assets/hub/build_hub_plan.py.", 0.6, False)]
    ty = 56.8
    for text, fs, bold in tb:
        o.append(f'<text x="{X(-18.5)}" y="{Y(ty)}" font-size="{fs}" {"font-weight=\"bold\"" if bold else ""}>{text}</text>')
        ty -= 1.15 if bold else 0.85
    items = [f"{k.replace('_', ' ')}: {'PASS' if v['pass'] else 'FAIL'}" for k, v in checks.items()]
    for i in range(0, len(items), 6):
        o.append(f'<text x="{X(-18.5)}" y="{Y(-4.6 - 0.8 * (i // 6))}" font-size="0.55" fill="#1b5e20">'
                 f'{"Checks — " if i == 0 else ""}{" · ".join(items[i:i + 6])}</text>')
    o.append("</svg>")
    return "\n".join(o)


# ----------------------------------------------------------------------------------------------- main


def main():
    cams, specs = [], {}
    for spec in CAMERA_SPECS:
        pose = place_camera(spec)
        cams.append(pose | {"id": spec[0], "zone": spec[1], "detail": spec[5], "mount": spec[6], "question": spec[7]})
        specs[spec[0]] = spec
    checks, sp_rows = run_checks(cams)
    zones_cov = zone_coverage(cams)
    cam_rows = []
    for c in cams:
        cov, fe = duty_report(c, specs[c["id"]])
        x0, y0, x1, y1, dz = specs[c["id"]][2]
        cam_rows.append({
            "id": c["id"], "zone": c["zone"], "question": c["question"], "detail_target": c["detail"],
            "target_ppm": TARGET_PPM[c["detail"]], "position_m": c["pos"][:2], "height_m": c["pos"][2],
            "heading_deg": c["yaw"], "tilt_down_deg": c["tilt"], "hfov_deg": HFOV, "vfov_deg": VFOV,
            "resolution": [IMG_W, IMG_H], "fps": FPS, "mount": c["mount"],
            "duty_area_m": {"x": [x0, x1], "y": [y0, y1], "parcel_height_m": dz},
            "duty_covered_at_target": round(cov, 2),
            "far_edge": {"point_m": [round(v, 1) for v in fe[0][:2]], "ppm": round(fe[1])} if fe else None,
            "meets_target": cov >= 0.9,
            "view_fractions": view_fractions(c | {"id": c["id"]}),
            "view_constraint": (CAMERA_VIEW.get(c["id"]) or None),
            "view_constraint_met": not c.get("view_unmet", False),
            "clock_domain": f"clkd_{c['id'].lower()}",
            "osd_label": OSD_LABELS[c["id"]],
            "realism": CAMERA_REALISM | SPECIAL_REALISM.get(c["id"], {}),
        })  # fmt: skip
    spec = {
        "meta": {"name": "Spoor demo parcel hub (fictional), Klang Valley", "status": "2D plan v2 — owner approved with changes 2026-10-28; changes applied, no Blender yet",
                 "frame": "metres; X east, Y north, Z up; origin SW outside corner", "scale_of_svg": "1:200",
                 "look": "PosLaju IPC look (single cross-belt loop, steel cladding) at Skynet Hounslow size (compact, "
                         "chutes on one side) — DEFAULT: the owner's look choice was left blank",
                 "brand": "CONTOH Express (fictional; 'contoh' = 'sample' in Malay) — owner-approved 2026-10-28",
                 "footage_label": "synthetic footage of a fictional hub",
                 "generator": "assets/hub/build_hub_plan.py"},
        "building": {"footprint_m": [BW, BD], "eaves_m": EAVES, "structure": "steel portal frame",
                     "flow": "L-flow: inbound west wall, outbound north wall", "columns": COLUMNS, "doors": DOORS},
        "zones": [{"id": z, "name": n, "kind": k, "polygon_m": p if p else {"west": YARD_WEST, "north": YARD_NORTH},
                   "size_m": [round(p[2][0] - p[0][0], 1), round(p[2][1] - p[0][1], 1)] if p else None,
                   "realism": r} for z, n, k, p, r in ZONES],
        "blind_corner": BLIND,
        "line_a": {"layout": LINE_A_LAYOUT},
        "machines": {"loop": LOOP | {"length_m": round(LOOP_LEN, 1), "carriers": round(LOOP_LEN / 0.7)},
                     "conveyors": CONVEYORS, "chutes": CHUTES,
                     "chute_layout_note": "Chutes on ONE side of the loop (north straight) is a deliberate "
                                          "simplification. Real cross-belt loops usually have chutes on both sides, "
                                          "often on two levels. One side keeps the plan readable, puts every chute in "
                                          "one camera row (2 cameras instead of ~4) and keeps one bagging aisle. "
                                          "Spoor's logic does not depend on it.",
                     "scan_tunnel": {"zone": "Z04", "box_m": [2.5, 1.8, 1.6], "exit_read_point_m": [22.2, 9.5],
                                     "weigh_section": {
                                         "x_m": [17.5, 19.0], "is_scan_point": False,
                                         "why": "an in-motion scale reads no barcode and emits no event of its own; "
                                                "the DWS controller tracks the parcel by photo-eye and merges weight "
                                                "+ dims into the single tunnel event at SP-TUNNEL (ScanEvent.weight_g "
                                                "/ dims_mm)",
                                         "still_filmed": "yes — see checks.weigh_section_filmed; the photo-eye "
                                                         "merge can pin the wrong weight on parcels running too "
                                                         "close together, and video is how you prove that"}},
                     "roll_cage_m": [0.72, 0.80, 1.80], "max_parcel_m": [1.0, 0.7, 0.7], "max_parcel_kg": 30},
        "circulation": {
            "crossovers": CROSSOVERS,
            "walkways": [{"id": w, "rect_m": list(r), "purpose": t} for w, r, t in WALKWAYS],
            "forklift_lane": {"centreline_m": LANE, "width_m": LANE_W, "route": "Z09 -> south aisle -> east aisle -> Z12"},
            "zebra_crossings": [{"id": z, "rect_m": list(r), "purpose": t} for z, r, t in ZEBRAS],
            "fire_exits": [d for d in DOORS if d["kind"] == "fire_exit"],
            "realism": CIRCULATION_REALISM},
        "flows": {
            "main": "Z01 telescopic -> collector -> Z03 induction -> Z04 tunnel -> Z05 loop -> Z06 chute -> bag -> "
                    "Z10 cage -> Z12 truck",
            "rework": "Z05 no-read -> Z07 reject chute -> Z08 bench (manual encode / relabel) -> walk back -> Z03",
            "oversize": "Z01 -> Z09 (manual scan SP-OVERSIZE, onto a pallet) -> forklift lane -> Z12 door -> truck "
                        "(never on the belts)",
            "bag_opening": "Z01 bag -> Z02 bench (SP-BAGOPEN) -> parcels onto the collector belt -> Z03"},
        "fixtures": {
            "benches": [{"name": n, "rect_m": list(r), "height_m": 0.9} for n, r in BENCHES],
            "cage_bays": [{"id": f"S{i + 1:02d}", "sw_corner_m": [bx, by], "size_m": CAGE_BAY}
                          for i, (bx, by) in enumerate(CAGE_BAYS)],
            "racks": [{"rect_m": list(r), "height_m": RACK_H} for r in RACKS],
            "store_shelves_m": [list(p) for p in STORE_SHELVES],
            "office": {"zone": "Z13", "wall_height_m": 3.0, "glass_wall": "north", "door": "west wall, onto W1"}},
        "sort_plans": SORT_PLANS,
        "clock_domains": [{"id": "clkd_wcs", "kind": "wcs_plc", "devices": "induct photo-eye, tunnel, diverts, RFID portals"},
                          {"id": "clkd_handheld", "kind": "handheld_fleet", "devices": "all handheld scanners (batch sync)"}] +
                         [{"id": f"clkd_{c['id'].lower()}", "kind": "camera", "devices": c["id"]} for c in cams],
        "scan_points": [{"id": s, "device_kind": k, "zone": z, "position_m": list(p), "clock_domain": d, "events": e,
                         "visible_by": next(r["visible_by"] for r in sp_rows if r["id"] == s)}
                        for s, k, z, p, d, e in SCAN_POINTS],
        "cameras": cam_rows,
        "assets": [{"zone": z, "item": i, "source": n, "url": u, "licence": lic, "status": st, "credit": a}
                   for z, i, n, u, lic, st, a in ASSETS],
        "assets_excluded": [{"name": n, "url": u, "licence_found": lic, "reason": r} for n, u, lic, r in EXCLUDED],
        "assets_other_terms": [{"name": n, "url": u, "terms": t, "use": us} for n, u, t, us in OTHER_TERMS],
        "assumptions": [{"id": i, "item": it, "value": v, "why": w} for i, it, v, w in ASSUMPTIONS],
        "checks": checks,
        "zone_coverage_fraction": zones_cov,
        "known_gaps": known_gaps(checks),
        "scenario_support": [{"scenario": n, "zones": z, "evidence_cameras": c} | ({"note": t} if t else {})
                             for n, z, c, t in SCENARIOS],
        "hackathon_mapping": HACKATHON,
        "render_plan": render_plan(cams, checks),
    }  # fmt: skip
    # JSON copy for Blender's bundled Python (no PyYAML there); same content as the YAML
    (HERE / "hub_spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    yaml.safe_dump(spec, (HERE / "hub_spec.yaml").open("w", encoding="utf-8"), sort_keys=False, allow_unicode=True,
                   width=118)  # fmt: skip
    truth = {"WARNING": "EVALUATOR-ONLY ground truth for rendering. Spoor runtime must never read this file (PRD §8.1).",
             "cameras": {cid: {"clock_offset_s": off, "clock_drift_ppm": ppm, "lens_k1": -0.08,
                               "mount_roll_deg": 1.5 if cid == "CAM_08" else 0.0}
                         for cid, (off, ppm) in RENDER_TRUTH_CLOCKS.items()},
             "handheld_fleet": {"clock_offset_s": -2.0, "batch_upload_delay_min": 40},
             "wcs": {"clock_offset_s": 0.0, "note": "reference timeline"}}  # fmt: skip
    yaml.safe_dump(truth, (HERE / "render_truth.yaml").open("w", encoding="utf-8"), sort_keys=False)
    (HERE / "render_truth.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")  # Blender has no PyYAML
    (HERE / "hub_plan.svg").write_text(svg(cams, checks), encoding="utf-8")
    credits = ["# Credits — third-party assets for the Spoor demo hub", "",
               "Licences checked 2026-10-28 (Sketchfab via its public API; Poly Haven and ambientCG via their APIs; "
               "Quaternius via its site). Only CC0 and CC BY are used. CC BY items require the credit line below.", "",
               "## Used", "", "| Asset | Author | Licence | URL | Use |", "|---|---|---|---|---|"]
    seen = set()
    used = [r for r in ASSETS if not r[5].startswith("not used")]
    for z, i, n, u, lic, st, a in used:
        if u and u not in seen:
            seen.add(u)
            credits.append(f"| {n} | {a} | {lic} | {u} | {i} ({z}) |")
    credits += ["", "CC BY credit line (README / video end card): models by " +
                ", ".join(sorted({a for _, _, _, u, lic, _, a in used if lic == BY and u.startswith(SF)})) +
                " on Sketchfab, licensed CC BY 4.0. Motion data: AndyData-lab-onePerson (Maurice et al. 2019) and "
                "100STYLE (Mason, Starke, Komura 2022), CC BY 4.0, retargeted.",
                "", "## Licence notices", "",
                "**Microsoft Rocketbox** (avatars and animations) — MIT License, Copyright (c) 2020 Microsoft. "
                "Permission is hereby granted, free of charge, to any person obtaining a copy of this software and "
                "associated documentation files (the \"Software\"), to deal in the Software without restriction, "
                "including without limitation the rights to use, copy, modify, merge, publish, distribute, "
                "sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is "
                "furnished to do so, subject to the following conditions: The above copyright notice and this "
                "permission notice shall be included in all copies or substantial portions of the Software. THE "
                "SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT "
                "LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. "
                "IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
                "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN "
                "CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.", "",
                "**Construction Worker in Safety Vest** by Nitoktris (https://sketchfab.com/mr.sinankaba), CC BY 4.0, "
                "https://sketchfab.com/3d-models/construction-worker-in-safety-vest-0ee4e54dc78b45f9bb7e26fb0d000f7e "
                "— mesh decimated and auto-rigged (Mixamo) for rendering.", "",
                "**Barlow Condensed** — SIL Open Font License 1.1, Copyright 2017 The Barlow Project Authors "
                "(https://github.com/jpt/barlow).",
                "", "## Built by us (not third-party)", ""] + \
               [f"- {i} ({z}): {n}" for z, i, n, u, lic, st, a in ASSETS if st == "build"] + \
               ["", "## Used under other terms (not redistributed)", "", "| Asset | Terms | Use |", "|---|---|---|"] + \
               [f"| [{n}]({u}) | {t} | {us} |" for n, u, t, us in OTHER_TERMS] + \
               ["", "## Checked and excluded", "", "| Asset | Licence found | Reason |", "|---|---|---|"] + \
               [f"| [{n}]({u}) | {lic} | {r} |" for n, u, lic, r in EXCLUDED] + \
               ["", "Specs copied from real products (e.g. the camera's resolution and field of view) carry no brand "
                "onto any model, sign or vehicle. All brands in the scene are fictional."]  # fmt: skip
    (HERE / "CREDITS.md").write_text("\n".join(credits) + "\n", encoding="utf-8")
    # console summary
    print("checks:")
    for k, v in checks.items():
        extra = {kk: vv for kk, vv in v.items() if kk not in ("detail",)}
        print(f"  {k}: {extra}")
    print("zone coverage:", zones_cov)
    print("cameras (duty coverage at target, far-edge PPM):")
    for r in cam_rows:
        fe = r["far_edge"]
        print(f"  {r['id']} {r['zone']} @{r['position_m']} h={r['height_m']} yaw={r['heading_deg']} tilt={r['tilt_down_deg']}"
              f" target {r['target_ppm']}: covered {r['duty_covered_at_target']:.0%}, far edge {fe['ppm'] if fe else '-'}"
              f" {'OK' if r['meets_target'] else 'BELOW'}")
    for r in sp_rows:
        if not r["visible_by"]:
            print("  UNSEEN scan point:", r["id"])
    rp = spec["render_plan"]
    print("render plan:", [(r["scenario"][:22], r["camera_count"]) for r in rp["scenarios"]], "total frames",
          rp["total_frames"], "vs all-cameras", rp["all_cameras_every_scenario_would_be"])


if __name__ == "__main__":
    main()
