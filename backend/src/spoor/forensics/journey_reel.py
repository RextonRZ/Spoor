"""The journey reel (Rexton, 2 Nov): ONE video of the parcel's whole journey, every checkpoint's clip joined in time
order, SAM's own outline (its mask edge) on the carton on every frame where SAM followed it, and a short card where
nothing can be seen (in a cage with no footage, inside the store). Built from stored evidence only.

Each segment burns in its camera, the shared clock, the checkpoint and one badge: green "Scanned" ("Last scan" on the last one), grey "On camera"
(seen with no scan, which is the good news), and red only where the records fail: "Not scanned in" at the one place a
scan should have happened, and "Records disagree" on a record the cameras contradict. The tracking number shows only when that handshake carries it (labelled). The outline is drawn only on frames SAM followed
the carton (a handshake's frames up to the scan, the live alert's track, the verified doorway track); never on a
guess, never on a person. A manifest lists the chapters (title, start, end, tone) and every source clip with its hash."""

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from spoor.forensics import reel_style as RS

W, H = RS.W, RS.H
FPS = 10
MYT = timezone(timedelta(hours=8))
# how a "loaded" record is made (no person types it): the cage is read, and every parcel scanned into it counts as loaded
LOAD_HOW = {"rfid_portal": "Automatic: the door's RFID reader read the cage's tag, so every parcel in it counts as "
                             "loaded. The cameras say this carton is still inside",
            "handheld": "A scan of the cage at the door marks every parcel in it as loaded. The cameras say this "
                          "carton is still inside",
            None: "The cage's load record counts every parcel in it as loaded. The cameras say this carton is still inside"}


@dataclass
class Segment:
    title: str  # the checkpoint, plain words ("Into chute C12")
    tone: str  # "scan" (green) | "seen" (on camera, grey) | "noscan" | "record" (red) | "wait" (no camera) | "card"
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
    media_id: str = ""
    track_id: str = ""  # the SAM track whose outline is drawn (for screens that show one frame of it)
    xy: tuple[float, float] | None = None  # where on the plan (its scan point, the store door, the truck's read point)
    last_scan: bool = False  # the last scan the records have: everything after it comes from cameras only


ZOOM_BELOW = 0.22  # an outline narrower than this share of the frame is shown on a crop around it (a far camera)
MIN_CROP = 0.6  # ...but never zoomed past 1/0.6 of the frame (a 0.38 crop blew a far carton up soft and squashed: Rexton)
XFADE = 4  # frames (0.4 s) of crossfade into each chapter
EASE = (0.4, 0.7, 1.0)  # the outline's first frames in a chapter
PUSH = 0.06  # a slow push-in toward the carton over each clip (calm: evidence, not a trailer)


def _focus(seg: Segment, w: int, h: int) -> tuple[int, int, int, int] | None:
    """One steady 16:9 crop around everything SAM outlined in this chapter, when the outline is small in the frame."""
    if not seg.boxes:
        return None
    bs = np.array(list(seg.boxes.values()), float)
    x0, y0, x1, y1 = bs[:, 0].min(), bs[:, 1].min(), bs[:, 2].max(), bs[:, 3].max()
    if x1 - x0 >= ZOOM_BELOW * w:
        return None
    cw = min(w, max(3.0 * (x1 - x0), 3.0 * (y1 - y0) * 16 / 9, MIN_CROP * w))
    ch = cw * 9 / 16
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left, top = min(max(0.0, cx - cw / 2), w - cw), min(max(0.0, cy - ch / 2), h - ch)
    return round(left), round(top), round(left + cw), round(top + ch)


def _fit(frame: np.ndarray) -> tuple[np.ndarray, float, int, int]:
    """Scale a frame to cover 1280x720 (centre crop); returns the image and the mapping (k, dx, dy)."""
    h, w = frame.shape[:2]
    k = max(W / w, H / h)
    img = cv2.resize(frame, (round(w * k), round(h * k)), interpolation=cv2.INTER_AREA)
    dx, dy = (img.shape[1] - W) // 2, (img.shape[0] - H) // 2
    return img[dy:dy + H, dx:dx + W].copy(), k, dx, dy


def _frame(seg: Segment | None, f: int) -> np.ndarray | None:
    if seg is None or seg.media_path is None:
        return None
    cap = cv2.VideoCapture(str(seg.media_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, f)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def _shape(seg: Segment, f: int, k: float, dx: int, dy: int, ox: int = 0, oy: int = 0):
    c = seg.contours.get(f)
    poly = [[(x - ox) * k - dx, (y - oy) * k - dy] for x, y in c] if c else None
    b = seg.boxes.get(f)
    box = [(b[0] - ox) * k - dx, (b[1] - oy) * k - dy, (b[2] - ox) * k - dx, (b[3] - oy) * k - dy] if b else None
    return poly, box


def _chip_tone(seg: Segment) -> str | None:
    return "last" if seg.last_scan else seg.tone if seg.tone in ("scan", "seen", "noscan", "record") else None


def _short(g: Segment) -> str:
    """A checkpoint's name on the answer card's rail."""
    if g.tone == "noscan":
        return "Store door"
    if g.tone == "record":
        return "Truck " + g.title.split(" on ")[-1] if " on " in g.title else "Truck"
    t = g.title
    for a, b in (("Label read in the tunnel", "Tunnel"), ("Into chute ", "Chute "), ("Into cage ", "Cage ")):
        t = t.replace(a, b)
    return t


def build_journey_reel(segments: list[Segment], out_dir: Path, reel_id: str, title: str) -> dict:
    """The reel in Spoor's style (reel_style.py): an intro card, every chapter with one top bar and a progress rail,
    crossfades between chapters, cards on their own camera frame, the answer card last."""
    segs = sorted(segments, key=lambda s: s.t)
    tones = [s.tone for s in segs]
    out_dir.mkdir(parents=True, exist_ok=True)
    chapters, sources = [], []
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.avi"
        vw = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
        n = 0
        last: list = [None]

        thumbs: dict = {}

        def put_seq(frames):
            """A chapter's frames, its first XFADE frames cross-faded from the last frame shown."""
            nonlocal n
            prev = last[0]
            if frames:
                thumbs["mid"] = frames[min(len(frames) - 1, max(XFADE + 1, len(frames) // 2))]
            for i, img in enumerate(frames):
                if prev is not None and i < XFADE:
                    a = (i + 1) / (XFADE + 1)
                    img = cv2.addWeighted(img, a, prev, 1 - a, 0)
                vw.write(img)
                last[0] = img
                n += 1

        def hold_card(bg, lines, seconds, **kw):
            steady = RS.card(bg, lines, **kw)
            frames = [RS.card(bg, lines, rise=(i + 1) / 3, **kw) for i in range(2)]  # text fades up 8 px over 0.3 s
            put_seq(frames + [steady] * max(1, round(seconds * FPS) - 2))

        first_clip = next((g for g in segs if g.media_path is not None), None)
        hold_card(RS.blurred(_frame(first_clip, first_clip.f0) if first_clip else None),
                  [(f"Parcel {title}", 34, 600, RS.INK), ("Its journey through the hub, on camera", 20, 400, RS.MUTE)],
                  2.0, logo=True)
        for ci, seg in enumerate(segs):
            start = n / FPS
            if seg.media_path is None and seg.image is None:
                prev_clip = next((g for g in reversed(segs[:ci]) if g.media_path is not None), None)
                if seg.tone == "card":  # the answer: the store door frame, SAM's outline frozen on the carton
                    door = next((g for g in segs if g.tone == "noscan" and g.media_path is not None), prev_clip)
                    bg = RS.blurred(None)
                    if door is not None:
                        keys = sorted(door.contours or door.boxes) or [door.f0]
                        bg = RS.blurred(_frame(door, keys[len(keys) // 2]))
                    dots = [(_short(g), g.tone if g.tone in ("noscan", "record") else "scan", g.tone == "noscan")
                            for g in segs if g.tone in ("scan", "noscan", "record") and g.title != TITLES["inducted"]]
                    hold_card(bg, [(f"{seg.t.astimezone(MYT):%H:%M:%S} · end of recording", 17, 400, RS.MUTE),
                                   (seg.title, 36, 600, RS.INK), (seg.sub, 20, 400, RS.MUTE)], 3.0, dots=dots, footer=True)
                else:
                    bg = RS.blurred(_frame(prev_clip, prev_clip.f1) if prev_clip else None)
                    hold_card(bg, [(f"{seg.t.astimezone(MYT):%H:%M:%S}", 22, 500, RS.MUTE), (seg.title, 34, 600, RS.INK),
                                   (seg.sub, 20, 400, RS.MUTE)], seg.seconds)
            elif seg.image is not None:
                img, top = RS.still_card(cv2.imread(str(seg.image)), seg.label, seg.sub)
                img = RS.top_bar(img, time=f"{seg.t.astimezone(MYT):%H:%M:%S}", title=seg.title, tone=_chip_tone(seg),
                                 tones=tones, cur=ci, note="Tunnel reader")
                if seg.label and top:
                    img = RS.tag(img, seg.label, top)
                put_seq([img] * max(1, round(seg.seconds * FPS)))
                sources.append({"kind": "still", "path": seg.image.name, "title": seg.title})
            else:
                cap = cv2.VideoCapture(str(seg.media_path))
                cap.set(cv2.CAP_PROP_POS_FRAMES, seg.f0)
                crop = _focus(seg, int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                frames, drawn = [], 0
                fw, fh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                bx0, by0, bx1, by1 = crop if crop else (0, 0, fw, fh)
                if seg.boxes:  # push in toward where SAM had the carton
                    bs = np.array(list(seg.boxes.values()), float)
                    fx_, fy_ = (bs[:, 0].mean() + bs[:, 2].mean()) / 2, (bs[:, 1].mean() + bs[:, 3].mean()) / 2
                else:
                    fx_, fy_ = (bx0 + bx1) / 2, (by0 + by1) / 2
                nfr = max(1, seg.f1 - seg.f0)
                for f in range(seg.f0, seg.f1 + 1):
                    ok, frame = cap.read()
                    if not ok:
                        break
                    u = (f - seg.f0) / nfr
                    z = 1 + PUSH * (3 * u * u - 2 * u ** 3)  # ease in-out
                    cw, ch = (bx1 - bx0) / z, (by1 - by0) / z
                    sx0 = min(max(bx0, fx_ - (fx_ - bx0) / z), bx1 - cw)
                    sy0 = min(max(by0, fy_ - (fy_ - by0) / z), by1 - ch)
                    sub = (round(sx0), round(sy0), round(sx0 + cw), round(sy0 + ch))
                    frame = frame[sub[1]:sub[3], sub[0]:sub[2]]
                    img, k, dx, dy = _fit(frame)
                    poly, box = _shape(seg, f, k, dx, dy, sub[0], sub[1])
                    top = None
                    if poly or box:
                        img, top = RS.outline(img, poly, box, EASE[min(drawn, len(EASE) - 1)])
                        drawn += 1
                    when = (seg.start_utc + timedelta(seconds=f / FPS)) if seg.start_utc else seg.t
                    img = RS.top_bar(img, time=f"{when.astimezone(MYT):%H:%M:%S}", title=seg.title, tone=_chip_tone(seg),
                                     sub=seg.sub, tones=tones, cur=ci, rise=(f - seg.f0 + 1) / 3)
                    if seg.label and top:
                        img = RS.tag(img, seg.label, top, min_y=104 if seg.sub else 76)
                    frames.append(img)
                cap.release()
                put_seq(frames)
                sources.append({"kind": "clip", "camera": seg.camera, "sha256": seg.sha256, "frames": [seg.f0, seg.f1],
                                "outlined_frames": len(seg.contours) or len(seg.boxes), "title": seg.title,
                                "zoomed_to": list(crop) if crop else None})
            if last[0] is not None:  # the step's thumbnail for the web player's strip: its middle frame
                mid = thumbs.get("mid")
                cv2.imwrite(str(out_dir / f"{reel_id}_t{ci}.jpg"), cv2.resize(mid if mid is not None else last[0], (320, 180),
                                                                         interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 82])
                thumbs.clear()
            chapters.append({"title": seg.title, "tone": seg.tone, "t": seg.t.isoformat(), "start_s": round(start, 2),
                             "end_s": round(n / FPS, 2), "camera": seg.camera, "label": seg.label, "sub": seg.sub,
                             "media_id": seg.media_id or None, "track_id": seg.track_id or None,
                             "xy": list(seg.xy) if seg.xy else None, "last_scan": seg.last_scan, "thumb": f"t{ci}"})
        vw.release()
        mp4 = out_dir / f"{reel_id}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-metadata", "comment=synthetic footage of a fictional hub",
                        str(mp4)], check=True)  # fmt: skip
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
       "outlined": "Too close to the next carton to label"}  # fmt: skip
PAD = 15  # frames shown before and after a moment (1.5 s at 10 fps)


def _hm(t: datetime) -> str:
    return f"{t.astimezone(MYT):%H:%M}"


def journey_segments(svc, case, waybill: str, answer: dict | None) -> list[Segment]:
    """The case's journey as reel segments, from stored evidence only: the passport's best stamp per scan, the live
    alert that named this parcel, the verified answer's tracks and clips, and the truck record. Cards where nothing
    can be seen. Labels only from labelled handshakes; outlines only from SAM tracks on that clip."""
    from spoor.contracts import ClockSync, MediaAsset, ScanEvent
    from spoor.contracts.observations import CameraCoverage, RawObservation, Track
    from spoor.forensics.journey import latest_plan
    from spoor.ingest import asset_path, load_result
    from spoor.perception.anchor import parcel_extent_px
    from spoor.perception.contours import contours_for
    from spoor.spatial.homography import site_to_image
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

    def best_view(xy, z, t):
        """The case camera with a clip at `t` that sees floor spot `xy` (at height z) closest: most pixels per metre."""
        best, scale = None, 0.0
        for cam in cams:
            m, cal = clip_at(cam, t), svc.valid_calibration(cam)
            if m is None or cal is None:
                continue
            uv, front = site_to_image(cal, [(xy[0], xy[1], z), (xy[0] + 0.5, xy[1], z), (xy[0], xy[1] + 0.5, z)])
            w, h = cal.image_wh_px
            if front.all() and 0 <= uv[0][0] < w and 0 <= uv[0][1] < h:
                k = max(float(np.hypot(*(uv[1] - uv[0]))), float(np.hypot(*(uv[2] - uv[0]))))
                if k > scale:
                    best, scale = m, k
        return best

    def carried(mid, f0, f1, xy):
        """SAM's outline of a carton carried through these frames (no scan to label it): a track on this clip that
        moves at least twice its own width inside them, never bigger than the largest parcel (PARCEL_MAX_M) standing
        at floor spot `xy` through this camera (a mask that grew onto the carrier is a person, not the carton); the
        longest such, or none."""
        m = svc.store.get(MediaAsset, mid)
        cal = svc.valid_calibration(m.camera_id) if m else None
        if cal is None:
            return "", ({}, {})
        ew, eh = parcel_extent_px(SimpleNamespace(device_parts_m=None, position_m=[xy[0], xy[1], 1.0]), cal)
        best = None
        for tr in svc.store.find(Track, media_id=mid):
            if tr.last_frame_index < f0 or tr.first_frame_index > f1:
                continue
            obs = [o for o in svc.store.find(RawObservation, track_id=tr.track_id)
                   if o.bbox_xyxy_px and f0 <= o.source_frame.frame_index <= f1]  # fmt: skip
            if len(obs) < 5:
                continue
            if np.median([o.bbox_xyxy_px[2] - o.bbox_xyxy_px[0] for o in obs]) > ew or                     np.median([o.bbox_xyxy_px[3] - o.bbox_xyxy_px[1] for o in obs]) > eh:
                continue
            obs.sort(key=lambda o: o.source_frame.frame_index)
            a, b = obs[0].bbox_xyxy_px, obs[-1].bbox_xyxy_px
            moved = np.hypot((a[0] + a[2] - b[0] - b[2]) / 2, (a[1] + a[3] - b[1] - b[3]) / 2)
            if moved >= 2 * max(a[2] - a[0], 1) and (best is None or len(obs) > best[1]):
                best = (tr.track_id, len(obs))
        return (best[0], track(mid, best[0])) if best else ("", ({}, {}))

    def clip(seg, mid, t, before=PAD, after=PAD):
        m = svc.store.get(MediaAsset, mid)
        f = svc.frame_at(mid, t.isoformat())
        seg.camera = (m.camera_id or "").removeprefix("cam_")
        seg.media_path, seg.sha256, seg.media_id = asset_path(svc.media, m), m.sha256, mid
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
    plan = latest_plan(svc.store, case.site_id)
    photo = svc.settings.data_dir / "scanner" / f"{waybill}.jpg"
    for hs in by.values():
        h = min(hs, key=rank)
        ev = svc.store.get(ScanEvent, h.scan_event_id)
        last = ev if last is None or ev.device_time_utc > last.device_time_utc else last
        title = TITLES.get(h.event_kind, h.event_kind.replace("_", " ").capitalize()).format(
            chute=(h.scan_point_id or "").rsplit("-", 1)[-1], cage=ev.container.value if ev.container else "")
        rp_ = plan.read_point(ev.station_id or ev.device_id) if plan else None
        seg = Segment(title=title, tone="scan", t=ev.device_time_utc, xy=tuple(rp_.position_for(ev.event_kind.value)) if rp_ else None)
        if h.event_kind == "tunnel_read" and photo.exists():
            seg.image, seg.label, seg.camera = photo, waybill, "Tunnel reader"
            seg.sub = "The tunnel reader's own photo" + (" · weight and size measured" if ev.dims_mm or ev.weight_g else "")
        elif not h.media_id or svc.store.get(MediaAsset, h.media_id).camera_id not in cams:
            continue
        elif h.outcome == "outlined" and h.labelled and h.track_id:
            clip(seg, h.media_id, ev.device_time_utc, after=max(PAD, h.frames_followed + 5))
            seg.contours, seg.boxes = track(h.media_id, h.track_id, upto=(h.frame_index or 0) + h.frames_followed)
            seg.label, seg.track_id = waybill, h.track_id
        else:
            # no outline: show the moment; on a clock known only to a few seconds (a handheld scanner's), the seconds
            # it may really be in, so the carry itself is on screen and not cut off (Rexton 3 Nov: the door was 3 s)
            covs = svc.store.find(CameraCoverage, media_id=h.media_id)
            unc = svc.store.get(ClockSync, covs[-1].sync_id).uncertainty_ms if covs else 0
            clip(seg, h.media_id, ev.device_time_utc, after=PAD + min(60, int(unc // 100)) if unc > 1000 else PAD)
            seg.sub = WHY.get(h.outcome, "")
        segs.append(seg)
    if last is None:
        return segs
    for seg in segs:
        seg.last_scan = seg.t == last.device_time_utc
    last_xy = next((g.xy for g in segs if g.last_scan), None)
    # after the last scan: the live alert that named only this parcel (taken out, no scan)
    where = last.container.value if last.container else "its last place"
    alert = next((a for a in sorted(svc.store.find(LiveAlert), key=lambda a: a.at_utc)
                  if len(a.candidates) == 1 and a.candidates[0]["waybill"] == waybill), None)  # fmt: skip
    if alert is not None:
        mins = round((alert.at_utc - last.device_time_utc).total_seconds() / 60)
        segs.append(Segment(title=f"Waiting in {where} for {mins} min", tone="wait", xy=last_xy,
                            t=last.device_time_utc + timedelta(seconds=1),
                            sub=f"{_hm(last.device_time_utc)} to {_hm(alert.at_utc)} · no scan, and no camera saw it move"))
        polys, boxes = track(alert.media_id, alert.track_id)
        ap_ = plan.read_point(alert.scan_point_id) if plan else None
        seg = Segment(title=f"Taken out of {where}", tone="seen", t=alert.at_utc, xy=tuple(ap_.position_m[:2]) if ap_ else last_xy,
                      sub=f"The one parcel caged in {where} and not scanned since: could be {waybill}")
        clip(seg, alert.media_id, alert.at_utc, before=alert.frame_index - min(boxes, default=alert.frame_index) + 5)
        seg.contours, seg.boxes, seg.track_id = polys, boxes, alert.track_id
        segs.append(seg)
    # the verified answer: carried to the store door on its track, into the store, out without it
    inside = next((o["inside"] for o in (answer or {}).get("objects", []) if o.get("inside")), None)
    if not inside:
        return segs
    place = inside["place"].split(" (")[0]
    o = svc.store.get(RawObservation, inside["observation_id"])
    polys, boxes = track(inside["media_id"], o.track_id)
    door_t = datetime.fromisoformat(inside["iso"]["door_at"])
    door_xy = tuple(inside["door_xy"])
    seg = Segment(title=f"Carried to the door of the {place}", tone="seen", t=door_t, xy=door_xy,
                  sub="SAM followed the carton in the carrier's hands")
    f_door = svc.frame_at(inside["media_id"], door_t.isoformat())
    clip(seg, inside["media_id"], door_t, before=f_door - min(boxes, default=f_door) + 5, after=5)
    seg.contours, seg.boxes, seg.track_id = polys, boxes, o.track_id
    segs.append(seg)
    carry_end = seg.start_utc + timedelta(seconds=seg.f1 / FPS) if seg.start_utc else door_t  # the carry plays on to here
    # the store door's own view (the case camera that sees the door closest, not the wide one that followed it)
    for key, title, tone, sub in [("carried_in_at", f"Carried into the {place}", "noscan", "Past the scan-in post, not scanned in"),
                                  ("came_out_0", "Came out without it", "seen", "SAM tracked no carton with the person coming out")]:
        if key in inside["iso"]:
            t = datetime.fromisoformat(inside["iso"][key])
            m = best_view(inside["door_xy"], 1.0, t)
            if m is not None and m.media_id != inside["media_id"]:
                # the carry into the store is ONE moment seen from two angles: the door camera picks up where the wide
                # one stopped (Rexton 3 Nov: it replayed the last two seconds), so its clip starts at carry_end
                before = max(5, round((t - carry_end).total_seconds() * FPS)) if key == "carried_in_at" else 25
                seg = clip(Segment(title=title, tone=tone, t=t, sub=sub, xy=door_xy), m.media_id, t, before=before, after=25)
                if key == "carried_in_at":  # the carton in the carrier's hands; coming out there is none to outline
                    seg.track_id, (seg.contours, seg.boxes) = carried(m.media_id, seg.f0, seg.f1, inside["door_xy"])
                segs.append(seg)
    # the record that says it left, made while the cameras show it still inside
    until = datetime.fromisoformat(inside["iso"]["until"])
    rec = next((s for s in sorted(svc.store.find(ScanEvent, event_kind="container_loaded"), key=lambda s: s.device_time_utc)
                if any(i.value == where for i in [*s.identifiers, *([s.container] if s.container else [])])
                and door_t < s.device_time_utc < until), None)  # fmt: skip
    rp = plan.read_point(rec.station_id or rec.device_id) if rec is not None and plan else None
    m = best_view(rp.position_m[:2], 1.0, rec.device_time_utc) if rp is not None else None
    if rec is not None and m is not None:
        door = next((p for p in (rec.station_id or "").split("-") if p.startswith("D")), "")
        segs.append(clip(Segment(title=f"Record says {where} loaded on {door}".strip(), tone="record",
                                 t=rec.device_time_utc, sub=LOAD_HOW.get(rec.device_kind, LOAD_HOW[None]), xy=tuple(rp.position_m[:2])),
                         m.media_id, rec.device_time_utc, before=30, after=30))  # fmt: skip
    segs.append(Segment(title=f"Most likely in the {inside['place']}", tone="card", t=until, xy=tuple(inside["area_xy"]),
                        sub=f"Carried in at {inside['carried_in_at']} · not seen coming out", seconds=3.0))
    return segs
