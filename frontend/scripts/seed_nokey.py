"""Load REAL inputs into a no-key Spoor backend through its HTTP API (QUEUE C5).

    uv run --project ../backend python scripts/seed_nokey.py [--clips ../assets/hub/build/qa/cctv] [--case-parcel ID]

Inputs, all of them things a real site would hand over:
- the site plan, zones and camera mounting plan from assets/hub/hub_spec.json;
- synthetic CCTV clips (rendered footage of the fictional hub) as media, each carrying a burned-in SYNTHETIC mark;
- the hub's simulated scan log (assets/hub/build/sim/events_scan_simulated.jsonl) through the scan import route,
  labelled `simulated` end to end.

Never read here (and never by the frontend or backend runtime): render_truth.*, flow_truth.json, build/truth/*.
No tracks, detections, calibrations, clock fits or answers are created: those need a model or a human.
Camera clocks get an explicit UNVERIFIED sync (declared start time, wide uncertainty) because the upload route
needs one to place a clip on the timeline; the UI shows it as a clock warning.
"""

import argparse
import json
import math
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
FRONT = HERE.parent
REPO = FRONT.parent
FORBIDDEN = ("render_truth", "flow_truth", "/truth/", "\\truth\\", "scenario_card")

SITE_ID = "site_contoh_hub"
FLOOR_ID = "floor_ground"
# Default recording start for the QA clips: the OSD start time the renders were made with. Declared, not verified.
DEFAULT_CLIP_START = "2026-10-28T14:32:07+08:00"


def guard(path: Path) -> Path:
    s = str(path).replace("\\", "/")
    if any(f.replace("\\", "/") in s for f in FORBIDDEN):
        sys.exit(f"refusing to read evaluator-only file: {path}")
    return path


def load_env() -> dict:
    env = {}
    for line in (FRONT / ".env.local").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def zone_polys(z: dict) -> list[tuple[str, list]]:
    poly = z["polygon_m"]
    if isinstance(poly, dict):  # Z14 yard has named parts
        return [(f"zone_{z['id']}" + ("" if i == 0 else f"_{name}"), p) for i, (name, p) in enumerate(poly.items())]
    return [(f"zone_{z['id']}", poly)]


def floor_footprint(cam: dict, max_range_m: float = 45.0, steps: int = 6) -> list[list[float]]:
    """Approximate floor footprint of a camera's view from its MOUNTING PLAN pose (no occlusion, no lens model)."""
    x, y = cam["position_m"]
    h = cam["height_m"]
    yaw, tilt = math.radians(cam["heading_deg"]), math.radians(cam["tilt_down_deg"])
    th, tv = math.tan(math.radians(cam["hfov_deg"]) / 2), math.tan(math.radians(cam["vfov_deg"]) / 2)
    fwd = (math.cos(yaw) * math.cos(tilt), math.sin(yaw) * math.cos(tilt), -math.sin(tilt))
    right = (math.sin(yaw), -math.cos(yaw), 0.0)
    up = (right[1] * fwd[2] - right[2] * fwd[1], right[2] * fwd[0] - right[0] * fwd[2],
          right[0] * fwd[1] - right[1] * fwd[0])  # fmt: skip
    border = []
    for i in range(steps):
        border.append((-1 + 2 * i / steps, -1))
    for i in range(steps):
        border.append((1, -1 + 2 * i / steps))
    for i in range(steps):
        border.append((1 - 2 * i / steps, 1))
    for i in range(steps):
        border.append((-1, 1 - 2 * i / steps))
    pts = []
    for u, v in border:
        d = [fwd[k] + u * th * right[k] + v * tv * up[k] for k in range(3)]
        n = math.hypot(*d)
        d = [c / n for c in d]
        if d[2] < -1e-6:
            t = h / -d[2]
            horiz = math.hypot(d[0], d[1]) * t
            if horiz > max_range_m:
                t *= max_range_m / horiz
        else:
            t = max_range_m / max(math.hypot(d[0], d[1]), 1e-6)
        pts.append([round(x + d[0] * t, 2), round(y + d[1] * t, 2)])
    return pts


def mark_synthetic(src: Path, out_dir: Path) -> Path:
    """Copy a clip with a burned-in SYNTHETIC mark if it has none (QA renders are unmarked; final CCTV renders from
    cctv_look.py already carry 'SYNTHETIC - fictional hub')."""
    out = out_dir / src.name
    font = "C\\:/Windows/Fonts/arial.ttf" if sys.platform == "win32" else "DejaVuSans"
    draw = (f"drawtext=fontfile='{font}':text='SYNTHETIC - fictional hub':x=w-tw-14:y=h-th-12:fontsize=h/30:"
            "fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=6")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", draw, "-c:v", "libx264", "-crf", "20",
                    "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an", str(out)], check=True)  # fmt: skip
    return out


def photo_eye_csv(lines: list[str]) -> tuple[str, int]:
    """bag_drop pulses (no parcel ID, no bag ID) -> simulated photo-eye SensorEvents: corroboration, never identity
    (review 004, answer to 002 Q2)."""
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=chr(10))
    w.writerow(["device_id", "kind", "value", "zone_id", "device_time_utc", "clock_quality", "source"])
    n = 0
    for line in lines:
        if not line.strip():
            continue
        r = json.loads(line)
        if r["event"] != "bag_drop" or r.get("parcel_id"):
            continue
        zone = "zone_Z07" if r["chute"] == "REJECT" else "zone_Z06"
        w.writerow([f"chute:{r['chute']}:photo-eye", "motion_trigger", "true", zone, r["time"],
                    "sorter WCS clock, not fitted", "simulated"])
        n += 1
    return buf.getvalue(), n


def handheld_point(points: dict, r: dict, prefix: str) -> dict | None:
    """The read point of a handheld record: its own scan_point, else the chute's point for bag scans."""
    if r.get("scan_point") in points:
        return points[r["scan_point"]]
    if r.get("chute") and f"{prefix}{r['chute']}" in points:
        return points[f"{prefix}{r['chute']}"]
    return None


def convert_scans(lines: list[str], domain_ids: dict[str, str], spec: dict) -> tuple[list[dict], dict]:
    """Translate the hub's simulated log into Spoor ScanEvent rows. Field meanings only; no values invented."""
    points = {p["id"]: p for p in spec["scan_points"]}
    out, skipped = [], {}
    for line in lines:
        if not line.strip():
            continue
        r = json.loads(line)
        ev, pid = r["event"], r.get("parcel_id")
        ids = [{"scheme": "carrier_waybill", "value": pid}] if pid else []
        # `time` is the DEVICE clock of the record's own clock domain; handhelds upload later (`received_time`).
        # Ground-truth seconds (`t_s`, removed in log v2) are never used.
        base = {"device_time_utc": r["time"], "record_time_utc": r.get("received_time") or r["time"], "raw_code": ev,
                "clock_domain_id": domain_ids.get(r.get("clock_domain") or "clkd_wcs")}  # fmt: skip
        if ev in ("tunnel_read", "tunnel_no_read"):
            sp = points["SP-TUNNEL"]
            row = {**base, "event_kind": ev, "read_outcome": "read" if ev == "tunnel_read" else "no_read",
                   "identifiers": ids if ev == "tunnel_read" else [], "device_id": sp["id"], "device_kind": "tunnel",
                   "station_id": sp["id"], "read_point_zone_id": f"zone_{sp['zone']}",
                   "dims_mm": r.get("dims_mm"), "weight_g": r.get("weight_g"),
                   "raw_description": f"tunnel photo {r['photo']}" if r.get("photo") else None}  # fmt: skip
        elif ev == "induct_to_carrier":
            sp = points["SP-INDUCT"]
            row = {**base, "event_kind": "inducted", "identifiers": ids, "read_outcome": "read" if pid else "no_read", "device_id": sp["id"],
                   "device_kind": "sorter_plc", "station_id": sp["id"], "read_point_zone_id": f"zone_{sp['zone']}",
                   "raw_description": f"carrier {r.get('carrier')}"}  # fmt: skip
        elif ev == "divert_confirm":  # without parcel_id: the sorter diverted a parcel it could not identify
            sp = points.get(r.get("scan_point")) or points[f"SP-DIV-{r['chute']}"]
            row = {**base, "event_kind": "divert_confirmed", "identifiers": ids, "read_outcome": "read" if pid else "no_read", "device_id": sp["id"],
                   "device_kind": "sorter_plc", "station_id": sp["id"], "read_point_zone_id": f"zone_{sp['zone']}",
                   "sort_destination_actual": r["chute"], "divert_confirmed": True,
                   "raw_description": f"carrier {r.get('carrier')}"}  # fmt: skip
        elif ev == "recirculate_chute_full":  # sorter could not discharge: target chute full, item stays on the loop
            sp = points.get(r.get("scan_point")) or points[f"SP-DIV-{r['chute']}"]
            row = {**base, "event_kind": "recirculated", "identifiers": ids, "read_outcome": "read" if pid else "no_read",
                   "device_id": sp["id"], "device_kind": "sorter_plc", "station_id": sp["id"],
                   "read_point_zone_id": f"zone_{sp['zone']}", "sort_destination_assigned": r["chute"],
                   "divert_confirmed": False, "reason_code": "chute_full",
                   "raw_description": f"carrier {r.get('carrier')}"}  # fmt: skip
        elif ev in ("bag_open", "bag_close"):  # container lifecycle at a chute: a bag scan, never a parcel read
            sp = handheld_point(points, r, "SP-BAG-")
            row = {**base, "event_kind": "container_opened" if ev == "bag_open" else "container_closed",
                   "container": {"scheme": "container", "value": r["bag_id"]}, "container_type": "bag",
                   "device_id": sp["id"] if sp else r.get("device_id", "handheld"), "device_kind": "handheld",
                   "station_id": sp["id"] if sp else None, "read_point_zone_id": f"zone_{sp['zone']}" if sp else None,
                   "raw_description": f"bag {r['bag_id']}" + (f" on chute {r['chute']}" if r.get("chute") else "")}  # fmt: skip
        elif ev == "container_add" and r.get("item_kind") == "bag":  # bag into roll cage: aggregation evidence
            sp = handheld_point(points, r, "SP-CAGE-")
            row = {**base, "event_kind": "container_add", "identifiers": [{"scheme": "container", "value": r["item_id"]}],
                   "container": {"scheme": "container", "value": r["container_id"]}, "container_type": "cage",
                   "device_id": sp["id"] if sp else r.get("device_id", "handheld"), "device_kind": "handheld",
                   "station_id": sp["id"] if sp else None, "read_point_zone_id": f"zone_{sp['zone']}" if sp else None,
                   "raw_description": f"bag {r['item_id']} into {r['container_id']}"}  # fmt: skip
        elif ev == "reject_bin" and not pid:
            sp = points["SP-DIV-REJECT"]
            row = {**base, "event_kind": "exception_diverted", "read_outcome": "no_read", "identifiers": [],
                   "device_id": f"chute:{r['chute']}", "device_kind": "sorter_plc", "station_id": sp["id"],
                   "read_point_zone_id": f"zone_{sp['zone']}", "sort_destination_actual": r["chute"],
                   "raw_description": "parcel without identity dropped into the reject chute"}  # fmt: skip
        else:
            # bag_drop: an anonymous chute photo-eye pulse (no parcel ID, no bag ID). Spoor's ScanEvent has no kind
            # for an event that carries neither identity nor container, so it is reported, not imported.
            skipped[ev] = skipped.get(ev, 0) + 1
            continue
        out.append({k: v for k, v in row.items() if v is not None})
    return out, skipped


def load_inputs(admin, *, clips_dir: Path, clip_start: str, scans_path: Path, spec_path: Path,
                work_dir: Path, log=print, batch: str = "hub_sim_2026-10-28_1432", skip_covered: bool = True,
                burn_mark: bool = True) -> dict:
    """Register site, cameras, clock domains, clips and the scan log through the API. `admin` is any httpx-style
    client with a site-admin token (a live server, or FastAPI's TestClient for the evaluator)."""
    caps = admin.get("/v1/capabilities").raise_for_status().json()
    if caps["sam"] or caps["spark"]:
        raise SystemExit("backend has model keys configured; this loader is for no-key mode only")
    spec = json.loads(guard(spec_path).read_text(encoding="utf-8"))
    b = spec["building"]
    W, H = b["footprint_m"]
    outline = [[-18, 0], [W, 0], [W, 58], [20, 58], [20, H], [0, H], [0, 34], [-18, 34]]  # hall + both yards
    zones = [{"zone_id": zid, "floor_id": FLOOR_ID, "name": f"{z['id']} {z['name']}", "kind": "other",
              "polygon_m": poly, "measured": False} for z in spec["zones"] for zid, poly in zone_polys(z)]  # fmt: skip
    site = {"site_id": SITE_ID, "name": "CONTOH Express Klang Valley hub (fictional)",
            "measurement_method": "design plan of a fictional hub (assets/hub/hub_spec.json); not surveyed",
            "floors": [{"floor_id": FLOOR_ID, "name": "Ground", "outline_m": outline}], "zones": zones}  # fmt: skip
    if admin.get(f"/v1/sites/{SITE_ID}").status_code == 200:
        log("site exists; re-running imports only (scan import is idempotent)")
    else:
        admin.post("/v1/sites", json=site).raise_for_status()
        log("site", SITE_ID, len(zones), "zones")

    have = {c["camera"]["camera_id"] for c in admin.get(f"/v1/sites/{SITE_ID}/cameras").json()}
    for c in spec["cameras"]:
        if f"cam_{c['id']}" in have:
            continue
        cam = {"camera_id": f"cam_{c['id']}", "site_id": SITE_ID, "floor_id": FLOOR_ID,
               "name": f"{c['id']} {c['osd_label']}", "resolution_wh_px": c["resolution"],
               "position_m": [*c["position_m"], c["height_m"]], "position_measured": False,
               "yaw_deg": c["heading_deg"], "hfov_deg": c["hfov_deg"], "orientation_measured": False,
               "fov_polygon_m": floor_footprint(c)}  # fmt: skip
        admin.post(f"/v1/sites/{SITE_ID}/cameras", json=cam).raise_for_status()
    log("cameras", len(spec["cameras"]))

    existing = {d["domain"]["name"]: d["domain"]["clock_domain_id"]
                for d in admin.get(f"/v1/sites/{SITE_ID}/clock-domains").json()}  # fmt: skip
    domain_ids = {}
    for d in spec["clock_domains"]:
        if d["id"] in existing:
            domain_ids[d["id"]] = existing[d["id"]]
            continue
        cams = [f"cam_{c['id']}" for c in spec["cameras"] if c["clock_domain"] == d["id"]]
        r = admin.post(f"/v1/sites/{SITE_ID}/clock-domains", json={"kind": d["kind"], "name": d["id"],
                                                                     "camera_ids": cams}).raise_for_status()  # fmt: skip
        domain_ids[d["id"]] = r.json()["clock_domain_id"]
    log("clock domains", len(domain_ids), "(no fits: anchors need observed events)")

    clips = sorted(guard(clips_dir).glob("CAM_*.mp4")) if clips_dir.exists() else []
    with tempfile.TemporaryDirectory() as tmp:
        for clip in clips:
            cam_id = f"cam_{clip.stem}"
            cams = admin.get(f"/v1/sites/{SITE_ID}/cameras").json()
            mine = next((x for x in cams if x["camera"]["camera_id"] == cam_id), None)
            if mine is None:
                log("skip clip without camera", clip.name)
                continue
            if mine["coverage"] and skip_covered:
                log("already ingested", clip.name)
                continue
            if mine["clock_sync"] is None:
                admin.post(f"/v1/cameras/{cam_id}/clock-syncs", json={
                    "offset_ms": 0, "uncertainty_ms": 5000,
                    "method": "UNVERIFIED: uploader-declared recording start; no anchor event matched yet",
                    "anchor_description": "none (no-key mode: anchors need observed events)"}).raise_for_status()
            # Final CCTV renders already carry the burned-in SYNTHETIC mark; only unmarked QA renders get one added.
            marked = mark_synthetic(clip, Path(tmp)) if burn_mark else clip
            meta = {"site_id": SITE_ID, "camera_id": cam_id,
                    "rights_statement": "Synthetic footage rendered from a fictional hub model; no real people",
                    "purpose": "Spoor no-key demonstration", "consent_confirmed": True,
                    "hosted_processing_allowed": False, "retention_days": 30,
                    "recording_start_camera_time": clip_start, "recording_kind": "synthetic_test"}  # fmt: skip
            with marked.open("rb") as fh:
                r = admin.post("/v1/media/uploads", data={"meta": json.dumps(meta)},
                               files={"file": (clip.name, fh, "video/mp4")})  # fmt: skip
            r.raise_for_status()
            log("clip", clip.name, r.json()["media_id"], r.json()["frames"], "frames")

    lines = guard(scans_path).read_text(encoding="utf-8").splitlines()
    rows, skipped = convert_scans(lines, domain_ids, spec)
    work_dir.mkdir(parents=True, exist_ok=True)
    conv = work_dir / "scans_converted.jsonl"
    conv.write_text("".join(json.dumps(r) + chr(10) for r in rows), encoding="utf-8")
    r = admin.post(f"/v1/sites/{SITE_ID}/scans/import",
                   data={"batch": batch, "source": "simulated"},
                   files={"file": ("events_scan_simulated.jsonl", conv.read_bytes(), "application/x-ndjson")})
    r.raise_for_status()
    log("scans", r.json(), "not imported:", skipped)
    return {"spec": spec, "rows": rows, "lines": lines, "skipped": skipped, "clips": clips, "domain_ids": domain_ids}


def import_photo_eyes(admin, case_id: str, lines: list[str]) -> int:
    csv_text, n = photo_eye_csv(lines)
    if not n:
        return 0
    imp = admin.post(f"/v1/cases/{case_id}/evidence/import", data={"batch": "hub_sim_photo_eyes"},
                     files={"file": ("photo_eyes.csv", csv_text.encode(), "text/csv")}).raise_for_status().json()
    return len(imp["imported"])


def seed_scenarios(admin, inv, manifest: Path, spec_path: Path, work_dir: Path) -> None:
    """QUEUE F1: one INPUT case per rendered scenario, from a manifest the builder writes next to the scenario cards:
    [{"scenario": "S3", "title": "Wrong bag at bagging", "parcel": "CTX...", "subject_kind": "parcel",
      "clips": "<dir of CAM_XX.mp4>", "scans": "<scan-log slice .jsonl>", "clip_start": "2026-10-28T14:32:07+08:00"}]
    Paths are relative to the manifest (ml/evaluation/scenarios/manifest.json, written by assets/hub/make_cards.py).
    subject_kind "container" (e.g. S4) means `parcel` holds a roll-cage RFID id (RC-xxx). The question comes from
    <S>/case_input.json when present. The subject comes from the scenario card, never from truth."""
    items = json.loads(guard(manifest).read_text(encoding="utf-8"))
    existing = {c["case"]["question"] for c in inv.get("/v1/cases").json()}
    for it in items:
        base = manifest.parent
        kind = it.get("subject_kind", "parcel")
        got = load_inputs(admin, clips_dir=base / it["clips"], clip_start=it["clip_start"], scans_path=base / it["scans"],
                          spec_path=spec_path, work_dir=work_dir / it["scenario"], batch=f"scenario_{it['scenario']}",
                          skip_covered=False, burn_mark=False)  # fmt: skip
        ci = base / it["scenario"] / "case_input.json"
        asked = json.loads(guard(ci).read_text(encoding="utf-8")).get("question") if ci.exists() else None
        default = (f"which truck did cage {it['parcel']} go onto?" if kind == "container"
                   else f"where did parcel {it['parcel']} go after its last scan?")  # fmt: skip
        q = f"{it['scenario']} · {it['title']}: {asked or default}"
        if q in existing:
            print("case exists:", q)
            continue
        body = case_body(it["parcel"], got["clips"], it["clip_start"], question=q, subject_kind=kind,
                         window_s=max(40.0, clip_seconds(got["clips"]) + 5))  # fmt: skip
        r = inv.post("/v1/cases", json=body)
        r.raise_for_status()
        print("scenario case", it["scenario"], r.json()["case"]["case_id"])
        import_photo_eyes(admin, r.json()["case"]["case_id"], got["lines"])


def case_body(subject: str, clips: list[Path], clip_start: str, question: str | None = None, *,
              subject_kind: str = "parcel", window_s: float = 40.0) -> dict:
    """Input case. subject_kind "parcel" = a waybill; "container" = a roll-cage / bag id (scheme "container")."""
    t0 = datetime.fromisoformat(clip_start)
    if subject_kind == "container":
        default_q, target, ident = (f"Which truck did cage {subject} go onto?", f"roll cage {subject}",
                                    {"scheme": "container", "value": subject})  # fmt: skip
    else:
        default_q, target, ident = (f"Where did parcel {subject} go after its last scan?", f"parcel {subject}",
                                    {"scheme": "carrier_waybill", "value": subject})  # fmt: skip
    return {"site_id": SITE_ID, "question": question or default_q, "target_description": target,
            "camera_ids": [f"cam_{c.stem}" for c in clips],
            "window": {"start_utc": (t0 - timedelta(seconds=5)).isoformat(),
                       "end_utc": (t0 + timedelta(seconds=window_s)).isoformat()},
            "identifiers": [ident]}  # fmt: skip


def clip_seconds(clips: list[Path]) -> float:
    """Longest clip duration (ffprobe), so a scenario's case window covers all its footage."""
    longest = 0.0
    for c in clips:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(c)],
                           capture_output=True, text=True)  # fmt: skip
        try:
            longest = max(longest, float(r.stdout.strip()))
        except ValueError:
            pass
    return longest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", default=str(FRONT / ".local/clips"), help="dir of CAM_XX.mp4 (synthetic renders)")
    ap.add_argument("--clip-start", default=DEFAULT_CLIP_START)
    ap.add_argument("--scans", default=str(REPO / "assets/hub/build/sim/events_scan_simulated.jsonl"))
    ap.add_argument("--spec", default=str(REPO / "assets/hub/hub_spec.json"))
    ap.add_argument("--case-parcel", default="auto", help="parcel ID, or auto = the parcel with the most reads")
    ap.add_argument("--scenarios", default=None, help="scenario manifest JSON (QUEUE F1); one input case per scenario")
    args = ap.parse_args()

    env = load_env()
    api = env.get("SPOOR_API_URL", "http://127.0.0.1:8000")
    admin = httpx.Client(base_url=api, headers={"Authorization": f"Bearer {env['SPOOR_TOKEN_SITE_ADMIN']}"},
                         timeout=300)  # fmt: skip
    inv = httpx.Client(base_url=api, headers={"Authorization": f"Bearer {env['SPOOR_TOKEN_INVESTIGATOR']}"},
                       timeout=300)  # fmt: skip
    local = FRONT / ".local"
    if args.scenarios:
        seed_scenarios(admin, inv, Path(args.scenarios), Path(args.spec), local / "scenarios")
        return
    got = load_inputs(admin, clips_dir=Path(args.clips), clip_start=args.clip_start, scans_path=Path(args.scans),
                      spec_path=Path(args.spec), work_dir=local)  # fmt: skip
    rows, skipped, clips = got["rows"], got["skipped"], got["clips"]

    auto = args.case_parcel == "auto"
    if auto:  # an operator choice of INPUT case, made from the scan log only (PRD §23)
        counts: dict[str, int] = {}
        for row in rows:
            for i in row.get("identifiers", []):
                if i["scheme"] == "carrier_waybill":
                    counts[i["value"]] = counts.get(i["value"], 0) + 1
        args.case_parcel = max(sorted(counts), key=lambda k: counts[k])
    cases = inv.get("/v1/cases").json()
    if not (auto and cases) and not any(c["case"]["target_description"].endswith(args.case_parcel) for c in cases):
        r = inv.post("/v1/cases", json=case_body(args.case_parcel, clips, args.clip_start)).raise_for_status().json()
        print("case", r["case"]["case_id"])
        n = import_photo_eyes(admin, r["case"]["case_id"], got["lines"])
        if n:
            print("photo-eye pulses imported as simulated sensor events:", n)
            skipped.pop("bag_drop", None)
    (local / "seed_report.json").write_text(json.dumps({"scans_not_imported": skipped, "clips": [c.name for c in clips]},
                                                       indent=1), encoding="utf-8")  # fmt: skip


if __name__ == "__main__":
    main()
