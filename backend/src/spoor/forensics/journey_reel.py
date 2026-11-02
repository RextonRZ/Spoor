"""The journey reel (Rexton, 2 Nov): ONE video of the parcel's whole journey, every checkpoint's clip joined in time
order, SAM's own outline (its mask edge) on the carton on every frame where SAM followed it, and a short card where
nothing can be seen (in a cage with no footage, inside the store). Built from stored evidence only.

Each segment burns in its camera, the shared clock, the checkpoint, a green "Scanned here" or a red "No scan", and
the tracking number only when that handshake carries it (labelled). The outline is drawn only on frames SAM followed
the carton (a handshake's frames up to the scan, the live alert's track, the verified doorway track); never on a
guess, never on a person. A manifest lists the chapters (title, start, end, tone) and every source clip with its hash."""

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

W, H = 1280, 720
FPS = 10
MYT = timezone(timedelta(hours=8))
GREEN, RED, INK, MUTE, BG = (128, 222, 74), (113, 113, 248), (244, 242, 240), (170, 168, 165), (18, 15, 13)


@dataclass
class Segment:
    title: str  # the checkpoint, plain words ("Into chute C12")
    tone: str  # "scan" (green) | "noscan" (red) | "card"
    t: datetime  # its moment on the shared clock
    camera: str = ""
    media_path: Path | None = None
    sha256: str = ""
    start_utc: datetime | None = None  # the clip's first frame on the shared clock
    f0: int = 0
    f1: int = 0
    label: str | None = None  # the tracking number, only when the handshake is labelled
    contours: dict[int, list[list[float]]] = field(default_factory=dict)
    boxes: dict[int, list[float]] = field(default_factory=dict)
    sub: str = ""  # one plain line under the title (cards, and the reason for a no-scan step)
    image: Path | None = None  # a still to show instead of a clip (the tunnel's own photo)
    seconds: float = 2.4  # how long a card or a still is held


def _txt(img, s, xy, scale=0.62, color=INK, thick=1):
    cv2.putText(img, s, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, s, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def _fit(frame: np.ndarray) -> tuple[np.ndarray, float, int, int]:
    """Scale a frame to cover 1280x720 (centre crop); returns the image and the mapping (k, dx, dy)."""
    h, w = frame.shape[:2]
    k = max(W / w, H / h)
    img = cv2.resize(frame, (round(w * k), round(h * k)), interpolation=cv2.INTER_AREA)
    dx, dy = (img.shape[1] - W) // 2, (img.shape[0] - H) // 2
    return img[dy:dy + H, dx:dx + W].copy(), k, dx, dy


def _burn(img, seg: Segment, when: datetime):
    cv2.rectangle(img, (0, H - 58), (W, H), (10, 10, 12), -1)
    _txt(img, f"{seg.camera}   {when.astimezone(MYT):%H:%M:%S}   {seg.title}", (24, H - 22), 0.66)
    badge, col = ("Scanned here", GREEN) if seg.tone == "scan" else ("No scan", RED)
    (tw, _), _ = cv2.getTextSize(badge, cv2.FONT_HERSHEY_SIMPLEX, 0.62, 2)
    cv2.rectangle(img, (W - tw - 46, H - 46), (W - 22, H - 14), col, -1)
    cv2.putText(img, badge, (W - tw - 34, H - 23), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (12, 12, 12), 2, cv2.LINE_AA)
    _txt(img, "SYNTHETIC - fictional hub", (W - 250, 30), 0.5, MUTE)
    if seg.sub:
        _txt(img, seg.sub, (24, H - 72), 0.58, MUTE)


def _outline(img, seg: Segment, f: int, k: float, dx: int, dy: int):
    poly = seg.contours.get(f)
    box = seg.boxes.get(f)
    if poly:
        pts = np.array([[(x * k - dx), (y * k - dy)] for x, y in poly], np.int32)
        cv2.polylines(img, [pts], True, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.polylines(img, [pts], True, GREEN, 2, cv2.LINE_AA)
        top = pts[pts[:, 1].argmin()]
    elif box:
        p1, p2 = (round(box[0] * k - dx), round(box[1] * k - dy)), (round(box[2] * k - dx), round(box[3] * k - dy))
        cv2.rectangle(img, p1, p2, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.rectangle(img, p1, p2, GREEN, 2, cv2.LINE_AA)
        top = np.array(p1)
    else:
        return
    if seg.label:
        x, y = int(top[0]), max(24, int(top[1]) - 12)
        (tw, th), _ = cv2.getTextSize(seg.label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(img, (x - 4, y - th - 6), (x + tw + 4, y + 4), GREEN, -1)
        cv2.putText(img, seg.label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (8, 30, 12), 1, cv2.LINE_AA)


def _card(seg: Segment) -> np.ndarray:
    img = np.full((H, W, 3), BG, np.uint8)
    _txt(img, seg.title, (64, H // 2 - 14), 1.1, INK, 2)
    if seg.sub:
        _txt(img, seg.sub, (64, H // 2 + 30), 0.7, MUTE)
    _txt(img, f"{seg.t.astimezone(MYT):%H:%M:%S}", (64, H // 2 - 70), 0.7, RED if seg.tone == "noscan" else MUTE)
    return img


def build_journey_reel(segments: list[Segment], out_dir: Path, reel_id: str, title: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    chapters, sources = [], []
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.avi"
        vw = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
        n = 0

        def hold(img, seconds):
            nonlocal n
            for _ in range(max(1, round(seconds * FPS))):
                vw.write(img)
                n += 1

        intro = np.full((H, W, 3), BG, np.uint8)
        _txt(intro, "The parcel's journey", (64, H // 2 - 20), 1.2, INK, 2)
        _txt(intro, title, (64, H // 2 + 26), 0.72, MUTE)
        _txt(intro, "Every clip from the hub's own cameras, in time order. Outline: SAM 3.1, where it followed the carton.",
             (64, H // 2 + 64), 0.55, MUTE)
        hold(intro, 2.4)
        for seg in sorted(segments, key=lambda s: s.t):
            start = n / FPS
            if seg.media_path is None and seg.image is None:
                hold(_card(seg), seg.seconds)
            elif seg.image is not None:
                still = cv2.imread(str(seg.image))
                img, *_ = _fit(still)
                _burn(img, seg, seg.t)
                if seg.label:
                    _txt(img, seg.label, (24, 40), 0.7, GREEN, 2)
                hold(img, seg.seconds)
                sources.append({"kind": "still", "path": seg.image.name, "title": seg.title})
            else:
                cap = cv2.VideoCapture(str(seg.media_path))
                cap.set(cv2.CAP_PROP_POS_FRAMES, seg.f0)
                for f in range(seg.f0, seg.f1 + 1):
                    ok, frame = cap.read()
                    if not ok:
                        break
                    img, k, dx, dy = _fit(frame)
                    _outline(img, seg, f, k, dx, dy)
                    when = (seg.start_utc + timedelta(seconds=f / FPS)) if seg.start_utc else seg.t
                    _burn(img, seg, when)
                    vw.write(img)
                    n += 1
                cap.release()
                sources.append({"kind": "clip", "camera": seg.camera, "sha256": seg.sha256, "frames": [seg.f0, seg.f1],
                                "outlined_frames": len(seg.contours) or len(seg.boxes), "title": seg.title})
            chapters.append({"title": seg.title, "tone": seg.tone, "t": seg.t.isoformat(), "start_s": round(start, 2),
                             "end_s": round(n / FPS, 2), "camera": seg.camera, "label": seg.label, "sub": seg.sub})
        vw.release()
        mp4 = out_dir / f"{reel_id}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)], check=True)  # fmt: skip
    manifest = {"reel_id": reel_id, "kind": "journey", "seconds": round(n / FPS, 1), "chapters": chapters,
                "sources": sources, "label": "built from stored evidence; synthetic footage; outline = SAM 3.1"}
    (out_dir / f"{reel_id}.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


TITLES = {"arrived_facility": "Unloaded", "tunnel_read": "Label read in the tunnel", "inducted": "On the sorter",
          "divert_confirmed": "Into chute {chute}", "recirculated": "Went round again", "container_add": "Into cage {cage}",
          "container_remove": "Out of cage {cage}"}  # fmt: skip
WHY = {"cant_tell": "Several cartons handled here at once: no outline",
       "clock_not_fitted": "This camera's clock is not fitted closely enough to pick the carton",
       "not_found": "No outline: nothing stood out at the scan point at that instant",
       "outlined": "Outlined, but it could not be told from the carton next to it"}  # fmt: skip
PAD = 15  # frames shown before and after a moment (1.5 s at 10 fps)


def _hm(t: datetime) -> str:
    return f"{t.astimezone(MYT):%H:%M}"


def journey_segments(svc, case, waybill: str, answer: dict | None) -> list[Segment]:
    """The case's journey as reel segments, from stored evidence only: the passport's best stamp per scan, the live
    alert that named this parcel, the verified answer's tracks and clips, and the truck record. Cards where nothing
    can be seen. Labels only from labelled handshakes; outlines only from SAM tracks on that clip."""
    from spoor.contracts import MediaAsset, ScanEvent
    from spoor.contracts.observations import CameraCoverage, RawObservation
    from spoor.ingest import asset_path, load_result
    from spoor.perception.contours import contours_for
    from spoor.store import LiveAlert, ScanHandshake

    cams = set(svc.case_cameras(case))
    invalid = svc.store.invalid_ids()

    def track(mid, tid, upto=None):
        obs = sorted((o for o in svc.store.find(RawObservation, track_id=tid)
                      if o.bbox_xyxy_px and o.source_frame.media_id == mid), key=lambda o: o.source_frame.frame_index)  # fmt: skip
        boxes = [(o.source_frame.frame_index, tuple(o.bbox_xyxy_px)) for o in obs
                 if upto is None or o.source_frame.frame_index <= upto]  # fmt: skip
        sha = load_result(svc.media, mid).proxy.sha256[:16]
        polys = contours_for(boxes, sorted((svc.settings.data_dir / "inference_cache").glob(f"sam_{sha}_*.json")))
        return polys, {f: list(b) for f, b in boxes}

    def clip_at(camera, t):
        for c in svc.store.find(CameraCoverage, camera_id=camera):
            m = svc.store.get(MediaAsset, c.media_id)
            if c.start_utc <= t <= c.end_utc and m.media_id not in invalid and m.probe and m.probe.width_px <= 1920:
                return m
        return None

    def clip(seg, mid, t, before=PAD, after=PAD):
        m = svc.store.get(MediaAsset, mid)
        f = svc.frame_at(mid, t.isoformat())
        seg.camera = (m.camera_id or "").removeprefix("cam_")
        seg.media_path, seg.sha256 = asset_path(svc.media, m), m.sha256
        seg.start_utc = svc.store.find(CameraCoverage, media_id=mid)[-1].start_utc
        seg.f0, seg.f1 = max(0, f - before), min(len(load_result(svc.media, mid).original_frames.pts_ms) - 1, f + after)
        return seg

    segs: list[Segment] = []
    # scans: the best stamp per scan (labelled, then outlined, then any clip; a close-up first), as the passport
    by: dict[str, list] = {}
    for h in svc.store.find(ScanHandshake, waybill=waybill):
        if not (h.media_id and h.media_id in invalid):
            by.setdefault(h.scan_event_id, []).append(h)

    def rank(h):
        return (0 if h.labelled else 2 if h.outcome == "outlined" else 3 if h.media_id else 5) + \
            (0 if h.camera_id.startswith("cam_CHK_") else 1)  # fmt: skip

    last = None
    photo = svc.settings.data_dir / "scanner" / f"{waybill}.jpg"
    for hs in by.values():
        h = min(hs, key=rank)
        ev = svc.store.get(ScanEvent, h.scan_event_id)
        last = ev if last is None or ev.device_time_utc > last.device_time_utc else last
        title = TITLES.get(h.event_kind, h.event_kind.replace("_", " ").capitalize()).format(
            chute=(h.scan_point_id or "").rsplit("-", 1)[-1], cage=ev.container.value if ev.container else "")
        seg = Segment(title=title, tone="scan", t=ev.device_time_utc)
        if h.event_kind == "tunnel_read" and photo.exists():
            seg.image, seg.label, seg.camera, seg.sub = photo, waybill, "Tunnel reader", "The reader's own photo at the read"
        elif not h.media_id or svc.store.get(MediaAsset, h.media_id).camera_id not in cams:
            continue
        elif h.outcome == "outlined" and h.labelled and h.track_id:
            clip(seg, h.media_id, ev.device_time_utc, after=max(PAD, h.frames_followed + 5))
            seg.contours, seg.boxes = track(h.media_id, h.track_id, upto=(h.frame_index or 0) + h.frames_followed)
            seg.label = waybill
        else:
            clip(seg, h.media_id, ev.device_time_utc)
            seg.sub = WHY.get(h.outcome, "")
        segs.append(seg)
    if last is None:
        return segs
    # after the last scan: the live alert that named only this parcel (taken out, no scan)
    where = last.container.value if last.container else "its last place"
    alert = next((a for a in sorted(svc.store.find(LiveAlert), key=lambda a: a.at_utc)
                  if len(a.candidates) == 1 and a.candidates[0]["waybill"] == waybill), None)  # fmt: skip
    if alert is not None:
        mins = round((alert.at_utc - last.device_time_utc).total_seconds() / 60)
        segs.append(Segment(title=f"In {where}, no scan for {mins} min", tone="noscan",
                            t=last.device_time_utc + timedelta(seconds=1),
                            sub=f"{_hm(last.device_time_utc)} to {_hm(alert.at_utc)}: no scan, no camera saw it move"))
        polys, boxes = track(alert.media_id, alert.track_id)
        seg = Segment(title=f"Taken out of {where}", tone="noscan", t=alert.at_utc,
                      sub=f"No scan. The only parcel in {where} with no scan since: could be {waybill}")
        clip(seg, alert.media_id, alert.at_utc, before=alert.frame_index - min(boxes, default=alert.frame_index) + 5)
        seg.contours, seg.boxes = polys, boxes
        segs.append(seg)
    # the verified answer: carried to the store door on its track, into the store, out without it
    inside = next((o["inside"] for o in (answer or {}).get("objects", []) if o.get("inside")), None)
    if not inside:
        return segs
    place = inside["place"].split(" (")[0]
    o = svc.store.get(RawObservation, inside["observation_id"])
    polys, boxes = track(inside["media_id"], o.track_id)
    door_t = datetime.fromisoformat(inside["iso"]["door_at"])
    seg = Segment(title=f"Carried to the door of the {place}", tone="noscan", t=door_t,
                  sub="No scan. SAM followed the carton in the carrier's hands")
    f_door = svc.frame_at(inside["media_id"], door_t.isoformat())
    clip(seg, inside["media_id"], door_t, before=f_door - min(boxes, default=f_door) + 5, after=5)
    seg.contours, seg.boxes = polys, boxes
    segs.append(seg)
    for key, title, sub in [("carried_in_at", f"Carried into the {place}", "Past the scan-in post: no scan"),
                            ("came_out_0", "Came out without it", "The carrier leaves empty-handed")]:
        if key in inside["iso"]:
            t = datetime.fromisoformat(inside["iso"][key])
            if (m := clip_at("cam_CHK_STORE", t)) is not None:
                segs.append(clip(Segment(title=title, tone="noscan", t=t, sub=sub), m.media_id, t, before=25, after=25))
    # the record that says it left, made while the cameras show it still inside
    until = datetime.fromisoformat(inside["iso"]["until"])
    rec = next((s for s in sorted(svc.store.find(ScanEvent, event_kind="container_loaded"), key=lambda s: s.device_time_utc)
                if any(i.value == where for i in [*s.identifiers, *([s.container] if s.container else [])])
                and door_t < s.device_time_utc < until), None)  # fmt: skip
    if rec is not None and (m := clip_at("cam_CHK_DOCK", rec.device_time_utc)) is not None:
        door = next((p for p in (rec.station_id or "").split("-") if p.startswith("D")), "")
        segs.append(clip(Segment(title=f"Record: {where} loaded on truck {door}".strip(), tone="noscan",
                                 t=rec.device_time_utc, sub="The cage leaves. The cameras say the carton is still inside"),
                         m.media_id, rec.device_time_utc, before=30, after=30))  # fmt: skip
    segs.append(Segment(title=f"Most likely in the {inside['place']}", tone="card", t=until,
                        sub=f"Carried in at {inside['carried_in_at']}, not seen coming out", seconds=3.0))
    return segs
