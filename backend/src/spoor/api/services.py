"""Service wiring: storage, provider clients, and the paid tools agents may call (PRD §24 modular monolith)."""

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

from spoor.agents import ToolContext
from spoor.config import Settings
from spoor.contracts import (
    AssociationStatus,
    Camera,
    CameraCoverage,
    Case,
    CaseRevision,
    ClockSync,
    EvidenceScope,
    FloorCalibration,
    MediaAsset,
    MediaAuthorization,
    ObjectInstance,
    RawObservation,
    RigState,
    Site,
    TimeWindow,
)
from spoor.forensics.journey import latest_plan
from spoor.ingest import MediaStore, asset_path, load_result
from spoor.ingest.clips import crop_window
from spoor.perception import MetaSamBackend, PerceptionRequest, SamBackend, track_target
from spoor.perception.anchor import (
    AnchorError,
    anchor_for,
    expected_carton_px,
    handled,
    inside,
    leaves,
    parcel_extent_px,
)
from spoor.perception.prompts import InstancePrompt
from spoor.reasoning import (
    BasetenChatBackend,
    JsonBackend,
    MetaResponsesBackend,
    ask_clip,
    cut_clip,
    ground_facts,
    uploaded,
)
from spoor.store import EvidenceStore
from spoor.verification import Verifier

from .auth import RateLimiter, TokenRegistry, UrlSigner
from .jobs import JobRunner


class ServiceError(ValueError):
    pass


GRANT_REASON = "scope: cameras granted"
DIVERT_EVENTS = {"divert_confirmed", "recirculated"}
BOARD_EVENTS = {"inducted"}  # reported where the parcel boards the loop (the plan's event_positions)
RIDE_M = 1.0  # boarding: the outline rides at least this far along the loop in ~1.5 s (the loop runs ~2 m/s)
CARTON_X = 2.5  # an outline more than this many times the parcel's own projected area is not that parcel


def _area(b) -> float:
    return max(0.0, (b[2] - b[0]) * (b[3] - b[1]))  # sorter events at a chute mouth, where the motion rule holds


@dataclass
class Services:
    settings: Settings
    store: EvidenceStore
    media: MediaStore
    jobs: JobRunner
    tokens: TokenRegistry
    signer: UrlSigner
    limiter: RateLimiter
    sam: SamBackend | None = None
    spark: JsonBackend | None = None  # Meta Muse Spark (video-capable)
    spark_client: Any = None  # sync OpenAI client for Files API uploads
    agent: JsonBackend | None = None  # Evidence/Hypothesis agents
    voice: Any = None  # Muse Voice Transcribe (spoor.voice.Transcriber), J4
    _case_locks: dict[str, threading.Lock] = field(default_factory=dict)
    _locks_guard: threading.Lock = field(default_factory=threading.Lock)
    _sam_loop: Any = None

    def _on_sam_loop(self, coro):
        """Run a SAM coroutine on one long-lived loop. The async HTTP client pools connections bound to the loop that
        opened them, so a fresh asyncio.run per call failed every other call with "Event loop is closed"."""
        with self._locks_guard:
            if self._sam_loop is None:
                self._sam_loop = asyncio.new_event_loop()
                threading.Thread(target=self._sam_loop.run_forever, name="sam-loop", daemon=True).start()
        return asyncio.run_coroutine_threadsafe(coro, self._sam_loop).result()

    def case_lock(self, case_id: str) -> threading.Lock:
        """One investigation per case at a time (concurrent runs would race on the case revision)."""
        with self._locks_guard:
            return self._case_locks.setdefault(case_id, threading.Lock())

    @classmethod
    def from_settings(cls, s: Settings) -> "Services":
        s.data_dir.mkdir(parents=True, exist_ok=True)
        store = EvidenceStore(s.database_url) if s.database_url else EvidenceStore.sqlite_file(s.data_dir / "spoor.db")
        tokens = TokenRegistry.from_file(s.users_file) if s.users_file else TokenRegistry({})
        secret = s.url_signing_secret.get_secret_value().encode() if s.url_signing_secret else None
        svc = cls(s, store, MediaStore(s.data_dir / "media"), JobRunner(), tokens, UrlSigner(secret,
                  s.signed_url_ttl_s), RateLimiter(s.rate_limit_per_minute))  # fmt: skip
        if s.model_api_key is not None:
            from openai import AsyncOpenAI, OpenAI

            key = s.model_api_key.get_secret_value()
            svc.sam = MetaSamBackend(AsyncOpenAI(api_key=key, base_url=s.meta_base_url), s.sam_model)
            svc.spark_client = OpenAI(api_key=key, base_url=s.meta_base_url)
            svc.spark = MetaResponsesBackend(svc.spark_client, s.spark_model)
            from spoor.voice import MetaVoiceTranscriber

            svc.voice = MetaVoiceTranscriber(key, s.meta_base_url)
        if s.agent_backend == "meta":
            svc.agent = svc.spark
        elif s.agent_backend == "baseten" and s.baseten_api_key is not None and s.baseten_model_id:
            from openai import OpenAI

            client = OpenAI(api_key=s.baseten_api_key.get_secret_value(), base_url=s.baseten_base_url)
            svc.agent = BasetenChatBackend(client, s.baseten_model_id)
        return svc

    # --- lookups --------------------------------------------------------------------------------

    def site(self, site_id: str) -> Site:
        return self.store.get(Site, site_id)

    def latest_sync(self, camera_id: str) -> ClockSync:
        syncs = self.store.find(ClockSync, camera_id=camera_id)
        if not syncs:
            raise ServiceError(f"camera {camera_id} has no clock synchronization record (PRD §8.3)")
        return syncs[-1]

    def valid_calibration(self, camera_id: str) -> FloorCalibration | None:
        cals = [c for c in self.store.find(FloorCalibration, camera_id=camera_id)
                if c.rig_state == RigState.VALIDATED_FLOOR_ONLY and not self.store.is_invalid(c.calibration_id)]
        return cals[-1] if cals else None

    def clip_timing(self, media: MediaAsset) -> tuple[datetime, ClockSync]:
        """Camera-clock start of the clip and THE clock sync its coverage was registered with. Observations must use
        the same sync as the coverage, or they would disagree after a re-sync (review #14)."""
        covs = self.store.find(CameraCoverage, media_id=media.media_id)
        if not covs:
            raise ServiceError(f"{media.media_id} has no recorded start time; register it at upload")
        sync = self.store.get(ClockSync, covs[-1].sync_id)
        return covs[-1].start_utc - timedelta(milliseconds=sync.offset_ms), sync

    def purge_sidecars(self, media_ids: list[str], shas: list[str]) -> int:
        """Delete manifests, frame tables, model-output caches and clip cuts derived from purged media."""
        d = self.settings.data_dir
        paths = [self.media.root / sub / f"{m}.json" for m in media_ids for sub in ("manifests", "frame_tables")]
        for m in media_ids:
            paths += [*(d / "clips").glob(f"{m}_*.mp4"), *(d / "inference_cache" / "chunks").glob(f"{m}_*.mp4")]
        for sha in shas:
            paths += list((d / "inference_cache").glob(f"sam_{sha[:16]}_*.json"))
        removed = 0
        for p in paths:
            if p.exists():
                self.media.delete_file(p)
                removed += 1
        return removed

    # --- paid operations ----------------------------------------------------------------------------

    def run_perception(self, media_id: str, *, concept: str | None = None, instance=None, case_id: str | None = None,
                       on_floor_plane: bool = False, frame_range: tuple[int, int] | None = None):  # fmt: skip
        if self.sam is None:
            raise ServiceError("SAM backend not configured (no MODEL_API_KEY)")
        original = self.store.get(MediaAsset, media_id)
        ingest = load_result(self.media, media_id)
        camera = self.store.get(Camera, original.camera_id)
        clip_start, clip_sync = self.clip_timing(original)
        req = PerceptionRequest(
            original=original, proxy=ingest.proxy, proxy_path=asset_path(self.media, ingest.proxy),
            original_frames=ingest.original_frames, proxy_frames=ingest.proxy_frames,
            authorization=self.store.get(MediaAuthorization, original.authorization_id), camera=camera,
            clip_start_camera_time=clip_start, sync=clip_sync,
            concept=concept, instance=instance, case_id=case_id, on_floor_plane=on_floor_plane,
            site=self.site(original.site_id), calibration=self.valid_calibration(camera.camera_id),
            frame_range=frame_range,
        )  # fmt: skip
        result = self._on_sam_loop(track_target(req, backend=self.sam, store=self.store,
                                                cache_dir=self.settings.data_dir / "inference_cache"))  # fmt: skip
        return result

    def handshake(self, row, *, now):
        """One planned handshake (forensics/handshake.py): SAM aimed at the scan point at the scan's moment on that
        camera; the carton it finds there is the scanned parcel. Stored as a ScanHandshake whatever the outcome."""
        from datetime import timedelta

        from spoor.forensics.handshake import BEFORE_S, CLOCK_MS, FOLLOW_S, SLIDE_M
        from spoor.spatial.homography import image_to_site
        from spoor.store import ScanHandshake

        # one row per scan, camera and clip (and clock state): footage that arrives later, or a clock fitted later,
        # gets its own row instead of the stored "no footage" / "clock not fitted" answer
        hid = (f"hs_{row.scan.scan_event_id}_{row.camera_id or 'none'}_{row.media_id or 'none'}"
               f"{'_unfitted' if row.reason in ('clock_not_fitted', 'cant_tell') else ''}").replace("-", "_")
        try:  # hs_ ids have no registered kind, so exists() can't see them
            return self.store.get(ScanHandshake, hid)
        except KeyError:
            pass
        base = {"handshake_id": hid, "site_id": row.scan.site_id, "scan_event_id": row.scan.scan_event_id,
                "waybill": row.waybill, "event_kind": row.scan.event_kind.value, "scan_point_id": row.scan_point_id,
                "camera_id": row.camera_id, "media_id": row.media_id, "at_utc": row.at, "rule": row.rule, "at": now}
        if row.reason:
            return self.store.put(ScanHandshake(**base, outcome=row.reason, note=row.note))
        at_iso = row.at.isoformat()
        cov = self.store.find(CameraCoverage, media_id=row.media_id)[-1]  # the follow stops where the clip does
        unc = timedelta(milliseconds=self.store.get(ClockSync, cov.sync_id).uncertainty_ms)
        wide = row.rule == "work_area" and unc.total_seconds() * 1000 > CLOCK_MS  # handheld on an unfitted clock
        pad = unc if wide else timedelta(0)
        start = max(row.at - timedelta(seconds=BEFORE_S) - pad, cov.start_utc).isoformat()
        end = min(row.at + timedelta(seconds=FOLLOW_S) + pad, cov.end_utc).isoformat()
        try:
            res = self.anchored_sam(None, row.media_id, concept=None, start_iso=start, end_iso=end,
                                    scan_point_id=row.scan_point_id, at_iso=None if row.rule == "work_area" else at_iso,
                                    keep="handled", event_kind=row.scan.event_kind.value)
            f_at = self.frame_at(row.media_id, at_iso)
        except (ServiceError, AnchorError) as e:
            return self.store.put(ScanHandshake(**base, outcome="failed", note=str(e)[:300]))
        if res.get("status") not in (None, "ok", "completed", "succeeded"):
            return self.store.put(ScanHandshake(**base, outcome="failed", note=f"{res.get('status')}: {res.get('message')}"[:300]))
        tracks = res.get("tracks", []) if wide else [
            t for t in res.get("tracks", []) if t["frames"][0] <= f_at + 10 and t["frames"][1] >= f_at - 2]
        near_box = {}
        for t in tracks:
            obs = [o for o in self.store.find(RawObservation, track_id=t["track_id"]) if o.bbox_xyxy_px]
            if obs:
                near_box[t["track_id"]] = min(obs, key=lambda o: abs(o.source_frame.frame_index - f_at)).bbox_xyxy_px
        plan = latest_plan(self.store, row.scan.site_id)
        cal = self.valid_calibration(self.store.get(MediaAsset, row.media_id).camera_id)
        if plan and cal and plan.read_point(row.scan_point_id):  # a belt, a cage or the frame is not a parcel
            rp0 = plan.read_point(row.scan_point_id)
            from types import SimpleNamespace

            from spoor.perception.anchor import event_xyz
            at_rp = SimpleNamespace(device_parts_m=None, position_m=event_xyz(rp0, row.scan.event_kind.value, plan.conveyors))                 if row.scan.event_kind.value in rp0.event_positions else rp0  # (sized where the event happens)
            pw, ph = parcel_extent_px(at_rp, cal)
            big = {k for k, b in near_box.items() if b[2] - b[0] > 2 * pw or b[3] - b[1] > 2 * ph}
            if big and len(big) == len(tracks):
                return self.store.put(ScanHandshake(**base, outcome="not_found", frame_index=f_at,
                                                    note="only outlines far bigger than a parcel at the point"))
            tracks = [t for t in tracks if t["track_id"] not in big]
        if not tracks:
            later = self._retry_later(row, start, end, f_at) if row.rule == "work_area" else None
            if later:
                return self.store.put(ScanHandshake(**base, **later))
            return self.store.put(ScanHandshake(**base, outcome="not_found", frame_index=f_at,
                                                note="nothing at the scan point at the scan's moment"))
        if len(tracks) > 1:  # two cartons fit: mark neither (never guess)
            return self.store.put(ScanHandshake(**base, outcome="cant_tell", frame_index=f_at,
                                                note=f"{len(tracks)} cartons at the point: can't tell which"))
        tid = tracks[0]["track_id"]
        obs = sorted((o for o in self.store.find(RawObservation, track_id=tid) if o.bbox_xyxy_px),
                     key=lambda o: o.source_frame.frame_index)  # fmt: skip
        if wide and obs:  # the carton's own moment in the hands, not the unfitted clock's guess
            f_at = obs[0].source_frame.frame_index
        near = min(obs, key=lambda o: abs(o.source_frame.frame_index - f_at)) if obs else None
        box = list(near.bbox_xyxy_px) if near else None
        after = [o for o in obs if o.source_frame.frame_index >= f_at]
        span = (after[-1].source_frame.pts_ms - after[0].source_frame.pts_ms) / 1000 if len(after) > 1 else 0.0
        labelled, note = row.rule == "work_area", ""
        boards = row.rule == "point" and row.scan.event_kind.value in BOARD_EVENTS and plan is not None             and row.scan.event_kind.value in plan.read_point(row.scan_point_id).event_positions
        if row.rule == "point" and (row.scan.event_kind.value in DIVERT_EVENTS or boards) and box and plan and cal:
            # carton-sized? a point at a chute mouth often outlines the whole tray: compare with this parcel's own
            # measured size at the point; if much bigger, prompt SAM again with a box of that size; else no label
            exp = self._expected_box(row, plan, cal)
            if exp is None:  # no measured size to check the outline against: no label (wrong 14 of 16 unchecked)
                return self.store.put(ScanHandshake(**base, outcome="cant_tell", track_id=tid, frame_index=f_at,
                                                    box_px=box, note="the parcel's measured size is not in the log, "
                                                    "so the outline cannot be checked against it"))  # fmt: skip
            if _area(box) > CARTON_X * _area(exp):
                re = self._reprompt(row, start, end, at_iso, exp, f_at, box)
                if re is None:
                    return self.store.put(ScanHandshake(**base, outcome="cant_tell", track_id=tid, frame_index=f_at,
                                                        box_px=box, note="SAM outlined more than the parcel (its "
                                                        "tray); a box of the parcel's size found nothing tighter"))  # fmt: skip
                tid, obs, box, after, span = re
        if boards:
            # boarding the loop (the induct the sorter reports where the parcel boards a carrier): the carrier taking it
            # is empty, so the one carton there is the parcel, if it then rides off ALONG the loop at the loop's speed
            # (a carton resting, or crossing, is something else). Measured on the floor at the deck's height
            labelled = self._rides_loop(row, plan, cal, obs, f_at)
            if not labelled:
                later = self._retry_later(row, start, end, f_at)
                if later:
                    return self.store.put(ScanHandshake(**base, **later))
                return self.store.put(ScanHandshake(**base, outcome="cant_tell", track_id=tid, frame_index=f_at,
                                                    box_px=box, note="the outline did not ride off along the loop: "
                                                    "can't tell it is the carton boarding"))  # fmt: skip
        elif row.rule == "point" and row.scan.event_kind.value not in DIVERT_EVENTS:
            labelled = False  # (the device's own spot: a belt passes a carton a second there; no label)
        elif row.rule == "point":
            # the diverted carton slides off its tray INTO the chute: from where the plan puts the event (on the loop)
            # towards the chute mouth. A tray (empty, or carrying it) carries on along the loop; a still outline is
            # something resting; a recirculated carton stays on its tray, so it can't be told from the tray
            rp = plan.read_point(row.scan_point_id) if plan else None
            moving = [o for o in obs if f_at - 2 <= o.source_frame.frame_index <= f_at + 15]
            kind = row.scan.event_kind.value
            if kind == "divert_confirmed" and rp is not None and cal is not None and len(moving) > 1:
                centres = [((o.bbox_xyxy_px[0] + o.bbox_xyxy_px[2]) / 2, (o.bbox_xyxy_px[1] + o.bbox_xyxy_px[3]) / 2)
                           for o in moving]  # fmt: skip
                xy = image_to_site(cal, centres, rp.position_m[2])[:, :2]
                into = np.array(rp.position_m[:2]) - np.array(rp.position_for(kind))
                if np.linalg.norm(into) > 0:
                    into = into / np.linalg.norm(into)
                    step = xy[-1] - xy[0]
                    along, across = float(step @ into), abs(float(step @ np.array([-into[1], into[0]])))
                    labelled = along >= SLIDE_M and along >= 2 * across
            if not labelled:
                return self.store.put(ScanHandshake(**base, outcome="cant_tell", track_id=tid, frame_index=f_at,
                                                    box_px=box, note="the outline did not go into the chute (a tray "
                                                    "carries on along the loop): can't tell it is the carton"))  # fmt: skip
        if row.rule == "tunnel_exit":
            note = "the tunnel's own photo identifies it; at the exit it can't be told from the carton queued before it"
        return self.store.put(ScanHandshake(**base, outcome="outlined", track_id=tid, frame_index=f_at, box_px=box,
                                            labelled=labelled, frames_followed=len(after), followed_s=round(span, 2),
                                            note=note))

    def _rides_loop(self, row, plan, cal, obs, f_at, f_scan=None) -> bool:
        """The outline, on the floor at the deck height, moves at least RIDE_M along the loop's direction at the boarding
        spot within ~1.5 s, and at least twice as far along as across."""
        from spoor.perception.anchor import event_xyz
        from spoor.spatial.homography import image_to_site

        rp = plan.read_point(row.scan_point_id)
        x, y, deck = event_xyz(rp, row.scan.event_kind.value, plan.conveyors)
        loop = [cv for cv in plan.conveyors if cv.kind == "loop"]
        segs = [(a, b) for cv in loop for a, b in zip(cv.path_m, cv.path_m[1:] + ([cv.path_m[0]] if cv.closed else []), strict=False)]
        if not segs:
            return False
        p = np.array([x, y])

        def dist(a, b):
            a, b = np.array(a), np.array(b)
            t = np.clip(np.dot(p - a, b - a) / max(1e-9, np.dot(b - a, b - a)), 0, 1)
            return float(np.linalg.norm(p - (a + t * (b - a))))
        a, b = min(segs, key=lambda s_: dist(*s_))
        d = np.array(b) - np.array(a)
        d = d / max(1e-9, np.linalg.norm(d))
        def travel(lo, hi):
            seen = [o for o in obs if lo <= o.source_frame.frame_index <= hi]
            if len(seen) < 2:
                return None
            c = [((o.bbox_xyxy_px[0] + o.bbox_xyxy_px[2]) / 2, (o.bbox_xyxy_px[1] + o.bbox_xyxy_px[3]) / 2) for o in seen]
            xy = image_to_site(cal, c, deck)[:, :2]
            step = xy[-1] - xy[0]
            frames = seen[-1].source_frame.frame_index - seen[0].source_frame.frame_index
            return float(step @ d), abs(float(step @ np.array([-d[1], d[0]]))), max(1, frames)

        after = travel(f_at, f_at + 15)
        if after is None:
            return False
        along, across, n = after
        if not (along >= RIDE_M and along >= 2 * across):
            return False
        # it must not have been riding the loop already: an empty carrier passing the boarding spot rides along at the
        # loop's speed before the scan too (W1: SAM's point landed on the tray the parcel was about to board); a
        # carton boarding comes off the induction belt, so before the scan it was not yet moving along with the loop
        f0 = f_at if f_scan is None else f_scan
        before = travel(f0 - 6, f0)
        return before is None or before[0] / before[2] < 0.5 * along / n

    RETRY_S = (0.5, 1.0)

    def _retry_later(self, row, start, end, f_at) -> dict | None:
        """The outline at the scan instant failed its checks only because of timing (a head in front of the carton at
        the door; the parcel not yet on its tray at the sorter's boarding spot): prompt SAM again RETRY_S later, at the
        same spot (a handheld point: where the scanner is used) or where the parcel's tray is by then (boarding: the
        boarding spot carried along the loop at the plan's loop speed), and label only if that passes every check the
        scan instant's outline had to pass. None: leave it as it was."""
        from datetime import timedelta

        from spoor.perception.anchor import event_xyz, handled
        from spoor.spatial.homography import site_to_image

        plan = latest_plan(self.store, row.scan.site_id)
        cal = self.valid_calibration(self.store.get(MediaAsset, row.media_id).camera_id)
        rp = plan.read_point(row.scan_point_id) if plan else None
        if rp is None or cal is None:
            return None
        kind = row.scan.event_kind.value
        boards = row.rule == "point" and kind in BOARD_EVENTS and kind in rp.event_positions
        if not boards and row.rule != "work_area":
            return None
        x, y, z = event_xyz(rp, kind, plan.conveyors) if boards else list(rp.position_m)
        along = None
        if boards:
            loop = [cv for cv in plan.conveyors if cv.kind == "loop" and cv.speed_mps]
            segs = [(a, b, cv.speed_mps) for cv in loop
                    for a, b in zip(cv.path_m, cv.path_m[1:] + ([cv.path_m[0]] if cv.closed else []), strict=False)]
            if not segs:
                return None
            p = np.array([x, y])

            def dist(a, b):
                a, b = np.array(a), np.array(b)
                t = np.clip(np.dot(p - a, b - a) / max(1e-9, np.dot(b - a, b - a)), 0, 1)
                return float(np.linalg.norm(p - (a + t * (b - a))))
            a, b, speed = min(segs, key=lambda s_: dist(s_[0], s_[1]))
            along = (np.array(b) - np.array(a)) / max(1e-9, np.linalg.norm(np.array(b) - np.array(a))) * speed
        for dt in self.RETRY_S:
            at2 = row.at + timedelta(seconds=dt)
            px, py = (x + along[0] * dt, y + along[1] * dt) if along is not None else (x, y)
            uv, front = site_to_image(cal, [[px, py, z]])
            w, h = cal.image_wh_px
            if not front[0] or not (0 <= uv[0][0] < w and 0 <= uv[0][1] < h):
                continue
            pt = (int(uv[0][0] + 0.5), int(uv[0][1] + 0.5))
            try:
                res = self.anchored_sam(None, row.media_id, concept=None, start_iso=start, end_iso=end,
                                        scan_point_id=row.scan_point_id, at_iso=at2.isoformat(), keep="handled",
                                        event_kind=kind, point_px=pt)
                f2 = self.frame_at(row.media_id, at2.isoformat())
            except (ServiceError, AnchorError):
                continue
            if res.get("status") not in (None, "ok", "completed", "succeeded"):
                continue
            cands = []
            for t in res.get("tracks", []):
                obs = sorted((o for o in self.store.find(RawObservation, track_id=t["track_id"]) if o.bbox_xyxy_px),
                             key=lambda o: o.source_frame.frame_index)
                near = [o for o in obs if o.source_frame.frame_index == f2]
                if near and near[0].bbox_xyxy_px[0] <= pt[0] <= near[0].bbox_xyxy_px[2] \
                        and near[0].bbox_xyxy_px[1] <= pt[1] <= near[0].bbox_xyxy_px[3]:
                    cands.append((t["track_id"], obs, list(near[0].bbox_xyxy_px)))
            if len(cands) != 1:  # nothing, or two cartons under the point: never guess
                continue
            tid, obs, box = cands[0]
            pw, ph = parcel_extent_px(rp, cal)
            if box[2] - box[0] > 2 * pw or box[3] - box[1] > 2 * ph:
                continue
            if boards:
                exp = self._expected_box(row, plan, cal)
                if exp is None or _area(box) > CARTON_X * _area(exp):
                    continue
                if not self._rides_loop(row, plan, cal, obs, f2, f_scan=f_at):
                    continue
            else:
                anchor = anchor_for(rp, cal, kind, plan.conveyors)
                if anchor.kind != "area" or not handled(anchor.polygon_px, [o.bbox_xyxy_px for o in obs]):
                    continue
            after = [o for o in obs if o.source_frame.frame_index >= f2]
            span = (after[-1].source_frame.pts_ms - after[0].source_frame.pts_ms) / 1000 if len(after) > 1 else 0.0
            return {"outcome": "outlined", "track_id": tid, "frame_index": f2, "box_px": box, "labelled": True,
                    "frames_followed": len(after), "followed_s": round(span, 2),
                    "note": f"found {dt:g} s after the scan instant (at the instant: "
                            f"{'a person in front of the carton' if not boards else 'the parcel not yet on its tray'})"}
        return None

    def _expected_box(self, row, plan, cal):
        """This parcel's own measured size (its tunnel read's dims) projected at the scan point, or None."""
        from spoor.contracts import ScanEvent

        dims = next((s.dims_mm for s in self.store.find(ScanEvent, event_kind="tunnel_read")
                     if s.dims_mm and any(i.value == row.waybill for i in s.identifiers)), None)  # fmt: skip
        rp = plan.read_point(row.scan_point_id)
        kind = row.scan.event_kind.value
        if dims and rp and kind in rp.event_positions:  # where it boards: its bottom on that conveyor's deck
            from types import SimpleNamespace

            from spoor.perception.anchor import event_xyz
            x, y, deck = event_xyz(rp, kind, plan.conveyors)
            rp = SimpleNamespace(device_parts_m=None, position_m=[x, y, deck + min(dims) / 2000])
        return expected_carton_px(rp, cal, tuple(v / 1000 for v in dims)) if dims and rp else None

    def _reprompt(self, row, start, end, at_iso, exp, f_at, first):
        """SAM again with a box of the parcel's own size, centred on what SAM first outlined (the parcel sits on that
        tray; the scan point itself is the chute's edge); its track if carton-sized, else None."""
        cx, cy = (first[0] + first[2]) / 2, (first[1] + first[3]) / 2
        hw, hh = (exp[2] - exp[0]) * 0.6, (exp[3] - exp[1]) * 0.6
        try:
            res = self.anchored_sam(None, row.media_id, concept=None, start_iso=start, end_iso=end,
                                    scan_point_id=row.scan_point_id, at_iso=at_iso,
                                    prompt_box=(cx - hw, cy - hh, cx + hw, cy + hh), event_kind=row.scan.event_kind.value)  # fmt: skip
        except (ServiceError, AnchorError):
            return None
        tracks = [t for t in res.get("tracks", []) if t["frames"][0] <= f_at + 10 and t["frames"][1] >= f_at - 2]
        for t in tracks:
            obs = sorted((o for o in self.store.find(RawObservation, track_id=t["track_id"]) if o.bbox_xyxy_px),
                         key=lambda o: o.source_frame.frame_index)  # fmt: skip
            if not obs:
                continue
            near = min(obs, key=lambda o: abs(o.source_frame.frame_index - f_at))
            if _area(near.bbox_xyxy_px) <= CARTON_X * _area(exp):
                after = [o for o in obs if o.source_frame.frame_index >= f_at]
                span = (after[-1].source_frame.pts_ms - after[0].source_frame.pts_ms) / 1000 if len(after) > 1 else 0.0
                return t["track_id"], obs, list(near.bbox_xyxy_px), after, span
        return None

    def watch_container_area(self, w, *, now) -> list:
        """One planned watch (left_alert.py): SAM on the clip after the container scans, keeping cartons that start in
        the point's work area and leave it; each one is a LiveAlert at the moment it leaves."""
        from spoor.store import LiveAlert

        plan = latest_plan(self.store, self.store.get(MediaAsset, w.media_id).site_id)
        rp = plan.read_point(w.scan_point_id)
        cal = self.valid_calibration(w.camera_id)
        if cal is None:
            return []
        poly = anchor_for(rp, cal).polygon_px
        res = self.anchored_sam(None, w.media_id, concept=None, start_iso=w.start.isoformat(), end_iso=w.end.isoformat(),
                                scan_point_id=w.scan_point_id, at_iso=None, out_of_view=True)  # fmt: skip
        out = []
        cov = self.store.find(CameraCoverage, media_id=w.media_id)[-1]
        for t in res.get("tracks", []):
            obs = sorted((o for o in self.store.find(RawObservation, track_id=t["track_id"]) if o.bbox_xyxy_px),
                         key=lambda o: o.source_frame.frame_index)  # fmt: skip
            gone = next((o for o in obs if not inside(poly, (o.bbox_xyxy_px[0] + o.bbox_xyxy_px[2]) / 2,
                                                      (o.bbox_xyxy_px[1] + o.bbox_xyxy_px[3]) / 2)), None)                 or (obs[-1] if obs else None)  # carried out of view: it left at its last sighting  # fmt: skip
            if gone is None:
                continue
            t_left = gone.source_frame.normalized_utc or (cov.start_utc + timedelta(milliseconds=gone.source_frame.pts_ms))
            # on a clock known to +-u, only parcels scanned in more than u before the exit could be the one leaving
            unc = timedelta(milliseconds=self.store.get(ClockSync, cov.sync_id).uncertainty_ms)
            cands = [{"waybill": c["waybill"], "container": c["container"], "scanned_in": c["scanned_in"].isoformat()}
                     for c in w.parcels if c["scanned_in"] < t_left - unc
                     and (c["container_left"] is None or c["container_left"] > t_left + unc)]
            if not cands:
                continue
            aid = f"alert_{t['track_id']}"
            try:
                out.append(self.store.get(LiveAlert, aid))
                continue
            except KeyError:
                pass
            out.append(self.store.put(LiveAlert(
                alert_id=aid, site_id=plan.site_id, kind="left_without_scan", scan_point_id=w.scan_point_id,
                camera_id=w.camera_id, media_id=w.media_id, at_utc=t_left, track_id=t["track_id"],
                frame_index=gone.source_frame.frame_index, box_px=list(gone.bbox_xyxy_px), candidates=cands,
                note="a carton left the work area; no scan of the parcels last scanned into a container here since"
                     + (f"; camera clock +-{unc.total_seconds():g} s (not fitted)" if unc.total_seconds() > 1 else ""),
                at=now)))
        return out

    def frame_at(self, media_id: str, iso: str) -> int:
        """Nearest original frame to a time on the shared clock (as /media/{id}/frame-at)."""
        cov = self.store.find(CameraCoverage, media_id=media_id)
        if not cov:
            raise ServiceError(f"{media_id} has no recorded start time")
        t = datetime.fromisoformat(iso)
        if t.tzinfo is None:
            raise ServiceError("times must include a timezone")
        if not cov[-1].start_utc <= t <= cov[-1].end_utc:
            raise ServiceError(f"{iso} is outside this clip ({cov[-1].start_utc.isoformat()} - {cov[-1].end_utc.isoformat()})")
        table = load_result(self.media, media_id).original_frames
        rel_ms = (t - cov[-1].start_utc).total_seconds() * 1000
        return min(range(len(table.pts_ms)), key=lambda i: abs(table.pts_ms[i] - rel_ms))

    def anchored_sam(self, case: Case | None, media_id: str, *, concept: str | None, start_iso: str | None,
                     end_iso: str | None, scan_point_id: str | None, at_iso: str | None,
                     out_of_view: bool = False, keep: str = "leaves", prompt_box: tuple | None = None,
                     event_kind: str | None = None, point_px: tuple[int, int] | None = None) -> dict:
        """SAM on a window of one clip, aimed by a scan point (anchor.py): a device/sorter point is a point prompt on
        the scan's frame; a handheld point's work area keeps only tracks that start inside it and leave it."""
        original = self.store.get(MediaAsset, media_id)
        lo = self.frame_at(media_id, start_iso) if start_iso else None
        hi = self.frame_at(media_id, end_iso) if end_iso else None
        n = len(load_result(self.media, media_id).original_frames.pts_ms)
        window = (lo or 0, n - 1 if hi is None else hi) if (lo is not None or hi is not None) else None
        if window is None and at_iso:  # a scan's second: 5 s either side, not the whole clip
            f = self.frame_at(media_id, at_iso)
            window = (max(0, f - 50), min(n - 1, f + 50))
        anchor = None
        if scan_point_id:
            plan = latest_plan(self.store, original.site_id)
            rp = plan.read_point(scan_point_id) if plan else None
            if rp is None:
                raise ServiceError(f"unknown scan point {scan_point_id}")
            moved = bool(event_kind and event_kind in rp.event_positions)  # the event happens away from the device:
            # the cameras that see THAT spot (checked through each one's calibration below), not the device's
            if original.camera_id not in rp.visible_by and not moved:
                raise ServiceError(f"{original.camera_id} does not see {scan_point_id} (plan check); try "
                                   f"{', '.join(rp.visible_by) or 'no camera'}")
            cal = self.valid_calibration(original.camera_id)
            if cal is None:
                raise ServiceError(f"{original.camera_id} has no valid calibration")
            anchor = anchor_for(rp, cal, event_kind, plan.conveyors)
        if point_px is not None and anchor is not None:  # a retry: prompt this pixel at at_iso (handshake retries)
            from spoor.perception.anchor import Anchor
            anchor = Anchor(anchor.scan_point_id, "point", point_px=(int(point_px[0]), int(point_px[1])))
        instance = None
        if anchor is not None and anchor.kind == "point":
            if not at_iso:
                raise ServiceError("a point anchor needs at_iso: the scan's time, when the parcel was at the point")
            if prompt_box and original.probe:  # a sized box is kept inside the picture (a carton near the edge)
                fw, fh = original.probe.display_wh_px
                prompt_box = (max(0, prompt_box[0]), max(0, prompt_box[1]), min(fw, prompt_box[2]), min(fh, prompt_box[3]))
                if prompt_box[2] - prompt_box[0] < 4 or prompt_box[3] - prompt_box[1] < 4:
                    raise ServiceError("the parcel-sized box falls outside the picture")
            # a sized box prompt carries its own point: its centre
            pt = anchor.point_px
            if prompt_box:
                pt = (round((prompt_box[0] + prompt_box[2]) / 2), round((prompt_box[1] + prompt_box[3]) / 2))
            instance = InstancePrompt(frame_index=self.frame_at(media_id, at_iso), positive_points_px=[pt],
                                      box_ltrb_px=tuple(round(v) for v in prompt_box) if prompt_box else None)  # fmt: skip
            concept = None
        elif not concept:
            concept = "box"
        r = self.run_perception(media_id, concept=concept, instance=instance, case_id=case.case_id if case else None,
                                frame_range=window)  # fmt: skip
        tracks = r.tracks
        if anchor is not None and anchor.kind == "area":
            boxes = {t.track_id: [o.bbox_xyxy_px for o in sorted(
                (o for o in r.observations if o.track_id == t.track_id), key=lambda o: o.source_frame.frame_index)]
                for t in r.tracks}  # fmt: skip
            wh = tuple(self.valid_calibration(original.camera_id).image_wh_px) if out_of_view else None
            last = window[1] if window else n - 1  # a track still in view at the window's end only ran out of footage
            if keep == "handled":  # a handshake at a handheld point: the carton in the hands, put in or taken out
                tracks = [t for t in r.tracks if handled(anchor.polygon_px, boxes[t.track_id])]
            else:
                tracks = [t for t in r.tracks if leaves(anchor.polygon_px, boxes[t.track_id], wh)
                          and (not out_of_view or t.last_frame_index < last - 1 or leaves(anchor.polygon_px, boxes[t.track_id]))]
        return {"status": r.status, "message": r.message, "cache_hit": r.cache_hit,
                "frames_sent": [window[0], window[1]] if window else "whole clip",
                "anchor": None if anchor is None else {"scan_point": anchor.scan_point_id, "kind": anchor.kind},
                "tracks": [{"track_id": t.track_id, "frames": [t.first_frame_index, t.last_frame_index]}
                           for t in tracks],
                "dropped": len(r.tracks) - len(tracks),
                "note": (("kept only cartons handled in the work area; " if keep == "handled" else
                          "kept only tracks that start inside the work area and leave it; ") if anchor and anchor.kind
                         == "area" else "") + "new tracks are NOT linked to the case object until an investigator "
                                              "confirms them"}  # fmt: skip

    def case_cameras(self, case: Case) -> list[str]:
        """The cameras a case may use: those it was opened with, plus any an investigator granted later (a camera
        installed after the case opened, e.g. a checkpoint camera), each grant a case revision with its actor. Empty:
        every camera on the site (as at opening)."""
        if not case.camera_ids:
            return []
        granted = [c for r in self.store.find(CaseRevision, case_id=case.case_id)
                   if r.reason.startswith(GRANT_REASON) for c in r.changed_ids]  # fmt: skip
        return list(dict.fromkeys([*case.camera_ids, *granted]))

    def tool_context(self, case: Case) -> ToolContext:
        site = self.site(case.site_id)
        window = None
        if case.window:
            window = TimeWindow(start_utc=case.window.start_utc, end_utc=case.window.end_utc)
        ctx = ToolContext(store=self.store, site=site, case=case, verifier=Verifier(self.store, site),
                          scope=EvidenceScope(camera_ids=self.case_cameras(case), window=window))  # fmt: skip

        def run_sam(media_id: str, concept: str | None = None, start_iso: str | None = None,
                    end_iso: str | None = None, scan_point_id: str | None = None, at_iso: str | None = None) -> dict:
            try:
                return self.anchored_sam(case, media_id, concept=concept, start_iso=start_iso, end_iso=end_iso,
                                         scan_point_id=scan_point_id, at_iso=at_iso)  # fmt: skip
            except (ServiceError, AnchorError) as e:
                return {"status": "analysis_unavailable", "reason": str(e)}

        def ask_spark(media_id: str, start_s: float, end_s: float, template: str, track_id: str | None = None) -> dict:
            if self.spark is None or self.spark_client is None:
                return {"status": "analysis_unavailable", "reason": "Muse Spark not configured"}
            original = self.store.get(MediaAsset, media_id)
            ing = load_result(self.media, media_id)
            t0 = ing.proxy_frames.pts_ms[0]
            window = cut_clip(asset_path(self.media, ing.proxy), ing.proxy_frames, source_media_id=media_id,
                              start_ms=t0 + start_s * 1000, end_ms=t0 + end_s * 1000,
                              out_dir=self.settings.data_dir / "clips")  # fmt: skip
            crop = None
            if track_id:  # look closer: the region that track covers in this window, with room for hands and loads
                boxes = [o.bbox_xyxy_px for o in self.store.find(RawObservation, track_id=track_id)
                         if o.source_frame.media_id == media_id and o.bbox_xyxy_px
                         and window.start_frame <= o.source_frame.frame_index <= window.end_frame]
                if not boxes:
                    return {"status": "analysis_unavailable", "reason": f"{track_id} is not seen in this window"}
                w, h = ing.proxy.probe.width_px, ing.proxy.probe.height_px
                x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
                x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
                mx, my = max(40, 0.3 * (x1 - x0)), max(40, 0.3 * (y1 - y0))
                crop = (max(0, int(x0 - mx)), max(0, int(y0 - my)), min(w, int(x1 + mx)), min(h, int(y1 + my)))
                window = crop_window(window, crop)
            auth = self.store.get(MediaAuthorization, original.authorization_id)
            with uploaded(self.spark_client, window.path) as file_id:
                res = ask_clip(backend=self.spark, upload_file_id=file_id, window=window, table=ing.original_frames,
                               template=template, target=case.target_description,
                               hosted_processing_allowed=auth.hosted_processing_allowed, store=self.store,
                               case_id=case.case_id)  # fmt: skip
            objs = self.store.find(ObjectInstance, case_id=case.case_id)
            grounded = ground_facts(self.store, objs[0].object_instance_id, res.facts) if objs else []
            return {"status": res.status, "abstain_reason": res.abstain_reason, "unknowns": res.unknowns,
                    "facts": [{"statement": g.fact.statement, "grounding": g.status, "observation_ids":
                               g.observation_ids} for g in grounded],
                    "candidate_hypotheses": res.hypotheses, "rejected_statements": len(res.rejected_statements),
                    "uninspected_ms": res.uninspected, "crop_px": crop,
                    "note": "facts are proposals; only 'grounded' ones match SAM observations"}  # fmt: skip

        ctx.run_sam, ctx.ask_spark = run_sam, ask_spark
        return ctx


def utcnow() -> datetime:
    return datetime.now(UTC)


CONFIRM_STATUSES = {AssociationStatus.HUMAN_CONFIRMED, AssociationStatus.VERIFIED_SAME_CAMERA,
                    AssociationStatus.REJECTED, AssociationStatus.CANDIDATE_CROSS_CAMERA}  # fmt: skip
