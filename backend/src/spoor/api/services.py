"""Service wiring: storage, provider clients, and the paid tools agents may call (PRD §24 modular monolith)."""

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from spoor.agents import ToolContext
from spoor.config import Settings
from spoor.contracts import (
    AssociationStatus,
    Camera,
    CameraCoverage,
    Case,
    ClockSync,
    EvidenceScope,
    FloorCalibration,
    MediaAsset,
    MediaAuthorization,
    ObjectInstance,
    RigState,
    Site,
    TimeWindow,
)
from spoor.ingest import MediaStore, asset_path, load_result
from spoor.perception import MetaSamBackend, PerceptionRequest, SamBackend, track_target
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
                       on_floor_plane: bool = False):  # fmt: skip
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
        )  # fmt: skip
        result = asyncio.run(track_target(req, backend=self.sam, store=self.store,
                                          cache_dir=self.settings.data_dir / "inference_cache"))  # fmt: skip
        return result

    def tool_context(self, case: Case) -> ToolContext:
        site = self.site(case.site_id)
        window = None
        if case.window:
            window = TimeWindow(start_utc=case.window.start_utc, end_utc=case.window.end_utc)
        ctx = ToolContext(store=self.store, site=site, case=case, verifier=Verifier(self.store, site),
                          scope=EvidenceScope(camera_ids=case.camera_ids, window=window))  # fmt: skip

        def run_sam(media_id: str, concept: str) -> dict:
            try:
                r = self.run_perception(media_id, concept=concept, case_id=case.case_id)
            except ServiceError as e:
                return {"status": "analysis_unavailable", "reason": str(e)}
            return {"status": r.status, "message": r.message, "cache_hit": r.cache_hit,
                    "tracks": [{"track_id": t.track_id, "frames": [t.first_frame_index, t.last_frame_index]}
                               for t in r.tracks],
                    "note": "new tracks are NOT linked to the case object until an investigator confirms them"}

        def ask_spark(media_id: str, start_s: float, end_s: float, template: str) -> dict:
            if self.spark is None or self.spark_client is None:
                return {"status": "analysis_unavailable", "reason": "Muse Spark not configured"}
            original = self.store.get(MediaAsset, media_id)
            ing = load_result(self.media, media_id)
            t0 = ing.proxy_frames.pts_ms[0]
            window = cut_clip(asset_path(self.media, ing.proxy), ing.proxy_frames, source_media_id=media_id,
                              start_ms=t0 + start_s * 1000, end_ms=t0 + end_s * 1000,
                              out_dir=self.settings.data_dir / "clips")  # fmt: skip
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
                    "uninspected_ms": res.uninspected,
                    "note": "facts are proposals; only 'grounded' ones match SAM observations"}  # fmt: skip

        ctx.run_sam, ctx.ask_spark = run_sam, ask_spark
        return ctx


def utcnow() -> datetime:
    return datetime.now(UTC)


CONFIRM_STATUSES = {AssociationStatus.HUMAN_CONFIRMED, AssociationStatus.VERIFIED_SAME_CAMERA,
                    AssociationStatus.REJECTED, AssociationStatus.CANDIDATE_CROSS_CAMERA}  # fmt: skip
