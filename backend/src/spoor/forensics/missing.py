"""The missing moment (QUEUE I3 / H10): where the chain of evidence stops, and what should have come next.

From the last confirmed point (a scan or an observation) this lists, per camera, when and where the subject should
have appeared next — along the belt at belt speed, or on foot at walking speed — with the clock tolerance applied, the
expected region in that camera's image, and the result:
  seen          the subject is confirmed on that camera in the window;
  not_seen      that footage was analysed, nothing was tracked where the subject should be, and the subject was not
                confirmed: a typed NEGATIVE observation with the frames it covers (negative evidence made visible);
  unresolved_candidates  something was tracked where it should be but no track is linked to the subject: no
                negative evidence until an identity decision is made;
  not_analysed  footage exists but nothing was run on it (no-key mode: tracking needs SAM);
  no_footage    the camera recorded nothing for this window.
Predictions are computed from the site plan; they are never observations."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from spoor.contracts import Camera, CameraCoverage, Case, ObjectInstance, PlanCamera, RawObservation, SitePlan
from spoor.store import EvidenceStore, ObjectView, epoch_ms

from .conveyance import ConveyorNet
from .floorgrid import FloorGrid, footprint_mask, grid_for
from .journey import build_journey, iso, latest_plan
from .viewgeom import expected_region

BELT_HORIZON_S = 60.0
# The sorter discharged the carrier: the parcel left timed conveyance into a chute (gravity, no stated speed).
LEAVES_BELT = frozenset({"divert_confirmed", "exception_diverted"})
ON_FOOT_CAMERAS = 3
FrameLookup = Callable[[str, float], dict | None]  # (camera_id, t_ms) -> frame ref (media_id, frame_index, url…)


@dataclass
class CameraContext:
    camera: Camera
    pose: PlanCamera | None
    footprint: np.ndarray
    coverage: list[CameraCoverage]

    def covering(self, t_ms: float) -> CameraCoverage | None:
        return next((c for c in reversed(self.coverage) if epoch_ms(c.start_utc) <= t_ms <= epoch_ms(c.end_utc)), None)


def camera_contexts(store: EvidenceStore, site_id: str, plan: SitePlan, grid: FloorGrid) -> dict[str, CameraContext]:
    poses = {c.camera_id: c for c in plan.cameras}
    out = {}
    for cam in store.find(Camera, site_id=site_id):
        covs = [c for c in store.find(CameraCoverage, camera_id=cam.camera_id) if not store.is_invalid(c.coverage_id)]
        out[cam.camera_id] = CameraContext(cam, poses.get(cam.camera_id), footprint_mask(grid, cam.fov_polygon_m),
                                           covs)  # fmt: skip
    return out


def analysed(store: EvidenceStore, media_id: str) -> bool:
    """True when a perception run produced anything on this clip (so absence of the subject means something)."""
    return bool(store.find(RawObservation, media_id=media_id))


def missing_moment(store: EvidenceStore, case_id: str, *, frame_lookup: FrameLookup | None = None) -> dict:
    case = store.get(Case, case_id)
    plan = latest_plan(store, case.site_id)
    journey = build_journey(store, case_id, plan=plan)
    out = []
    for obj, oj in zip(store.find(ObjectInstance, case_id=case_id), journey["objects"], strict=True):
        out.append(_for_object(store, case, obj, oj, plan, frame_lookup))
    return {"case_id": case_id, "plan_id": plan.plan_id if plan else None, "objects": out,
            "needs": journey["needs"], "label": "predicted from the site plan; not an observation"}  # fmt: skip


def _for_object(store, case, obj, oj, plan, frame_lookup) -> dict:
    last = oj["last_confirmed"]
    if last is None:
        return {"object_instance_id": obj.object_instance_id, "last_confirmed": None, "expected_next": [],
                "note": "nothing confirmed yet: no scan and no confirmed track"}  # fmt: skip
    t0 = _ms(last["t"])
    base = {"object_instance_id": obj.object_instance_id, "label": obj.label, "last_confirmed": dict(last)}
    if plan is None or last["xy"] is None:
        return {**base, "expected_next": [], "note": "the last confirmed point has no floor position in the plan"}
    grid, net = grid_for(plan), ConveyorNet(plan)
    ctx = camera_contexts(store, case.site_id, plan, grid)
    xy = tuple(last["xy"])
    seen_on = _confirmed_after(store, obj.object_instance_id, t0)
    tol_ms = _clock_tol_ms(store, last)
    base["last_confirmed"]["frames"] = _last_frames(last, plan, ctx, grid, t0, frame_lookup)
    rows: dict[str, dict] = {}

    rp_cams = _watching(plan, last, ctx, grid)
    for cid in rp_cams:
        rows[cid] = _row(ctx[cid], "watching_last_point", t0, t0 + 2000 + tol_ms, t0, (*xy, _height(net, last)),
                         "in view where it was last confirmed", tol_ms)  # fmt: skip

    if last["on_conveyor"] and last.get("event_kind") not in LEAVES_BELT:
        snap = net.snap(xy)
        samples = net.downstream_timed(snap[:2], BELT_HORIZON_S) if snap else []
        for cid, c in ctx.items():
            if cid in rows:
                continue
            inside = [(dt, p, conv) for dt, p, conv in samples if c.footprint[grid.cell(p)]]
            if inside:
                dt, p, conv = inside[0]
                z = net.lines[conv].height(net.lines[conv].project(p)[0])
                rows[cid] = _row(c, "belt_next", t0 + dt * 1000 - tol_ms, t0 + inside[-1][0] * 1000 + tol_ms,
                                 t0 + dt * 1000, (*p, z), f"on {conv} at belt speed: {dt:.1f} s after", tol_ms)

    dist = grid.distance_from(xy)
    on_foot = []
    for cid, c in ctx.items():
        if cid in rows:
            continue
        cells = c.footprint & np.isfinite(dist)
        if not cells.any():
            continue
        d = float(dist[cells].min())
        r, cc = np.unravel_index(np.where(cells, dist, np.inf).argmin(), dist.shape)
        on_foot.append((d, cid, grid.xy(int(r), int(cc))))
    for d, cid, p in sorted(on_foot)[:ON_FOOT_CAMERAS]:
        c = ctx[cid]
        cov_end = max((epoch_ms(x.end_utc) for x in c.coverage), default=t0 + d / plan.walk_speed_mps * 1000)
        rows[cid] = _row(c, "on_foot_next", t0 + d / plan.walk_speed_max_mps * 1000 - tol_ms, max(cov_end, t0),
                         t0 + d / plan.walk_speed_mps * 1000, (*p, 0.9),
                         f"{d:.0f} m on foot: {d / plan.walk_speed_max_mps:.0f}-{d / plan.walk_speed_mps:.0f} s",
                         tol_ms)  # fmt: skip

    for cid, row in rows.items():
        _resolve(store, row, ctx[cid], seen_on.get(cid), frame_lookup)
    ordered = sorted(rows.values(), key=lambda r: (r["role"] != "watching_last_point", r["predicted_t"]))
    return {**base, "expected_next": ordered, "clock_tolerance_ms": tol_ms}


def _ms(t: str) -> float:
    return datetime.fromisoformat(t).timestamp() * 1000


def _height(net: ConveyorNet, last: dict) -> float:
    if last.get("on_conveyor"):
        line = net.lines[last["on_conveyor"]]
        return line.height(line.project(tuple(last["xy"]))[0])
    return 0.9


def _clock_tol_ms(store: EvidenceStore, last: dict) -> float:
    """Tolerance on the predicted times: the last point's clock uncertainty (unsynchronized scans: 1 s floor)."""
    if last["kind"] == "observation":
        o = store.get(RawObservation, last["evidence_id"])
        return float(o.source_frame.time_uncertainty_ms or 0) if o.source_frame else 1000.0
    return 1000.0


def _watching(plan: SitePlan, last: dict, ctx, grid: FloorGrid) -> list[str]:
    """Cameras that watch the last confirmed point: the plan's visibility check for a read point when it has one,
    else every camera whose footprint contains the point. Empty for an observation (that camera IS the sighting)."""
    if last["kind"] == "observation":
        return []
    rp = plan.read_point(last.get("station_id"))
    if rp and rp.visible_by:
        return [c for c in rp.visible_by if c in ctx][:4]
    cell = grid.cell(tuple(last["xy"]))
    return [cid for cid, c in ctx.items() if c.footprint[cell]][:4]


def _row(c: CameraContext, role: str, w0: float, w1: float, t_pred: float, xyz, how: str, tol_ms: float) -> dict:
    region = expected_region(c.pose, xyz) if c.pose else None
    return {"camera_id": c.camera.camera_id, "camera_name": c.camera.name, "role": role,
            "window": {"start": iso(w0), "end": iso(max(w0, w1))}, "predicted_t": iso(t_pred), "how": how,
            "expected_xy": [round(xyz[0], 2), round(xyz[1], 2)], "expected_region_px": region,
            "region_basis_wh_px": list(c.pose.resolution_wh_px) if c.pose else None,
            "region_note": "approximate: mounting-plan pose, no lens model" if region else
                           "point not in this camera's image by the mounting-plan pose",
            "clock_tolerance_ms": tol_ms}  # fmt: skip


def _confirmed_after(store: EvidenceStore, object_instance_id: str, t0: float) -> dict[str, list[str]]:
    seen: dict[str, list[str]] = {}
    for t in ObjectView.load(store, object_instance_id).evidence.timed:
        if t.t_ms > t0 + 1 and t.obs.camera_id:
            seen.setdefault(t.obs.camera_id, []).append(t.obs.observation_id)
    return seen


def _resolve(store, row: dict, c: CameraContext, seen: list[str] | None, frame_lookup) -> None:
    t_pred = _ms(row["predicted_t"])
    w0, w1 = _ms(row["window"]["start"]), _ms(row["window"]["end"])
    cov = c.covering(min(max(t_pred, w0), w1)) or next(
        (x for x in c.coverage if epoch_ms(x.start_utc) <= w1 and epoch_ms(x.end_utc) >= w0), None)
    row["frame"] = frame_lookup(c.camera.camera_id, t_pred) if (frame_lookup and cov) else None
    if cov is None:
        row["result"] = "no_footage"
        return
    row["media_id"] = cov.media_id
    if seen:
        row["result"], row["evidence_ids"] = "seen", seen
        return
    if not analysed(store, cov.media_id):
        row["result"] = "not_analysed"
        row["needs"] = "object tracking on this clip (SAM 3.1 via MODEL_API_KEY)"
        return
    lo, hi = max(w0, epoch_ms(cov.start_utc)), min(w1, epoch_ms(cov.end_utc))
    cands = _candidates(store, cov.media_id, lo, hi, row.get("expected_region_px"))
    if cands:
        # Something was tracked where the subject should be, but no track is linked to it: absence is NOT shown.
        row["result"], row["candidate_track_ids"] = "unresolved_candidates", cands
        row["needs"] = "an identity decision on these tracks (scan-anchored link or human review)"
        return
    frames = []
    if frame_lookup:
        t = lo
        while t <= hi and len(frames) < 30:
            f = frame_lookup(c.camera.camera_id, t)
            if f and (not frames or f["frame_index"] != frames[-1]):
                frames.append(f["frame_index"])
            t += 1000
    row["result"] = "not_seen"
    row["negative_observation"] = {
        "kind": "negative_observation", "camera_id": c.camera.camera_id, "media_id": cov.media_id,
        "coverage_id": cov.coverage_id, "window": {"start": iso(lo), "end": iso(hi)}, "frame_indices": frames,
        "basis": "footage analysed for this case; the subject was not confirmed in this window",
        "evidence_ids": [cov.media_id, cov.coverage_id]}  # fmt: skip


def _candidates(store, media_id: str, lo: float, hi: float, region: list[float] | None) -> list[str]:
    """Tracks on this clip in the window that could be the subject: overlapping the expected region (any track at all
    when no region is known). Their presence blocks a negative observation."""
    out, invalid = [], store.invalid_ids()
    for o in store.find(RawObservation, media_id=media_id):
        if o.observation_id in invalid or o.track_id in invalid:
            continue
        f = o.source_frame
        t = epoch_ms(f.normalized_utc) if f and f.normalized_utc else None
        if t is None or not lo <= t <= hi or not o.track_id or o.track_id in out:
            continue
        b = o.bbox_xyxy_px
        if region is None or b is None or (b[0] < region[2] and b[2] > region[0] and b[1] < region[3] and b[3] > region[1]):
            out.append(o.track_id)
    return out


def _last_frames(last: dict, plan: SitePlan, ctx, grid: FloorGrid, t0: float, frame_lookup) -> list[dict]:
    """Frames at the moment of the last confirmation: the observation's own frame, or (for a scan) context frames
    from cameras that watch the read point — context only, not an observation of the parcel."""
    if not frame_lookup:
        return []
    if last["kind"] == "observation" and last.get("camera_id"):
        f = frame_lookup(last["camera_id"], t0)
        return [{**f, "role": "last_sighting"}] if f else []
    return [{**f, "role": "context_at_scan_time"} for cid in _watching(plan, last, ctx, grid)
            if (f := frame_lookup(cid, t0))]
