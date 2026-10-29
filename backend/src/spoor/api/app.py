"""Spoor HTTP API (PRD §25). Every write is authenticated, role- and site-checked, and audited."""

import asyncio
import json
import shutil
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import AwareDatetime, BaseModel, Field, ValidationError

from spoor import __version__
from spoor.agents import investigate
from spoor.config import Settings, get_settings
from spoor.contracts import (
    Actor,
    ActorKind,
    AssociationStatus,
    Camera,
    CameraCoverage,
    Case,
    ClockDomain,
    ClockSync,
    FloorCalibration,
    Hypothesis,
    HypothesisStatus,
    HypothesisStatusChange,
    MediaAsset,
    MediaAuthorization,
    ObjectInstance,
    ParcelIdentifier,
    RawObservation,
    Role,
    ScanEvent,
    SensorEvent,
    Site,
    TimeWindow,
    Track,
    TrackAssociation,
    VerifiedFinding,
    new_id,
)
from spoor.contracts.site import SITE_FRAME
from spoor.ingest import IngestRejected, asset_path, extract_frame, ingest, load_result
from spoor.ingest.ffmpeg import MediaToolError
from spoor.perception import InstancePrompt, PromptError
from spoor.reports import build_report, canonical_sha256, content_fingerprint, manifest, render_html
from spoor.scans import ScanImportError, ingest_scans, parse_scan_jsonl
from spoor.spatial import (
    AnchorPair,
    CalibrationError,
    ClockFitError,
    ValidationThresholds,
    fit_clock,
    fit_floor_calibration,
    site_to_renderer,
    sync_from_fit,
)
from spoor.spatial.frames import SITE_TO_RENDERER
from spoor.store import (
    AgentStep,
    AuditEntry,
    CostEntry,
    EvidenceRequest,
    ReportRecord,
    StoreError,
    estimate_for,
    latest_associations,
    unobserved_intervals,
    visibility_timeline,
    world_state_at,
)
from spoor.store.parcels import (
    container_chain,
    facility_visit,
    graded_last_seen,
    resolve_identity,
    scans_for,
    timed,
)
from spoor.views import annotate_png, case_diff, replay

from .auth import Principal
from .services import ServiceError, Services

bearer = HTTPBearer(auto_error=False)


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    svc = services or Services.from_settings(settings or get_settings())
    app = FastAPI(title="Spoor API", version=__version__,
                  description="Evidence-grounded spatial investigation support. Not a forensic certification.")
    app.state.svc = svc

    # --- dependencies ------------------------------------------------------------------------------

    def principal(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Principal:
        if creds is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
        p = svc.tokens.resolve(creds.credentials)
        if p is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
        svc.limiter.check(p.user_id)
        return p

    User = Annotated[Principal, Depends(principal)]

    def actor(p: Principal) -> Actor:
        return Actor(kind=ActorKind.HUMAN, id=p.user_id)

    def now() -> datetime:
        return datetime.now(UTC)

    def get_or_404(model, rid: str):
        try:
            return svc.store.get(model, rid)
        except KeyError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{rid} not found") from None

    def case_for(p: Principal, case_id: str) -> Case:
        case = get_or_404(Case, case_id)
        p.require_site(case.site_id)
        return case

    def audit(p: Principal, action: str, target: str | None, **detail) -> None:
        svc.store.audit(actor(p), action, target, detail, now())

    # --- health ----------------------------------------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "version": __version__, "sam": svc.sam is not None, "spark": svc.spark is not None,
                "agents": svc.agent is not None and svc.settings.agent_backend}

    # --- sites, cameras, calibration -------------------------------------------------------------------

    @app.post("/v1/sites", status_code=201)
    def create_site(site: Site, p: User) -> Site:
        p.require_role(Role.SITE_ADMIN)
        p.require_site(site.site_id)
        svc.store.put(site)
        audit(p, "create_site", site.site_id)
        return site

    @app.post("/v1/sites/{site_id}/cameras", status_code=201)
    def create_camera(site_id: str, camera: Camera, p: User) -> Camera:
        p.require_role(Role.SITE_ADMIN)
        p.require_site(site_id)
        if camera.site_id != site_id:
            raise HTTPException(400, "camera.site_id does not match the path")
        if svc.store.exists(camera.camera_id) and svc.store.get(Camera, camera.camera_id).site_id != site_id:
            raise HTTPException(409, "camera id is already registered to another site")
        svc.store.put(camera)
        audit(p, "create_camera", camera.camera_id)
        return camera

    class CalibrationRequest(BaseModel):
        image_points_px: list[tuple[float, float]]
        floor_points_m: list[tuple[float, float]]
        holdout_image_points_px: list[tuple[float, float]] = []
        holdout_floor_points_m: list[tuple[float, float]] = []
        image_wh_px: tuple[int, int] = Field(description="Size of the frame the image points were clicked on")
        max_median_m: float = Field(gt=0, description="Chosen from investigation needs BEFORE seeing results")
        max_p95_m: float = Field(gt=0)
        undistorted: bool = False
        notes: str = ""

    @app.post("/v1/cameras/{camera_id}/calibrations", status_code=201)
    def calibrate(camera_id: str, body: CalibrationRequest, p: User) -> FloorCalibration:
        p.require_role(Role.SITE_ADMIN)
        cam = get_or_404(Camera, camera_id)
        p.require_site(cam.site_id)
        version = len(svc.store.find(FloorCalibration, camera_id=camera_id)) + 1
        try:
            cal = fit_floor_calibration(
                calibration_id=new_id("calibration"), camera_id=camera_id, floor_id=cam.floor_id, version=version,
                image_points_px=body.image_points_px, floor_points_m=body.floor_points_m,
                holdout_image_points_px=body.holdout_image_points_px,
                holdout_floor_points_m=body.holdout_floor_points_m,
                thresholds=ValidationThresholds(body.max_median_m, body.max_p95_m), undistorted=body.undistorted,
                image_wh_px=body.image_wh_px,
                now=now(), notes=body.notes,
            )  # fmt: skip
        except CalibrationError as e:
            raise HTTPException(422, str(e)) from e
        svc.store.put(cal)
        audit(p, "calibrate", cal.calibration_id, state=cal.rig_state.value, p95=cal.holdout_error_p95_m)
        return cal

    class InvalidateRequest(BaseModel):
        reason: str = Field(min_length=3)

    @app.post("/v1/calibrations/{calibration_id}/invalidate")
    def invalidate_calibration(calibration_id: str, body: InvalidateRequest, p: User) -> dict:
        p.require_role(Role.SITE_ADMIN)
        cal = get_or_404(FloorCalibration, calibration_id)
        p.require_site(get_or_404(Camera, cal.camera_id).site_id)
        affected = svc.store.invalidate(calibration_id, reason=body.reason, actor=actor(p), now=now())
        return {"invalidated": affected}

    class SyncRequest(BaseModel):
        offset_ms: float
        uncertainty_ms: float = Field(ge=0)
        method: str
        anchor_description: str = ""

    @app.post("/v1/cameras/{camera_id}/clock-syncs", status_code=201)
    def clock_sync(camera_id: str, body: SyncRequest, p: User) -> ClockSync:
        p.require_role(Role.SITE_ADMIN)
        p.require_site(get_or_404(Camera, camera_id).site_id)
        sync = svc.store.put(ClockSync(sync_id=new_id("sync"), camera_id=camera_id, created_at=now(),
                                       **body.model_dump()))  # fmt: skip
        audit(p, "clock_sync", sync.sync_id)
        return sync

    # --- media ----------------------------------------------------------------------------------------------

    class UploadMeta(BaseModel):
        site_id: str
        camera_id: str
        rights_statement: str = Field(min_length=10)
        purpose: str = Field(min_length=3)
        consent_confirmed: Literal[True]
        hosted_processing_allowed: bool
        retention_days: int = Field(gt=0, le=3650)
        recording_start_camera_time: AwareDatetime | None = Field(
            default=None, description="Camera-clock time of the first frame; needed to place the clip on the timeline")
        recording_kind: Literal["staged_event", "real_incident", "synthetic_test"] = Field(
            description="What this footage is; shown verbatim as its provenance label in reports")

    @app.post("/v1/media/uploads", status_code=201)
    def upload(p: User, meta: Annotated[str, Form()], file: Annotated[UploadFile, File()]) -> dict:
        p.require_role(Role.SITE_ADMIN, Role.INVESTIGATOR)
        try:
            m = UploadMeta.model_validate_json(meta)
        except ValidationError as e:
            raise HTTPException(422, json.loads(e.json(include_url=False))) from e
        p.require_site(m.site_id)
        cam = get_or_404(Camera, m.camera_id)
        if cam.site_id != m.site_id:
            raise HTTPException(400, "camera is not on this site")
        t = now()
        auth = svc.store.put(MediaAuthorization(
            authorization_id=new_id("authorization"), site_id=m.site_id, uploader=p.user_id,
            rights_statement=m.rights_statement, purpose=m.purpose, consent_confirmed=True,
            hosted_processing_allowed=m.hosted_processing_allowed, recording_kind=m.recording_kind,
            retention_until=t + timedelta(days=m.retention_days), recorded_at=t,
        ))  # fmt: skip
        with tempfile.TemporaryDirectory() as tmp:
            # Keep only the base name; the client-supplied filename is stored as data, never used as a path.
            src = Path(tmp) / Path(file.filename or "upload.mp4").name
            with src.open("wb") as out:
                shutil.copyfileobj(file.file, out)
            try:
                r = ingest(src, store=svc.media, authorization=auth, site_id=m.site_id, camera_id=m.camera_id,
                           ingested_by=p.user_id, now=t)  # fmt: skip
            except IngestRejected as e:
                raise HTTPException(422, f"rejected: {e}") from e
        if svc.store.exists(r.original.media_id):
            existing = svc.store.get(MediaAsset, r.original.media_id)
            if (existing.site_id, existing.camera_id) != (m.site_id, m.camera_id):
                raise HTTPException(409, "identical footage is already registered to another site/camera")
        for asset in (r.original, r.proxy):
            if not svc.store.exists(asset.media_id):
                svc.store.put(asset)
        coverage = None
        has_coverage = bool(svc.store.find(CameraCoverage, media_id=r.original.media_id))
        if m.recording_start_camera_time is not None and not has_coverage:
            try:
                sync = svc.latest_sync(m.camera_id)
            except ServiceError as e:
                raise HTTPException(409, str(e)) from e
            start = m.recording_start_camera_time + timedelta(milliseconds=sync.offset_ms)
            coverage = svc.store.put(CameraCoverage(
                coverage_id=new_id("coverage"), camera_id=m.camera_id, media_id=r.original.media_id,
                start_utc=start, end_utc=start + timedelta(milliseconds=r.original_frames.pts_ms[-1]),
                sync_id=sync.sync_id, time_uncertainty_ms=sync.uncertainty_ms,
            ))  # fmt: skip
        audit(p, "upload_media", r.original.media_id, sha256=r.original.sha256, deduplicated=r.deduplicated)
        return {"media_id": r.original.media_id, "proxy_media_id": r.proxy.media_id, "sha256": r.original.sha256,
                "flags": r.original.probe.flags, "frames": len(r.original_frames.pts_ms),
                "deduplicated": r.deduplicated, "coverage_id": coverage.coverage_id if coverage else None}

    @app.get("/v1/media/{media_id}")
    def media_info(media_id: str, p: User) -> MediaAsset:
        m = get_or_404(MediaAsset, media_id)
        p.require_site(m.site_id)
        return m

    @app.get("/v1/media/{media_id}/frames/{frame_index}/link")
    def frame_link(media_id: str, frame_index: int, p: User) -> dict:
        m = get_or_404(MediaAsset, media_id)
        p.require_site(m.site_id)
        exp, sig = svc.signer.sign(f"{media_id}/{frame_index}")
        audit(p, "frame_link", media_id, frame_index=frame_index)
        return {"url": f"/v1/signed/frames/{media_id}/{frame_index}?exp={exp}&sig={sig}", "expires": exp}

    @app.get("/v1/signed/frames/{media_id}/{frame_index}")
    def signed_frame(media_id: str, frame_index: int, exp: int, sig: str) -> Response:
        svc.signer.check(f"{media_id}/{frame_index}", exp, sig)
        m = get_or_404(MediaAsset, media_id)
        r = load_result(svc.media, media_id)
        try:
            png = extract_frame(asset_path(svc.media, m), r.original_frames, frame_index)
        except (IndexError, MediaToolError) as e:
            raise HTTPException(404, str(e)) from e
        return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=60",
                                                               "X-Spoor-Asset-Kind": m.kind.value})

    @app.get("/v1/signed/annotated/{observation_id}")
    def signed_annotated(observation_id: str, exp: int, sig: str) -> Response:
        svc.signer.check(f"annotated/{observation_id}", exp, sig)
        obs = get_or_404(RawObservation, observation_id)
        m = get_or_404(MediaAsset, obs.source_frame.media_id)
        r = load_result(svc.media, m.media_id)
        png = extract_frame(asset_path(svc.media, m), r.original_frames, obs.source_frame.frame_index)
        if obs.bbox_xyxy_px is not None:
            png = annotate_png(png, obs.bbox_xyxy_px, f"{obs.label} {observation_id[-6:]}")
        return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=60",
                                                               "X-Spoor-Asset-Kind": "annotated_derivative"})

    class SegmentRequest(BaseModel):
        case_id: str | None = None
        concept: str | None = None
        instance: dict | None = Field(default=None, description="{frame_index, box_ltrb_px, positive_points_px,...}")
        on_floor_plane: bool = False

    @app.post("/v1/media/{media_id}/segment", status_code=202)
    def segment(media_id: str, body: SegmentRequest, p: User) -> dict:
        p.require_role(Role.INVESTIGATOR, Role.SITE_ADMIN)
        m = get_or_404(MediaAsset, media_id)
        p.require_site(m.site_id)
        try:
            instance = InstancePrompt(**body.instance) if body.instance else None
        except (TypeError, PromptError) as e:
            raise HTTPException(422, str(e)) from e
        if body.case_id is not None:
            if case_for(p, body.case_id).site_id != m.site_id:
                raise HTTPException(400, "media and case are on different sites")
            if instance is not None:
                p.require_role(Role.INVESTIGATOR)  # linking evidence to a case is an investigator decision

        def work(job):
            job.emit("segmenting", media_id=media_id)
            r = svc.run_perception(media_id, concept=body.concept, instance=instance, case_id=body.case_id,
                                   on_floor_plane=body.on_floor_plane)  # fmt: skip
            # An operator-selected instance is a user-verified target: link its single track to the case object.
            if body.case_id and instance is not None and len(r.tracks) == 1:
                for obj in svc.store.find(ObjectInstance, case_id=body.case_id):
                    svc.store.put(TrackAssociation(object_instance_id=obj.object_instance_id,
                                                   track_id=r.tracks[0].track_id,
                                                   status=AssociationStatus.VERIFIED_SAME_CAMERA,
                                                   reason="operator-selected instance prompt", version=1,
                                                   created_at=now(), created_by=p.user_id))  # fmt: skip
            return {"status": r.status, "message": r.message, "cache_hit": r.cache_hit,
                    "tracks": [t.model_dump(mode="json") for t in r.tracks], "observations": len(r.observations)}

        job = svc.jobs.submit("segment", p.user_id, work)
        audit(p, "segment", media_id, job_id=job.job_id, concept=body.concept)
        return {"job_id": job.job_id}

    # --- cases ---------------------------------------------------------------------------------------------------

    class CaseRequest(BaseModel):
        site_id: str
        question: str = Field(min_length=3)
        target_description: str = Field(min_length=1, max_length=120)
        camera_ids: list[str] = []
        window: TimeWindow | None = None
        identifiers: list[ParcelIdentifier] = Field(default=[], description="e.g. the missing parcel's waybill")

    @app.post("/v1/cases", status_code=201)
    def create_case(body: CaseRequest, p: User) -> dict:
        p.require_role(Role.INVESTIGATOR)
        p.require_site(body.site_id)
        case = svc.store.put(Case(case_id=new_id("case"), created_by=p.user_id, created_at=now(),
                                  **body.model_dump(exclude={"identifiers"})))  # fmt: skip
        obj = svc.store.put(ObjectInstance(object_instance_id=new_id("object_instance"), case_id=case.case_id,
                                           label=body.target_description, identifiers=body.identifiers,
                                           created_by=p.user_id, created_at=now()))  # fmt: skip
        svc.store.append_revision(case.case_id, expected_parent=None, actor=actor(p), reason="case created",
                                  changed_ids=[case.case_id, obj.object_instance_id], now=now())  # fmt: skip
        audit(p, "create_case", case.case_id)
        return {"case": case.model_dump(mode="json"), "object_instance_id": obj.object_instance_id}

    class LinkRequest(BaseModel):
        status: Literal["human_confirmed", "rejected", "candidate_cross_camera"]
        reason: str = Field(min_length=3)

    @app.post("/v1/cases/{case_id}/objects/{object_id}/tracks/{track_id}")
    def link_track(case_id: str, object_id: str, track_id: str, body: LinkRequest, p: User) -> dict:
        """Investigator confirms (or rejects) that a SAM track is the case's target object (PRD §14.1 step 6)."""
        p.require_role(Role.INVESTIGATOR)
        case = case_for(p, case_id)
        if get_or_404(ObjectInstance, object_id).case_id != case_id:
            raise HTTPException(400, "object belongs to another case")
        track = get_or_404(Track, track_id)
        if get_or_404(MediaAsset, track.media_id).site_id != case.site_id:
            raise HTTPException(400, "track footage is from another site")
        prior = latest_associations(svc.store, object_id).get(track_id)
        try:
            a = svc.store.put(TrackAssociation(object_instance_id=object_id, track_id=track_id,
                                               status=AssociationStatus(body.status), reason=body.reason,
                                               version=(prior.version + 1) if prior else 1, created_at=now(),
                                               created_by=p.user_id))  # fmt: skip
        except StoreError as e:
            raise HTTPException(409, f"concurrent update, retry: {e}") from e
        audit(p, "link_track", track_id, object_id=object_id, status=body.status)
        return a.model_dump(mode="json")

    @app.post("/v1/cases/{case_id}/investigate", status_code=202)
    def start_investigation(case_id: str, p: User) -> dict:
        p.require_role(Role.INVESTIGATOR)
        case = case_for(p, case_id)

        def work(job):
            lock = svc.case_lock(case_id)
            if not lock.acquire(blocking=False):
                job.emit("waiting for a running investigation of this case to finish")
                lock.acquire()
            try:
                job.emit("investigating", agents=svc.agent is not None)
                ctx = svc.tool_context(case)
                res = investigate(ctx, evidence_backend=svc.agent, hypothesis_backend=svc.agent)
            finally:
                lock.release()
            return {"status": res.status, "answer": res.answer, "revision_id": res.revision_id,
                    "findings": [f.finding_id for f in res.findings],
                    "hypotheses": [{"id": h.hypothesis_id, "claim": h.claim, "status": h.status.value,
                                    "reasons": h.reasons} for h in res.hypotheses],
                    "evidence_requests": res.evidence_request_ids, "rejected": res.rejected,
                    "agent_runs": res.agent_runs}  # fmt: skip

        job = svc.jobs.submit("investigate", p.user_id, work)
        audit(p, "investigate", case_id, job_id=job.job_id)
        return {"job_id": job.job_id}

    @app.get("/v1/jobs/{job_id}")
    def job_status(job_id: str, p: User) -> dict:
        job = svc.jobs.jobs.get(job_id)
        if job is None or job.owner != p.user_id:
            raise HTTPException(404, "job not found")
        return {"job_id": job.job_id, "kind": job.kind, "status": job.status, "events": job.events,
                "result": job.result, "error": job.error}

    @app.get("/v1/jobs/{job_id}/events")
    async def job_events(job_id: str, p: User) -> StreamingResponse:
        job = svc.jobs.jobs.get(job_id)
        if job is None or job.owner != p.user_id:
            raise HTTPException(404, "job not found")

        async def stream():
            sent = 0
            while True:
                while sent < len(job.events):
                    yield f"data: {json.dumps(job.events[sent], default=str)}\n\n"
                    sent += 1
                if job.done.is_set() and sent >= len(job.events):
                    yield f"event: end\ndata: {json.dumps({'status': job.status})}\n\n"
                    return
                await asyncio.sleep(0.2)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/v1/cases/{case_id}/state")
    def case_state(case_id: str, p: User) -> dict:
        case = case_for(p, case_id)
        invalid = svc.store.invalid_ids()
        objects = svc.store.find(ObjectInstance, case_id=case_id)
        return {
            "case": case.model_dump(mode="json"),
            "revision": (r.model_dump(mode="json") if (r := svc.store.head_revision(case_id)) else None),
            "objects": [{
                "object": o.model_dump(mode="json"),
                "timeline": [{"state": s.state.value, "start_ms": s.start_ms, "end_ms": s.end_ms,
                              "zone_id": s.zone_id, "camera_ids": s.camera_ids, "track_ids": s.track_ids,
                              "observation_ids": s.observation_ids} for s in
                             visibility_timeline(svc.store, o.object_instance_id)],
                "tracks": {t: a.status.value for t, a in latest_associations(svc.store, o.object_instance_id).items()},
            } for o in objects],
            "findings": [{**f.model_dump(mode="json"), "invalidated": f.finding_id in invalid}
                         for f in svc.store.find(VerifiedFinding, case_id=case_id)],
            "hypotheses": [{**h.model_dump(mode="json"),
                            "history": [c.model_dump(mode="json") for c in svc.store.status_history(h.hypothesis_id)]}
                           for h in svc.store.find(Hypothesis, case_id=case_id)],
            "evidence_requests": [r.model_dump(mode="json") for r in svc.store.find(EvidenceRequest, case_id=case_id)],
        }  # fmt: skip

    @app.get("/v1/cases/{case_id}/world-at")
    def world_at(case_id: str, time: AwareDatetime, p: User) -> dict:
        case_for(p, case_id)
        t_ms = time.timestamp() * 1000
        out = []
        for s in world_state_at(svc.store, case_id, t_ms):
            est = s.estimate
            renderer = None
            if est and est.floor_xy_m is not None:
                renderer = site_to_renderer((*est.floor_xy_m, est.height_m or 0.0))
            out.append({"object_instance_id": s.object_instance_id, "label": s.label, "visibility": s.visibility.value,
                        "evidence_label": s.evidence_label.value, "spatial_mode": s.spatial_mode.value,
                        "last_observation_id": s.last_observation_id, "last_seen_ms": s.last_seen_ms,
                        "floor_xy_m": est.floor_xy_m if est else None, "zone_id": est.zone_id if est else None,
                        "uncertainty_radius_m": est.uncertainty_radius_m if est else None,
                        "renderer_xyz_y_up": renderer})  # fmt: skip
        return {"time": time.isoformat(), "objects": out}

    @app.get("/v1/cases/{case_id}/evidence/{observation_id}")
    def evidence(case_id: str, observation_id: str, p: User) -> dict:
        case_for(p, case_id)
        obs = get_or_404(RawObservation, observation_id)
        media = get_or_404(MediaAsset, obs.source_frame.media_id)
        p.require_site(media.site_id)
        est = estimate_for(svc.store, observation_id)
        exp, sig = svc.signer.sign(f"{media.media_id}/{obs.source_frame.frame_index}")
        audit(p, "view_evidence", observation_id)
        return {"observation": obs.model_dump(mode="json"), "invalidated": svc.store.is_invalid(observation_id),
                "estimate": est.model_dump(mode="json") if est else None,
                "media": {"media_id": media.media_id, "sha256": media.sha256, "kind": media.kind.value,
                          "flags": media.probe.flags if media.probe else []},
                "frame_url": f"/v1/signed/frames/{media.media_id}/{obs.source_frame.frame_index}?exp={exp}&sig={sig}",
                "annotated_frame_url": "/v1/signed/annotated/{}?exp={}&sig={}".format(
                    observation_id, *svc.signer.sign(f"annotated/{observation_id}")),
                "asset_label": "original"}  # fmt: skip

    class GapRequest(BaseModel):
        object_instance_id: str
        start: AwareDatetime
        end: AwareDatetime

    @app.post("/v1/cases/{case_id}/unobserved")
    def unobserved(case_id: str, body: GapRequest, p: User) -> list[dict]:
        case_for(p, case_id)
        if get_or_404(ObjectInstance, body.object_instance_id).case_id != case_id:
            raise HTTPException(404, "object not in this case")
        gaps = unobserved_intervals(svc.store, body.object_instance_id, body.start.timestamp() * 1000,
                                    body.end.timestamp() * 1000)  # fmt: skip
        return [g.__dict__ for g in gaps]

    @app.post("/v1/cases/{case_id}/evidence/import", status_code=201)
    def import_sensor_log(case_id: str, p: User, file: Annotated[UploadFile, File()],
                          batch: Annotated[str, Form()]) -> dict:  # fmt: skip
        """Import a sensor CSV (PRD §20.3). Rows must declare real vs simulated; see spoor.sensors."""
        from spoor.sensors import SensorImportError, parse_sensor_csv

        p.require_role(Role.INVESTIGATOR, Role.SITE_ADMIN)
        case = case_for(p, case_id)
        try:
            events = parse_sensor_csv(file.file.read().decode("utf-8"), import_batch=batch, site_id=case.site_id)
        except SensorImportError as e:
            raise HTTPException(422, str(e)) from e
        svc.store.put_many(events)
        audit(p, "import_sensor_log", case_id, count=len(events), batch=batch)
        return {"imported": [e.sensor_event_id for e in events],
                "simulated": sum(e.source_type.value == "sensor_simulated" for e in events)}

    @app.get("/v1/sites/{site_id}/sensor-events")
    def list_sensor_events(site_id: str, p: User) -> list[SensorEvent]:
        p.require_site(site_id)
        return svc.store.find(SensorEvent, site_id=site_id)

    @app.get("/v1/cases/{case_id}/replay")
    def case_replay(case_id: str, p: User, max_points: int = 120) -> dict:
        """Render-ready paths: solid = observed within one camera track, dashed = hypothesized, grey = unknown."""
        case_for(p, case_id)
        return replay(svc.store, case_id, max_points_per_segment=max(2, min(max_points, 2000)))

    @app.get("/v1/cases/{case_id}/diff")
    def diff(case_id: str, p: User, from_revision: str | None = None, to_revision: str | None = None) -> dict:
        """What changed between two revisions — e.g. after importing another camera (PRD §19.3)."""
        case_for(p, case_id)
        try:
            return case_diff(svc.store, case_id, from_revision, to_revision).as_dict()
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

    @app.get("/v1/operator/cases/{case_id}/trace")
    def operator_trace(case_id: str, p: User) -> dict:
        """Operator/judge view (PRD §23): every model call, its cost units, and the agent causal chain."""
        p.require_role(Role.SITE_ADMIN, Role.REVIEWER)
        case_for(p, case_id)
        costs = svc.store.find(CostEntry, case_id=case_id)
        steps = svc.store.find(AgentStep, case_id=case_id)
        by_model: dict[str, dict] = {}
        for c in costs:
            m = by_model.setdefault(f"{c.provider}:{c.model}", {"calls": 0, "cache_hits": 0, "input_tokens": 0,
                                                               "output_tokens": 0, "billed_frames": 0, "errors": 0})
            m["calls"] += not c.cache_hit
            m["cache_hits"] += c.cache_hit
            m["input_tokens"] += c.input_tokens
            m["output_tokens"] += c.output_tokens
            m["billed_frames"] += c.billed_units if c.unit == "frames" else 0
            m["errors"] += c.outcome != "ok"
        return {"models": by_model,
                "calls": [c.model_dump(mode="json") for c in costs],
                "agent_steps": [{"request_id": s.request_id, "seq": s.seq, "role": s.role, "kind": s.kind,
                                 "content": s.content, "at": s.at.isoformat()} for s in steps]}  # fmt: skip

    # --- parcels & scans (parcel-hub pivot) ------------------------------------------------------------------------

    class ClockDomainRequest(BaseModel):
        kind: Literal["wcs_plc", "handheld_fleet", "nvr", "camera", "rfid", "other"]
        name: str = Field(min_length=1)
        device_ids: list[str] = []
        camera_ids: list[str] = []

    @app.post("/v1/sites/{site_id}/clock-domains", status_code=201)
    def create_clock_domain(site_id: str, body: ClockDomainRequest, p: User) -> ClockDomain:
        p.require_role(Role.SITE_ADMIN)
        p.require_site(site_id)
        get_or_404(Site, site_id)
        d = svc.store.put(ClockDomain(clock_domain_id=new_id("clock_domain"), site_id=site_id, **body.model_dump()))
        audit(p, "create_clock_domain", d.clock_domain_id)
        return d

    class AnchorIn(BaseModel):
        device_time: AwareDatetime
        reference_time: AwareDatetime
        anchor_id: str = ""

    class ClockFitRequest(BaseModel):
        anchors: list[AnchorIn] = Field(min_length=3)
        fit_drift: bool | None = None
        base_uncertainty_ms: float = Field(default=0.0, ge=0, description="Timing uncertainty of the anchors themselves")
        description: str = ""

    @app.post("/v1/clock-domains/{clock_domain_id}/fit", status_code=201)
    def fit_domain_clock(clock_domain_id: str, body: ClockFitRequest, p: User) -> dict:
        """Fit a domain's offset/drift from matched anchor events (e.g. tunnel passages seen by a camera)."""
        p.require_role(Role.SITE_ADMIN)
        p.require_site(get_or_404(ClockDomain, clock_domain_id).site_id)
        try:
            fit = fit_clock([AnchorPair(a.device_time, a.reference_time, a.anchor_id) for a in body.anchors],
                            fit_drift=body.fit_drift)  # fmt: skip
        except ClockFitError as e:
            raise HTTPException(422, str(e)) from e
        sync = svc.store.put(sync_from_fit(fit, clock_domain_id=clock_domain_id,
                                           base_uncertainty_ms=body.base_uncertainty_ms, now=now(),
                                           anchor_description=body.description))  # fmt: skip
        audit(p, "fit_clock", clock_domain_id, sync_id=sync.sync_id, rejected=list(fit.rejected_anchor_ids))
        return {"sync": sync.model_dump(mode="json"), "n_used": fit.n_used, "n_rejected": fit.n_rejected,
                "rejected_anchor_ids": list(fit.rejected_anchor_ids)}

    @app.post("/v1/sites/{site_id}/scans/import", status_code=201)
    def import_scans(site_id: str, p: User, file: Annotated[UploadFile, File()], batch: Annotated[str, Form()],
                     source: Annotated[Literal["real", "simulated"], Form()]) -> dict:  # fmt: skip
        """Import a JSONL scan log. `source` is mandatory: simulated logs stay labelled end to end."""
        p.require_role(Role.SITE_ADMIN, Role.INVESTIGATOR)
        p.require_site(site_id)
        get_or_404(Site, site_id)
        try:
            scans = parse_scan_jsonl(file.file.read().decode("utf-8"), site_id=site_id, import_batch=batch,
                                     source=source, now=now())  # fmt: skip
            for s in scans:
                if s.clock_domain_id and get_or_404(ClockDomain, s.clock_domain_id).site_id != site_id:
                    raise ScanImportError(f"clock domain {s.clock_domain_id} belongs to another site")
            summary = ingest_scans(svc.store, scans, now=now())
        except ScanImportError as e:
            raise HTTPException(422, str(e)) from e
        except StoreError as e:
            raise HTTPException(409, str(e)) from e
        audit(p, "import_scans", site_id, batch=batch, source=source, count=len(summary.scans))
        return {"imported": len(summary.scans), "skipped_exact_duplicates": summary.skipped_exact_duplicates,
                "memberships_opened": len(summary.memberships_opened),
                "memberships_closed": len(summary.memberships_closed), "aliases": len(summary.aliases)}

    @app.get("/v1/sites/{site_id}/parcels/{scheme}/{value}")
    def parcel_lookup(site_id: str, scheme: str, value: str, p: User, sla_hours: float = 6.0) -> dict:
        """Everything the scan evidence says about one parcel at this site: aliases, timeline, visit state, containers."""
        p.require_site(site_id)
        try:
            ident = ParcelIdentifier(scheme=scheme, value=value)
        except ValidationError as e:
            raise HTTPException(422, "unknown identifier scheme") from e
        keys = resolve_identity(svc.store, {ident.key})
        timeline = scans_for(svc.store, keys)
        here = [t for t in timeline.scans if t.scan.site_id == site_id]
        visit = facility_visit(svc.store, site_id, keys, now=now(), sla=timedelta(hours=sla_hours))
        chain = container_chain(svc.store, ident.key, here[-1].t) if here else []
        audit(p, "parcel_lookup", None, key=ident.key)
        return {
            "identifier": ident.model_dump(mode="json"), "aliases": sorted(keys - {ident.key}),
            "visit": {"status": visit.status, "label": visit.label.value, "closed_by": visit.closed_by,
                      "opened_at": visit.opened_by.t.isoformat() if visit.opened_by else None, "notes": visit.notes},
            "scans": [{"scan_event_id": t.scan.scan_event_id, "site_id": t.scan.site_id,
                       "event_kind": t.scan.event_kind.value, "time": t.t.isoformat(), "synced": t.synced,
                       "time_uncertainty_ms": t.unc_ms, "device_id": t.scan.device_id,
                       "device_kind": t.scan.device_kind.value, "station_id": t.scan.station_id,
                       "zone_id": t.scan.read_point_zone_id, "late_upload": t.late_upload,
                       "source_type": t.scan.source_type.value, "read_outcome": t.scan.read_outcome.value,
                       "raw_code": t.scan.raw_code, "raw_description": t.scan.raw_description,
                       "sort_destination_actual": t.scan.sort_destination_actual}
                      for t in timeline.scans if t.scan.site_id == site_id],
            "container_chain": [{"container": m.parent_key, "since": m.valid_from.isoformat(),
                                 "until": m.valid_to.isoformat() if m.valid_to else None, "basis": m.basis,
                                 "label": "estimated"} for m in chain],
            "excluded": {"corrected": timeline.dropped_corrected, "duplicates": timeline.dropped_duplicates},
        }  # fmt: skip

    # --- review & reports -------------------------------------------------------------------------------------------

    class ReviewRequest(BaseModel):
        hypothesis_id: str
        to_status: Literal["supported", "contradicted", "insufficient_evidence", "evaluated"]
        evidence_ids: list[str] = []
        reason: str = Field(min_length=5)

    @app.post("/v1/cases/{case_id}/review")
    def review(case_id: str, body: ReviewRequest, p: User) -> dict:
        """A reviewer contests or decides a hypothesis. Recorded as an append-only human status change."""
        p.require_role(Role.REVIEWER)
        case_for(p, case_id)
        h = get_or_404(Hypothesis, body.hypothesis_id)
        if h.case_id != case_id:
            raise HTTPException(400, "hypothesis belongs to another case")
        current = svc.store.hypothesis_status(h.hypothesis_id)
        try:
            chain = []
            if body.to_status != "evaluated" and current != HypothesisStatus.EVALUATED:
                chain.append(HypothesisStatus.EVALUATED)
            chain.append(HypothesisStatus(body.to_status))
            changes, frm = [], current
            for to in chain:
                changes.append(HypothesisStatusChange(
                    change_id=new_id("status_change"), hypothesis_id=h.hypothesis_id, from_status=frm, to_status=to,
                    actor=actor(p), evidence_ids=body.evidence_ids if to == chain[-1] else [], reason=body.reason,
                    at=now()))  # fmt: skip
                frm = to
            svc.store.change_status_chain(changes)
            current = chain[-1]
        except (StoreError, ValueError) as e:
            raise HTTPException(409, str(e)) from e
        audit(p, "review_hypothesis", h.hypothesis_id, to=body.to_status, reason=body.reason)
        return {"hypothesis_id": h.hypothesis_id, "status": current.value}

    @app.post("/v1/cases/{case_id}/export", status_code=201)
    def export(case_id: str, p: User) -> dict:
        p.require_role(Role.INVESTIGATOR, Role.REVIEWER)
        case = case_for(p, case_id)
        report = build_report(svc.store, case_id, site=svc.site(case.site_id), now=now())
        rec = svc.store.put(ReportRecord(report_id=new_id("report"), case_id=case_id,
                                         case_revision_id=report["case_revision_id"], sha256=canonical_sha256(report),
                                         status="draft", content=report, at=now()))  # fmt: skip
        audit(p, "export_report", rec.report_id, sha256=rec.sha256)
        return {"report_id": rec.report_id, "status": "draft", "manifest": manifest(report)}

    @app.post("/v1/reports/{report_id}/approve", status_code=201)
    def approve(report_id: str, p: User) -> dict:
        p.require_role(Role.REVIEWER)
        draft = get_or_404(ReportRecord, report_id)
        case_for(p, draft.case_id)
        if draft.status != "draft":
            raise HTTPException(409, "only drafts can be approved")
        creator = [a for a in svc.store.find(AuditEntry, target_id=report_id) if a.action == "export_report"]
        if creator and creator[0].actor.id == p.user_id:
            raise HTTPException(403, "a reviewer cannot approve a report they exported")
        head = svc.store.head_revision(draft.case_id)
        if head and head.case_revision_id != draft.case_revision_id:
            raise HTTPException(409, "case changed since this draft; export a new draft")
        case = get_or_404(Case, draft.case_id)
        fresh = build_report(svc.store, draft.case_id, site=svc.site(case.site_id), now=now())
        if content_fingerprint(fresh) != content_fingerprint(draft.content):
            raise HTTPException(409, "evidence changed since this draft (e.g. purge, review, invalidation); "
                                     "export a new draft")
        approved = svc.store.put(ReportRecord(report_id=new_id("report"), case_id=draft.case_id,
                                              case_revision_id=draft.case_revision_id, sha256=draft.sha256,
                                              approved_by=p.user_id, status="approved", content=draft.content,
                                              at=now()))  # fmt: skip
        audit(p, "approve_report", approved.report_id, draft=report_id, sha256=draft.sha256)
        return {"report_id": approved.report_id, "status": "approved", "sha256": approved.sha256}

    @app.get("/v1/reports/{report_id}")
    def get_report(report_id: str, p: User, format: Literal["json", "html"] = "json"):
        rec = get_or_404(ReportRecord, report_id)
        case_for(p, rec.case_id)
        if format == "html":
            return HTMLResponse(render_html(rec.content, status=rec.status, approved_by=rec.approved_by))
        return {"report_id": rec.report_id, "status": rec.status, "approved_by": rec.approved_by,
                "sha256": rec.sha256, "manifest": manifest(rec.content), "content": rec.content}

    # --- deletion --------------------------------------------------------------------------------------------------

    @app.delete("/v1/cases/{case_id}")
    def delete_case(case_id: str, p: User) -> dict:
        p.require_role(Role.SITE_ADMIN)
        case_for(p, case_id)
        svc.store.delete_case(case_id, actor=actor(p), now=now())
        return {"deleted": case_id}

    class PurgeRequest(BaseModel):
        reason: str = Field(min_length=3)

    @app.post("/v1/media/{media_id}/purge")
    def purge(media_id: str, body: PurgeRequest, p: User) -> dict:
        p.require_role(Role.SITE_ADMIN)
        m = get_or_404(MediaAsset, media_id)
        p.require_site(m.site_id)
        if m.kind.value != "original":
            raise HTTPException(400, "purge the original; derivatives follow")
        derived = svc.store.find(MediaAsset, parent_id=media_id)
        shas = svc.store.purge_media(media_id, actor=actor(p), reason=body.reason, now=now())
        for sha in shas:
            svc.media.delete_file(svc.media.original_path(sha))
            svc.media.delete_file(svc.media.derivative_path(sha, ".mp4"))
        removed = svc.purge_sidecars([media_id, *(d.media_id for d in derived)], [*shas])
        return {"purged_media": media_id, "files_deleted": len(shas) + removed}

    @app.get("/v1/evaluations")
    def evaluations(p: User) -> dict:
        p.require_role(Role.SITE_ADMIN)
        path = Path(svc.settings.data_dir) / "evaluation" / "latest.json"
        if not path.exists():
            return {"status": "no_results", "note": "run ml/evaluation/run.py to produce results"}
        return json.loads(path.read_text(encoding="utf-8"))

    # --- workspace read models (web frontend, PRD §19) -----------------------------------------------------------
    # Read-only views over stored records. Nothing here derives new evidence; it only lists and resolves what exists.

    @app.get("/v1/me")
    def me(p: User) -> dict:
        return {"user_id": p.user_id, "role": p.role.value, "site_ids": sorted(p.site_ids)}

    @app.get("/v1/capabilities")
    def capabilities(p: User) -> dict:
        """Which model-backed steps can run. The UI shows "analysis unavailable" for the rest (PRD §24.1)."""
        return {"sam": svc.sam is not None, "spark": svc.spark is not None, "agents": svc.agent is not None,
                "agent_backend": svc.settings.agent_backend,
                "multiview_xyz": svc.settings.enable_multiview_xyz,
                "cross_camera_association": svc.settings.enable_cross_camera_association,
                # The one site -> renderer axis transform (PRD §13.5); the web scene applies exactly this matrix.
                "site_frame": SITE_FRAME, "site_to_renderer": SITE_TO_RENDERER.tolist()}  # fmt: skip

    @app.get("/v1/sites")
    def list_sites(p: User) -> list[Site]:
        return [svc.store.get(Site, s) for s in sorted(p.site_ids) if svc.store.exists(s)]

    @app.get("/v1/sites/{site_id}")
    def get_site(site_id: str, p: User) -> Site:
        p.require_site(site_id)
        return get_or_404(Site, site_id)

    def _sync_view(s: ClockSync | None) -> dict | None:
        if s is None:
            return None
        return {"sync_id": s.sync_id, "offset_ms": s.offset_ms, "drift_ppm": s.drift_ppm,
                "uncertainty_ms": s.uncertainty_ms, "method": s.method, "anchor_count": len(s.anchor_event_ids),
                "residual_ms_p95": s.residual_ms_p95, "created_at": s.created_at.isoformat()}  # fmt: skip

    @app.get("/v1/sites/{site_id}/cameras")
    def list_cameras(site_id: str, p: User) -> list[dict]:
        """Cameras with their latest clock sync, calibration state and recorded coverage."""
        p.require_site(site_id)
        out = []
        for cam in svc.store.find(Camera, site_id=site_id):
            syncs = svc.store.find(ClockSync, camera_id=cam.camera_id)
            cals = svc.store.find(FloorCalibration, camera_id=cam.camera_id)
            cal = cals[-1] if cals else None
            out.append({
                "camera": cam.model_dump(mode="json"),
                "clock_sync": _sync_view(syncs[-1] if syncs else None),
                "calibration": None if cal is None else {
                    "calibration_id": cal.calibration_id, "rig_state": cal.rig_state.value, "version": cal.version,
                    "holdout_error_median_m": cal.holdout_error_median_m,
                    "holdout_error_p95_m": cal.holdout_error_p95_m,
                    "invalidated": svc.store.is_invalid(cal.calibration_id)},
                "coverage": [{"coverage_id": c.coverage_id, "media_id": c.media_id, "start_utc": c.start_utc.isoformat(),
                              "end_utc": c.end_utc.isoformat(), "sync_id": c.sync_id,
                              "time_uncertainty_ms": c.time_uncertainty_ms}
                             for c in svc.store.find(CameraCoverage, camera_id=cam.camera_id)],
            })  # fmt: skip
        return out

    @app.get("/v1/sites/{site_id}/media")
    def list_media(site_id: str, p: User) -> list[dict]:
        """Original clips with provenance and timeline placement. Derivatives are reached through their original."""
        p.require_site(site_id)
        out = []
        for m in svc.store.find(MediaAsset, site_id=site_id, kind="original"):
            auth = svc.store.get(MediaAuthorization, m.authorization_id)
            covs = svc.store.find(CameraCoverage, media_id=m.media_id)
            out.append({"media": m.model_dump(mode="json"), "recording_kind": auth.recording_kind,
                        "purged": svc.store.is_invalid(m.media_id),
                        "coverage": [{"start_utc": c.start_utc.isoformat(), "end_utc": c.end_utc.isoformat(),
                                      "time_uncertainty_ms": c.time_uncertainty_ms, "sync_id": c.sync_id}
                                     for c in covs]})  # fmt: skip
        return out

    @app.get("/v1/media/{media_id}/frame-at")
    def frame_at(media_id: str, time: AwareDatetime, p: User) -> dict:
        """The frame of this clip shown at a normalized time (e.g. a scan time). Context only: the frame is not an
        observation of anything until someone or something observes it."""
        m = get_or_404(MediaAsset, media_id)
        p.require_site(m.site_id)
        covs = svc.store.find(CameraCoverage, media_id=media_id)
        if not covs:
            raise HTTPException(409, "clip has no recorded start time, so it cannot be placed on the timeline")
        cov = covs[-1]
        if not cov.start_utc <= time <= cov.end_utc:
            raise HTTPException(404, "time is outside this clip")
        table = load_result(svc.media, media_id).original_frames
        rel_ms = (time - cov.start_utc).total_seconds() * 1000
        idx = min(range(len(table.pts_ms)), key=lambda i: abs(table.pts_ms[i] - rel_ms))
        exp, sig = svc.signer.sign(f"{media_id}/{idx}")
        audit(p, "frame_at", media_id, frame_index=idx)
        return {"media_id": media_id, "camera_id": m.camera_id, "frame_index": idx, "pts_ms": table.pts_ms[idx],
                "delta_ms": table.pts_ms[idx] - rel_ms, "time_uncertainty_ms": cov.time_uncertainty_ms,
                "frame_count": len(table.pts_ms),
                "frame_url": f"/v1/signed/frames/{media_id}/{idx}?exp={exp}&sig={sig}",
                "label": "context frame at the requested time; not an observation"}  # fmt: skip

    @app.get("/v1/sites/{site_id}/clock-domains")
    def list_clock_domains(site_id: str, p: User) -> list[dict]:
        p.require_site(site_id)
        out = []
        for d in svc.store.find(ClockDomain, site_id=site_id):
            syncs = svc.store.find(ClockSync, clock_domain_id=d.clock_domain_id)
            out.append({"domain": d.model_dump(mode="json"), "sync": _sync_view(syncs[-1] if syncs else None)})
        return out

    @app.get("/v1/sites/{site_id}/scans")
    def list_scans(site_id: str, p: User, start: AwareDatetime | None = None, end: AwareDatetime | None = None,
                   limit: int = 2000) -> dict:  # fmt: skip
        """Scan events at this site on the normalized timeline, each with its own time uncertainty."""
        p.require_site(site_id)
        scans = svc.store.find(ScanEvent, site_id=site_id)
        cache: dict = {}
        rows = []
        for ts in sorted((timed(svc.store, s, cache) for s in scans), key=lambda t: t.t):
            if (start and ts.t < start) or (end and ts.t > end):
                continue
            s = ts.scan
            rows.append({"scan_event_id": s.scan_event_id, "time": ts.t.isoformat(), "synced": ts.synced,
                         "time_uncertainty_ms": ts.unc_ms, "event_kind": s.event_kind.value,
                         "read_outcome": s.read_outcome.value, "identity_keys": s.identity_keys,
                         "device_id": s.device_id, "device_kind": s.device_kind.value, "station_id": s.station_id,
                         "zone_id": s.read_point_zone_id, "sort_destination_actual": s.sort_destination_actual,
                         "raw_code": s.raw_code, "raw_description": s.raw_description,
                         "source_type": s.source_type.value, "import_batch": s.import_batch})  # fmt: skip
        return {"total": len(rows), "scans": rows[: max(1, min(limit, 20000))]}

    @app.get("/v1/cases")
    def list_cases(p: User, site_id: str | None = None) -> list[dict]:
        sites = [site_id] if site_id else sorted(p.site_ids)
        if site_id:
            p.require_site(site_id)
        out = []
        for s in sites:
            for c in svc.store.find(Case, site_id=s):
                head = svc.store.head_revision(c.case_id)
                reports = svc.store.find(ReportRecord, case_id=c.case_id)
                out.append({"case": c.model_dump(mode="json"),
                            "revision_at": head.at.isoformat() if head else None,
                            "report_status": reports[-1].status if reports else None})  # fmt: skip
        return sorted(out, key=lambda r: r["case"]["created_at"], reverse=True)

    @app.get("/v1/cases/{case_id}/last-seen")
    def last_seen(case_id: str, p: User) -> list[dict]:
        """Graded last seen per case object: fixed scan > handheld scan > video on a confirmed track. Leads
        (inherited container location, candidate video) are returned separately and are never 'last seen'."""
        case_for(p, case_id)

        def view(s) -> dict:
            return {"class": s.klass, "time": s.t.isoformat(), "label": s.label.value, "evidence_id": s.evidence_id,
                    "where": s.where, "time_uncertainty_ms": s.unc_ms}

        out = []
        for o in svc.store.find(ObjectInstance, case_id=case_id):
            g = graded_last_seen(svc.store, o.object_instance_id)
            out.append({"object_instance_id": o.object_instance_id, "label": o.label,
                        "last_confident": view(g.last_confident) if g.last_confident else None,
                        "confident": [view(s) for s in g.confident], "leads": [view(s) for s in g.leads]})
        return out

    @app.get("/v1/cases/{case_id}/reports")
    def list_reports(case_id: str, p: User) -> list[dict]:
        case_for(p, case_id)
        return [{"report_id": r.report_id, "status": r.status, "sha256": r.sha256, "approved_by": r.approved_by,
                 "case_revision_id": r.case_revision_id, "at": r.at.isoformat()}
                for r in svc.store.find(ReportRecord, case_id=case_id)]  # fmt: skip

    return app

