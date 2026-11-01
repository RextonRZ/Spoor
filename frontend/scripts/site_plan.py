"""Site plan payload (QUEUE I9) from the fictional hub's design plan, assets/hub/hub_spec.json.

This is what a real hub would hand over on day one: its floor plan, conveyor layout with deck heights and belt
speeds (machine spec), scan points, doors, racks and camera mounting plan. Nothing here is footage or truth.

Belt speeds are not in hub_spec.json; they are the conveyor design speeds the hub's flow model runs at
(assets/hub/flow.py `Belt(...)` definitions: telescopic booms 0.8, collector 1.2, induction 1.5, tunnel 1.5,
merge 1.8 m/s; sorter loop 2.0 m/s from hub_spec machines.loop.speed_mps). Chutes are gravity: no stated speed."""

import math

BELT_SPEEDS_MPS = {"telescopic": 0.8, "collector": 1.2, "induction": 1.5, "tunnel_line": 1.5, "merge": 1.8,
                   "induction_B": 1.5}  # fmt: skip
FEEDS = {"induction": ["tunnel_line"], "tunnel_line": ["merge"], "merge": ["loop"], "induction_B": ["loop"]}
SOURCE = ("Design plan of the fictional CONTOH hub (assets/hub/hub_spec.json: building, zones, conveyors, chutes, "
          "scan points, doors, racks, camera mounting plan) + conveyor design speeds (assets/hub/flow.py). "
          "Not surveyed.")  # fmt: skip


def rect(r: list[float]) -> list[list[float]]:
    x0, y0, x1, y1 = r
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def loop_path(loop: dict, step_deg: float = 10.0) -> list[list[float]]:
    """Closed centreline in travel direction: south straight eastbound, east arc, north straight westbound, west arc
    (counter-clockwise from above, hub_spec machines.loop.direction)."""
    r, cy, w, e = loop["radius"], loop["cy"], loop["west_cx"], loop["east_cx"]
    pts = [[w, loop["south_y"]], [e, loop["south_y"]]]
    n = int(180 / step_deg)
    pts += [[round(e + r * math.cos(math.radians(-90 + step_deg * k)), 3),
             round(cy + r * math.sin(math.radians(-90 + step_deg * k)), 3)] for k in range(1, n)]
    pts += [[e, loop["north_y"]], [w, loop["north_y"]]]
    pts += [[round(w + r * math.cos(math.radians(90 + step_deg * k)), 3),
             round(cy + r * math.sin(math.radians(90 + step_deg * k)), 3)] for k in range(1, n)]
    return pts  # fmt: skip


def site_plan(spec: dict, zone_polys) -> dict:
    b, m = spec["building"], spec["machines"]
    loop = m["loop"]
    W, H = b["footprint_m"]
    areas = []
    for z in spec["zones"]:
        for zid, poly in zone_polys(z):
            kind = {"store": "store", "machine": "machine"}.get(z["kind"], "zone")  # machines: searched last, line stopped
            areas.append({"area_id": zid.removeprefix("zone_"), "kind": kind, "name": f"{z['id']} {z['name']}",
                          "polygon_m": poly, "zone_id": zid, "walkable": z["kind"] != "yard"})  # fmt: skip
    walk = spec["circulation"]["walkways"] + spec["circulation"].get("zebra_crossings", [])
    areas += [{"area_id": w["id"], "kind": "walkway", "name": w.get("purpose", w["id"])[:120],
               "polygon_m": rect(w["rect_m"]), "walkable": True} for w in walk]  # fmt: skip
    for xo in spec["circulation"]["crossovers"]:  # stair + bridge footprint: a person can cross the belts here
        y0, y1 = xo["south_stair_y"][0], xo["north_stair_y"][1]
        areas.append({"area_id": xo["id"], "kind": "walkway", "name": f"crossover {xo['id']}: {xo['crosses']}"[:120],
                      "polygon_m": rect([xo["x"] - xo["width"] / 2, y0, xo["x"] + xo["width"] / 2, y1]),
                      "height_m": xo["deck_m"], "walkable": True})  # fmt: skip
    f = spec["fixtures"]
    areas += [{"area_id": f"rack_{i + 1}", "kind": "rack", "name": f"rack {i + 1}", "polygon_m": rect(r["rect_m"]),
               "height_m": r["height_m"], "walkable": False} for i, r in enumerate(f["racks"])]  # fmt: skip
    areas += [{"area_id": f"bench_{i + 1}", "kind": "bench", "name": x["name"], "polygon_m": rect(x["rect_m"]),
               "height_m": x["height_m"], "walkable": False} for i, x in enumerate(f["benches"])]  # fmt: skip
    areas += [{"area_id": c["id"], "kind": "cage_bay", "name": f"cage bay {c['id']}",
               "polygon_m": rect([*c["sw_corner_m"], c["sw_corner_m"][0] + c["size_m"], c["sw_corner_m"][1] + c["size_m"]]),
               "walkable": True} for c in f["cage_bays"]]  # fmt: skip
    bc = spec["blind_corner"]
    areas.append({"area_id": bc["id"], "kind": "blind_spot", "name": bc.get("label") or bc["why"][:120],
                  "note": bc["why"], "polygon_m": bc["polygon"],
                  "zone_id": f"zone_{bc['zone']}", "walkable": True})  # fmt: skip

    conveyors = []
    for c in m["conveyors"]:
        kind = "telescopic" if c["kind"] == "telescopic" else "belt"
        speed = BELT_SPEEDS_MPS.get("telescopic" if kind == "telescopic" else c["id"])
        feeds = ["collector"] if kind == "telescopic" else FEEDS.get(c["id"], [])
        conveyors.append({"conveyor_id": c["id"], "kind": kind, "path_m": c["path"],
                          "deck_heights_m": c.get("heights", [c["height"]]), "speed_mps": speed, "feeds": feeds})
    chutes = [ch["id"] for ch in m["chutes"]]
    conveyors.append({"conveyor_id": "loop", "kind": "loop", "path_m": loop_path(loop), "closed": True,
                      "deck_heights_m": [loop["deck_height"]], "speed_mps": loop["speed_mps"],
                      "feeds": [f"chute_{c}" for c in chutes]})  # fmt: skip
    conveyors += [{"conveyor_id": f"chute_{ch['id']}", "kind": "chute",
                   "path_m": [[ch["x"], ch["mouth_y"]], [ch["x"], ch["end_y"]]],
                   "deck_heights_m": [loop["deck_height"], ch["lip_z"]], "speed_mps": None} for ch in m["chutes"]]

    def merge_end(cid: str) -> list[float]:
        return next(c["path"][-1] for c in m["conveyors"] if c["id"] == cid)

    read_points = []
    for sp in spec["scan_points"]:
        ev: dict[str, list[float]] = {}
        sid = sp["id"]
        if sid == "SP-INDUCT":  # the PLC's carrier assignment happens where line A's merge joins the loop
            ev["inducted"] = merge_end("merge")
        elif sid == "SP-INDUCT-B":
            ev["inducted"] = merge_end("induction_B")
        elif sid.startswith("SP-DIV-"):  # divert = the sorter tips the carrier at the chute, on the loop
            x = sp["position_m"][0]
            ev["divert_confirmed"] = ev["recirculated"] = [x, loop["north_y"]]
        read_points.append({"scan_point_id": sid, "device_kind": sp["device_kind"], "position_m": sp["position_m"],
                            "zone_id": f"zone_{sp['zone']}", "event_positions": ev,
                            "visible_by": [f"cam_{v['camera']}" for v in sp.get("visible_by", [])],
                            "device_parts_m": sp.get("device_parts_m", []),
                            "work_area_m": sp.get("work_area_m", []), "work_height_m": sp.get("work_height_m")})  # fmt: skip

    doors = [{"door_id": d["id"], "kind": d["kind"], "centre_m": d["centre"], "width_m": d["width"],
              "wall": d["wall"], "exit": True} for d in b["doors"]]  # fmt: skip
    cams = [{"camera_id": f"cam_{c['id']}", "position_m": [*c["position_m"], c["height_m"]],
             "heading_deg": c["heading_deg"], "tilt_down_deg": c["tilt_down_deg"], "hfov_deg": c["hfov_deg"],
             "vfov_deg": c["vfov_deg"], "resolution_wh_px": c["resolution"], "label": c.get("osd_label")}
            for c in spec["cameras"]]  # fmt: skip
    return {"source": SOURCE, "outline_m": [[0, 0], [W, 0], [W, H], [0, H]],
            "eaves_m": b.get("eaves_m"), "areas": areas, "conveyors": conveyors, "doors": doors,
            "read_points": read_points, "cameras": cams}  # fmt: skip
