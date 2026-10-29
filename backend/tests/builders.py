"""Test-only builder for evidence-store scenarios. Values here are hand-made fixtures for unit tests — they are never
used by the runtime and never presented as model inference."""

from datetime import datetime, timedelta

from spoor.contracts import (
    Actor,
    ActorKind,
    AssetKind,
    AssociationStatus,
    Camera,
    CameraCoverage,
    Case,
    ClockSync,
    FloorCalibration,
    FrameRef,
    MediaAsset,
    MediaAuthorization,
    MediaProbe,
    ModelProvenance,
    ObjectInstance,
    RawObservation,
    RigState,
    Site,
    SourceType,
    SpatialEstimate,
    SpatialMode,
    Track,
    TrackAssociation,
    new_id,
)
from spoor.store import EvidenceStore

HUMAN = Actor(kind=ActorKind.HUMAN, id="investigator_1")
FPS = 10


class World:
    def __init__(self, store: EvidenceStore, site: Site, now: datetime):
        self.store, self.site, self.t0 = store, site, now
        store.put(site)
        self.auth = store.put(MediaAuthorization(
            authorization_id="auth_w", site_id=site.site_id, uploader="tester", rights_statement="unit test fixture",
            purpose="test", consent_confirmed=True, hosted_processing_allowed=True,
            retention_until=now + timedelta(days=30), recorded_at=now,
        ))  # fmt: skip
        self.cameras: dict[str, Camera] = {}
        self.syncs: dict[str, ClockSync] = {}
        self.calibrations: dict[str, FloorCalibration] = {}
        self.case = store.put(Case(case_id="case_w", site_id=site.site_id, question="Where is the blue case?",
                                   target_description="blue equipment case", created_by="investigator_1",
                                   created_at=now))  # fmt: skip

    def camera(self, camera_id: str, *, sync_uncertainty_ms: float = 20.0, outside: bool = False) -> str:
        cam = Camera(camera_id=camera_id, site_id=self.site.site_id, floor_id=self.site.floors[0].floor_id,
                     name=camera_id, resolution_wh_px=(1280, 720))  # fmt: skip
        self.cameras[camera_id] = self.store.put(cam)
        self.syncs[camera_id] = self.store.put(ClockSync(
            sync_id=f"sync_{camera_id}", camera_id=camera_id, offset_ms=0, uncertainty_ms=sync_uncertainty_ms,
            method="test fixture", created_at=self.t0,
        ))  # fmt: skip
        identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        self.calibrations[camera_id] = self.store.put(FloorCalibration(
            calibration_id=f"calib_{camera_id}", camera_id=camera_id, floor_id=self.site.floors[0].floor_id,
            version=1, rig_state=RigState.VALIDATED_FLOOR_ONLY, homography_image_to_floor=identity,
            fit_image_points_px=pts, fit_floor_points_m=pts, holdout_image_points_px=pts, holdout_floor_points_m=pts,
            holdout_error_median_m=0.05, holdout_error_p95_m=0.1, software_version="test", created_at=self.t0,
        ))  # fmt: skip
        return camera_id

    def clip(self, camera_id: str, start_s: float, end_s: float, fps: float | None = None) -> str:
        media_id = new_id("media")
        probe = None if fps is None else MediaProbe(container="mp4", video_codec="h264", width_px=1280, height_px=720,
                                                    duration_ms=(end_s - start_s) * 1000, avg_fps=fps)
        self.store.put(MediaAsset(probe=probe, 
            media_id=media_id, site_id=self.site.site_id, camera_id=camera_id, kind=AssetKind.ORIGINAL,
            sha256=f"{abs(hash(media_id)):064x}"[-64:], byte_size=1000, mime_type="video/mp4",
            original_filename=f"{camera_id}.mp4", authorization_id=self.auth.authorization_id, ingested_at=self.t0,
            ingested_by="tester",
        ))  # fmt: skip
        self.store.put(CameraCoverage(
            coverage_id=new_id("coverage"), camera_id=camera_id, media_id=media_id,
            start_utc=self.t0 + timedelta(seconds=start_s), end_utc=self.t0 + timedelta(seconds=end_s),
            sync_id=self.syncs[camera_id].sync_id, time_uncertainty_ms=self.syncs[camera_id].uncertainty_ms,
        ))  # fmt: skip
        self._clip_start = getattr(self, "_clip_start", {})
        self._clip_start[media_id] = start_s
        return media_id

    def track(self, camera_id: str, media_id: str, label: str = "blue equipment case") -> str:
        track_id = new_id("track")
        self.store.put(Track(track_id=track_id, camera_id=camera_id, media_id=media_id, label=label,
                             provider_object_id="1", first_frame_index=0, last_frame_index=0,
                             provenance=ModelProvenance(model="fixture", model_version="0", provider="test")))
        self._track_media = getattr(self, "_track_media", {})
        self._track_media[track_id] = (camera_id, media_id)
        return track_id

    def obs(self, track_id: str, t_s: float, *, xy: tuple[float, float] | None = None, zone: str | None = None,
            flags: tuple[str, ...] = (), observed: bool = True, synced: bool = True,
            label: str = "blue equipment case") -> str:  # fmt: skip
        camera_id, media_id = self._track_media[track_id]
        pts_ms = (t_s - self._clip_start[media_id]) * 1000
        sync = self.syncs[camera_id]
        frame = FrameRef(
            media_id=media_id, pts_ms=pts_ms, frame_index=round(pts_ms * FPS / 1000),
            normalized_utc=self.t0 + timedelta(seconds=t_s) if synced else None,
            sync_id=sync.sync_id if synced else None, time_uncertainty_ms=sync.uncertainty_ms if synced else None,
        )  # fmt: skip
        oid = new_id("observation")
        self.store.put(RawObservation(
            observation_id=oid, source_type=SourceType.VIDEO, camera_id=camera_id, source_frame=frame,
            track_id=track_id, label=label, bbox_xyxy_px=(100, 100, 200, 200), frame_wh_px=(1280, 720),
            observed=observed, quality_flags=list(flags),
            provenance=ModelProvenance(model="fixture", model_version="0", provider="test"), created_at=self.t0,
        ))  # fmt: skip
        if xy is not None or zone is not None:
            if xy is not None:
                est = SpatialEstimate(
                    estimate_id=new_id("spatial_estimate"), observation_ids=[oid], spatial_mode=SpatialMode.FLOOR_XY,
                    floor_id=self.site.floors[0].floor_id, floor_xy_m=xy, zone_id=zone, uncertainty_radius_m=0.2,
                    method="fixture", calibration_id=self.calibrations[camera_id].calibration_id, created_at=self.t0,
                )  # fmt: skip
            else:
                est = SpatialEstimate(estimate_id=new_id("spatial_estimate"), observation_ids=[oid],
                                      spatial_mode=SpatialMode.ZONE_ONLY, zone_id=zone, method="fixture",
                                      created_at=self.t0)  # fmt: skip
            self.store.put(est)
        return oid

    def obj(self, label: str = "blue equipment case", *tracks: str,
            status: AssociationStatus = AssociationStatus.VERIFIED_SAME_CAMERA) -> str:  # fmt: skip
        oid = new_id("object_instance")
        self.store.put(ObjectInstance(object_instance_id=oid, case_id=self.case.case_id, label=label,
                                      created_by="investigator_1", created_at=self.t0))  # fmt: skip
        for t in tracks:
            self.link(oid, t, status)
        return oid

    def link(self, object_id: str, track_id: str, status: AssociationStatus, version: int = 1) -> None:
        self.store.put(TrackAssociation(object_instance_id=object_id, track_id=track_id, status=status, reason="test",
                                        version=version, created_at=self.t0, created_by="tester"))  # fmt: skip

    def ms(self, t_s: float) -> float:
        return (self.t0 + timedelta(seconds=t_s)).timestamp() * 1000
