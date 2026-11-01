"""Site clock calibration: the sorter's WCS clock is the reference; every camera recorder is fitted to it from events
both record, never trusted from its on-screen clock or the upload form.

1. WCS is declared the reference (the hub's time master: the timeline IS its clock).
2. A camera that sees sorter scan points (plan visible_by: the tunnel exit, the induct, chute mouths): SAM follows the
   parcels in its clip; each one's closest pass to an event's pixel (the event's floor position at its height,
   through the camera's calibrated pose) is that event on the camera's own clock. Each WCS event in the clip is paired
   with the passage nearest to it after the camera's overall offset (the most common difference); the backend's
   robust fit drops mismatched pairs and re-registers the camera's clips on the fitted clock.
3. A camera without enough sorter events (CAM_19: two RFID reads) is aligned to an already fitted camera whose view
   overlaps it, from MOVING people both see: the shift that makes their velocity profiles agree (positions would carry
   the hidden-legs bias of a far, high camera; velocity does not), and a standing or steady walker is skipped. A likely carrier of any case's carton is left out, so a case's evidence never sets
   the clocks it is judged by; the script prints how much including them would change the fit.

  cd backend; DATA_DIR=... USERS_FILE=... URL_SIGNING_SECRET=... uv run python ../frontend/scripts/fit_camera_clocks.py
"""
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import numpy as np

from spoor.api.services import Services
from spoor.config import Settings
from spoor.contracts import (
    Camera,
    CameraCoverage,
    ClockDomain,
    ClockSync,
    MediaAsset,
    RawObservation,
    ScanEvent,
    Track,
    TrackAssociation,
)
from spoor.forensics.handover import carrier_fit, floor_path
from spoor.forensics.journey import latest_plan
from spoor.spatial.homography import image_to_site, site_to_image

FRONT = Path(__file__).resolve().parents[1]
SITE, REF = "site_contoh_hub", "clkd_wcs"
NEAR_PX = 45  # a parcel passes an event's pixel if its box centre comes this close (1920 px frame) ...
NEAR_M = 0.45  # ... or this close on the floor, whichever is more pixels (a close-up camera at 400-500 px/m: 45 px
# was 10 cm, so no passage ever paired: six checkpoints CHK_TUNNEL)
PAIR_S = 1.0  # an event and a passage pair if within this of the camera's overall offset
SEARCH_S = 10.0  # cameras may be this far off the reference
MIN_MOVE_M = 2.0  # a person must cover this much floor to carry timing information
MEET_MPS = 0.3  # two cameras' velocity profiles of one person agree within this at the right shift (m/s)
CONTRAST_MPS = 0.05  # ... and the right shift beats shifts 1 s off by at least this
MIN_SHARED = 50  # at least 5 s of shared movement (short, far figures agree by chance)
FALLBACK_NEAR_M = 12.0  # positions only when both cameras are this close to the walk (far, high views hide legs)
SAME_PLACE_M = 2.5  # at the chosen shift the two cameras must place them this close (allows the hidden-legs bias)
DEBUG = bool(__import__("os").environ.get("SPOOR_DEBUG"))
REFIT = set(filter(None, __import__("os").environ.get("SPOOR_REFIT", "").split(",")))  # cameras to fit again
# camera -> fitted camera whose view overlaps it, in order (a chain: CAM_13 from CAM_11's bagging area, then CAM_19)
OVERLAP = [("cam_CAM_13", "cam_CAM_11"), ("cam_CAM_19", "cam_CAM_13"),
           ("cam_CHK_CAGE_W", "cam_CAM_13"), ("cam_CHK_DOCK", "cam_CAM_19")]  # checkpoint cameras (six checkpoints)
CAMERAS = ("cam_CAM_04", "cam_CAM_05", "cam_CAM_09", "cam_CAM_10", "cam_CAM_11", "cam_CAM_13",  # S2's trail + sorter
           "cam_CAM_01", "cam_CHK_TUNNEL")  # + the W1 tunnel / carrier cameras (six checkpoints)

env = {k.strip(): v.strip() for k, v in (line.split("=", 1) for line in (FRONT / ".env.local").read_text(encoding="utf-8")
                                         .splitlines() if "=" in line and not line.startswith("#"))}
api = httpx.Client(base_url="http://127.0.0.1:8000", headers={"Authorization": f"Bearer {env['SPOOR_TOKEN_SITE_ADMIN']}"},
                   timeout=120)
svc = Services.from_settings(Settings())
plan = latest_plan(svc.store, SITE)
ref_id = next(d.clock_domain_id for d in svc.store.find(ClockDomain, site_id=SITE) if d.name == REF)
if not any(s.method == "reference clock of the timeline" for s in svc.store.find(ClockSync, clock_domain_id=ref_id)):
    r = api.post(f"/v1/clock-domains/{ref_id}/reference", json={"uncertainty_ms": 0,
                 "description": "the sorter's WCS / PLC clock is the hub's time master; the timeline is this clock"})
    print("reference:", r.status_code, REF)


def original(cam: str) -> MediaAsset:
    """The camera's valid clip with the most sorter scans in its span (a camera may hold several windows; purged
    uploads never count); ties: the longer clip."""
    ms = [m for m in svc.store.find(MediaAsset, camera_id=cam) if m.kind.value == "original" and not svc.store.is_invalid(m.media_id)]
    wcs = [s.device_time_utc for s in svc.store.find(ScanEvent, site_id=SITE) if s.clock_domain_id == ref_id]

    def score(m):
        c = svc.store.find(CameraCoverage, media_id=m.media_id)
        if not c:
            return (0, 0.0)
        return (sum(c[-1].start_utc <= t <= c[-1].end_utc for t in wcs), (c[-1].end_utc - c[-1].start_utc).total_seconds())
    return max(ms, key=score)


def cam_time(o: RawObservation) -> datetime:
    return o.source_frame.camera_clock_utc


def fit(cam: str, anchors: list[dict], how: str, base_ms: float = 100.0) -> dict | None:
    if len(anchors) < 3:
        print(f"  {cam}: only {len(anchors)} anchors, not fitted")
        return None
    res = api.post(f"/v1/cameras/{cam}/clock-fit", json={"anchors": anchors, "base_uncertainty_ms": base_ms,
                                                          "description": how})
    body = res.json()
    if res.status_code != 201:
        print(f"  {cam}: {res.status_code} {json.dumps(body)[:200]}")
        return None
    s = body["sync"]
    print(f"  {cam}: offset {s['offset_ms']:+.0f} ms, drift {s['drift_ppm']:+.0f} ppm, ± {s['uncertainty_ms']:.0f} ms "
          f"({body['n_used']} used, {body['n_rejected']} rejected)")
    return s


def by_sorter_events(cam: str) -> dict | None:
    cal = svc.valid_calibration(cam)
    points = {rp.scan_point_id: rp for rp in plan.read_points if cam in rp.visible_by and rp.device_kind != "handheld"}
    media = original(cam)
    cov = svc.store.find(CameraCoverage, media_id=media.media_id)[-1]
    lo, hi = cov.start_utc - timedelta(seconds=SEARCH_S), cov.end_utc + timedelta(seconds=SEARCH_S)
    events = [s for s in svc.store.find(ScanEvent, site_id=SITE)
              if (s.station_id or s.device_id) in points and s.clock_domain_id == ref_id and lo <= s.device_time_utc <= hi]
    if len(events) < 3 or cal is None:
        print(f"  {cam}: {len(events)} sorter events in view, skipped")
        return None
    r = svc.run_perception(media.media_id, concept="box")
    tracks = {}
    for o in r.observations:
        tracks.setdefault(o.track_id, []).append(o)
    passes = []  # (event point id, camera-clock time, observation id)
    for sid, rp in points.items():
        kinds = {e.event_kind.value for e in events if (e.station_id or e.device_id) == sid}
        for kind in kinds:
            x, y = rp.position_for(kind)
            uv, front = site_to_image(cal, [[x, y, rp.position_m[2]], [x + NEAR_M, y, rp.position_m[2]],
                                            [x, y + NEAR_M, rp.position_m[2]]])
            if not front[0]:
                continue
            near_px = max(NEAR_PX, float(min(np.linalg.norm(uv[1] - uv[0]), np.linalg.norm(uv[2] - uv[0]))))
            for obs in tracks.values():
                c = np.array([((o.bbox_xyxy_px[0] + o.bbox_xyxy_px[2]) / 2, (o.bbox_xyxy_px[1] + o.bbox_xyxy_px[3]) / 2) for o in obs])
                d = np.linalg.norm(c - uv[0], axis=1)
                i = int(np.argmin(d))
                if d[i] <= near_px:
                    passes.append((sid, kind, cam_time(obs[i]), obs[i].observation_id))
    diffs = [round((e.device_time_utc - t).total_seconds() * 5) / 5 for e in events for sid, k, t, _ in passes
             if sid == (e.station_id or e.device_id) and k == e.event_kind.value
             and abs((e.device_time_utc - t).total_seconds()) <= SEARCH_S]
    if not diffs:
        print(f"  {cam}: no event/passage pairs ({len(events)} events, {len(tracks)} tracks, {len(passes)} passages, "
              f"clip {media.media_id} {cov.start_utc.isoformat()[11:19]}-{cov.end_utc.isoformat()[11:19]})")
        return None
    off = Counter(diffs).most_common(1)[0][0]
    anchors = []
    for e in events:
        cands = [(abs((e.device_time_utc - t).total_seconds() - off), t, oid) for sid, k, t, oid in passes
                 if sid == (e.station_id or e.device_id) and k == e.event_kind.value]
        if cands and min(cands)[0] <= PAIR_S:
            _, t, oid = min(cands)
            anchors.append({"device_time": t.isoformat(), "reference_time": e.device_time_utc.isoformat(),
                            "anchor_id": f"{e.scan_event_id}~{oid}"})
    print(f"  {cam}: {len(events)} sorter events, {len(passes)} passages, offset guess {off:+.1f} s, {len(anchors)} anchors")
    return fit(cam, anchors, f"WCS events at {', '.join(sorted({e.station_id or e.device_id for e in events}))} paired "
                             f"with SAM-tracked parcel passages on {cam}")


def case_carriers(paths: dict) -> set[str]:
    """Person tracks that are a likely carrier of any carton linked to a case: left out of clock calibration, so the
    case's own evidence never sets the clocks it is judged by."""
    linked = {a.track_id for a in svc.store.find(TrackAssociation) if a.status.value in ("verified_same_camera",
                                                                                         "human_confirmed")}
    out = set()
    for tid in linked:
        t = svc.store.get(Track, tid)
        cal = svc.valid_calibration(t.camera_id)
        if cal is None:
            continue
        carton = floor_path(svc.store, tid, cal, carried=True)
        for cam, items in paths.items():
            for pid, _dev, _xy in items:
                if carrier_fit(carton, floor_path(svc.store, pid, svc.valid_calibration(cam), carried=False)).verdict                         == "likely carrier":  # fmt: skip
                    out.add(pid)
    return out


def velocity(t: np.ndarray, xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Smoothed floor velocity over time. A constant position bias (legs hidden behind cages pushes a person's floor
    point along their path) shifts WHERE they appear, not WHEN they speed up, slow down or turn: velocity carries the
    timing and is blind to the bias."""
    k = np.ones(7) / 7
    sx = np.c_[np.convolve(xy[:, 0], k, "same"), np.convolve(xy[:, 1], k, "same")][3:-3]
    st = t[3:-3]
    return st[3:-3], (sx[6:] - sx[:-6]) / (st[6:] - st[:-6])[:, None]


def best_shift(dev, xy, rt, rxy):
    """(median velocity difference m/s, shift s, samples, contrast m/s): the shift that makes two cameras' velocity
    profiles of one person agree, and how much worse shifts 1 s either side are (a steady walk or a standing person
    looks the same at every shift: no timing information)."""
    ta, va = velocity(dev, xy)
    tb, vb = velocity(rt, rxy)

    def at(shift):
        d = [float(np.linalg.norm(va[i] - vb[j])) for i in range(len(ta)) for j in [int(np.argmin(np.abs(tb - ta[i] - shift)))]
             if abs(tb[j] - ta[i] - shift) <= 0.06 and np.isfinite(va[i]).all() and np.isfinite(vb[j]).all()]
        return (float(np.median(d)), len(d)) if len(d) >= 20 else (np.inf, 0)
    grid = [(at(sh), sh) for sh in np.arange(-SEARCH_S, SEARCH_S, 0.05)]
    (med, n), shift = min(grid, key=lambda g: g[0][0])
    if not np.isfinite(med):
        return None
    side = min(at(shift - 1.0)[0], at(shift + 1.0)[0])
    return med, float(shift), n, side - med


def position_shift(dev, xy, rt, rxy):
    """Fallback when a walk is too steady for velocity to carry timing: the shift that brings two floor paths together
    (only sound where neither camera hides the legs: a constant bias along the path would become a time error)."""
    def at(shift):
        ds = [float(np.linalg.norm(xy[i] - rxy[j])) for i in range(0, len(dev), 3) for j in [int(np.argmin(np.abs(rt - dev[i] - shift)))]
              if abs(rt[j] - dev[i] - shift) <= 0.15 and np.isfinite(xy[i]).all() and np.isfinite(rxy[j]).all()]
        return (float(np.median(ds)), len(ds)) if len(ds) >= 10 else (np.inf, 0)
    grid = [(at(sh), sh) for sh in np.arange(-SEARCH_S, SEARCH_S, 0.05)]
    (med, n), shift = min(grid, key=lambda g: g[0][0])
    if not np.isfinite(med):
        return None
    return med, float(shift), n, min(at(shift - 2.0)[0], at(shift + 2.0)[0]) - med


def by_overlap(cam: str, ref_cam: str, ref_sync: dict) -> dict | None:
    """Moving people both cameras see: the shift that makes their movements agree, against the fitted camera."""
    paths = {}
    for c in (cam, ref_cam):
        k = svc.valid_calibration(c)
        r = svc.run_perception(original(c).media_id, concept="person")
        paths[c] = []
        for t in r.tracks:
            obs = sorted((o for o in r.observations if o.track_id == t.track_id), key=lambda o: o.source_frame.frame_index)
            b = np.array([o.bbox_xyxy_px for o in obs], float)
            xy = image_to_site(k, np.c_[(b[:, 0] + b[:, 2]) / 2, b[:, 3]], 0.0)[:, :2]
            ok = np.isfinite(xy).all(axis=1)
            if ok.sum() < 10 or np.linalg.norm(np.ptp(xy[ok], axis=0)) < MIN_MOVE_M:
                continue  # standing still: no timing information
            paths[c].append((t.track_id, np.array([cam_time(o).timestamp() for o in obs]), xy))
    carriers = case_carriers(paths)
    cam_xy = {c: np.asarray(svc.store.get(Camera, c).position_m[:2], float) for c in (cam, ref_cam)}
    shift_ref = ref_sync["offset_ms"] / 1000
    anchors, held_out = [], []
    for tid, dev, xy in paths[cam]:
        for rid, rdev, rxy in paths[ref_cam]:
            b = best_shift(dev, xy, rdev + shift_ref, rxy)
            how = "movements agree"
            near = max(float(np.linalg.norm(np.nanmedian(xy, axis=0) - cam_xy[cam])),
                       float(np.linalg.norm(np.nanmedian(rxy, axis=0) - cam_xy[ref_cam])))
            if (not b or b[3] < CONTRAST_MPS) and near <= FALLBACK_NEAR_M:  # too steady for velocity: positions
                p = position_shift(dev, xy, rdev + shift_ref, rxy)
                if p and p[0] <= 0.8 and p[3] >= 0.5 and p[2] >= MIN_SHARED // 3:
                    b, how = (0.0, p[1], MIN_SHARED, CONTRAST_MPS), f"paths meet ({p[0]:.2f} m apart, {p[3]:.1f} m better than 2 s off)"
            if DEBUG:
                print("      pair", tid[-6:], rid[-6:], b)
            if not b or b[0] > MEET_MPS or b[3] < CONTRAST_MPS or b[2] < MIN_SHARED:
                continue
            gap = [float(np.linalg.norm(xy[i] - rxy[j])) for i in range(0, len(dev), 3)
                   for j in [int(np.argmin(np.abs(rdev + shift_ref - dev[i] - b[1])))]
                   if abs(rdev[j] + shift_ref - dev[i] - b[1]) <= 0.15 and np.isfinite(xy[i]).all() and np.isfinite(rxy[j]).all()]
            if not gap or np.median(gap) > SAME_PLACE_M:
                continue  # same movement, different places: two different people
            excluded = tid in carriers or rid in carriers
            detail = how if how != "movements agree" else (f"movements agree ({b[0]:.2f} m/s apart, {b[2]} samples, "
                                                           f"{b[3]:.2f} m/s better than 1 s off)")
            print(f"    {tid[-6:]} ~ {rid[-6:]}: shift {b[1]:+.2f} s, {detail}{' - case carrier, left out' if excluded else ''}")
            rows = [{"device_time": datetime.fromtimestamp(dev[i], UTC).isoformat(),
                     "reference_time": datetime.fromtimestamp(dev[i] + b[1], UTC).isoformat(),
                     "anchor_id": f"{tid}~{rid}@{i}"} for i in range(0, len(dev), 10)]
            (held_out if excluded else anchors).extend(rows)
    if held_out and anchors:
        off = lambda a: np.median([(datetime.fromisoformat(x["reference_time"]) - datetime.fromisoformat(x["device_time"]))
                                   .total_seconds() for x in a])
        print(f"    robustness: with the case carrier included the offset would be {off(anchors + held_out) * 1000:+.0f} ms "
              f"instead of {off(anchors) * 1000:+.0f} ms")
    # time step 50 ms + the reference camera's own fit + the spread between body points (feet / head / middle)
    return fit(cam, anchors, f"movement (velocity) of people seen by both {cam} and {ref_cam} (fitted); case carriers "
                             "left out", base_ms=200.0)


fitted = {}  # cameras already fitted in an earlier run keep their fit
for cam in dict.fromkeys((*CAMERAS, *(c for c, _ in OVERLAP))):
    done = [s for s in svc.store.find(ClockSync, camera_id=cam) if s.method == "fitted_from_anchor_events"]
    if done and cam not in REFIT:
        fitted[cam] = done[-1].model_dump(mode="json")
        print(f"{cam}: already fitted ({done[-1].offset_ms:+.0f} ms ± {done[-1].uncertainty_ms:.0f} ms)")
for cam in CAMERAS:
    if cam in fitted:
        continue
    if svc.valid_calibration(cam) is None:
        continue
    print(cam)
    s = by_sorter_events(cam)
    if s:
        fitted[cam] = s
for cam, ref_cam in OVERLAP:
    if cam not in fitted and ref_cam in fitted:
        print(cam, "via", ref_cam)
        s = by_overlap(cam, ref_cam, fitted[ref_cam])
        if s:
            fitted[cam] = s
print("fitted:", sorted(fitted))
