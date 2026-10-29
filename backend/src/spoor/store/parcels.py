"""Parcel queries over scan evidence (parcel-hub pivot). Deterministic; no model calls.

Key ideas from the parcel-hub research:
- A parcel gets only a few item scans per hub visit; between them its location is unknown or inherited from a bag,
  cage or trailer. Inherited location is a presumption "until contradicted" (EPCIS) and is labelled estimated.
- "Scanned in but never out" is an open facility visit with explicit closure rules, checked against relabels
  (aliases), duplicates, late uploads and the downstream breakdown of the container.
- Device clocks differ; every scan time is normalized through its clock domain's fitted sync, with uncertainty.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import or_, select

from spoor.contracts import (
    VISIT_OPENING,
    ClockSync,
    ContainerMembership,
    DeviceKind,
    EvidenceLabel,
    IdentifierAlias,
    LinkStatus,
    ObjectInstance,
    ScanEvent,
    ScanEventKind,
)

from . import db
from .queries import last_confirmed, object_evidence
from .repository import EvidenceStore

DEFAULT_DEDUPE_MS = 2_000
LATE_UPLOAD_FLAG_MS = 5 * 60_000  # record_time - device_time beyond this marks a batch-synced (handheld) upload


# --- identity --------------------------------------------------------------------------------------------------------


def resolve_identity(store: EvidenceStore, keys: list[str] | set[str]) -> set[str]:
    """All identifier keys denoting the same physical parcel: closure over ACTIVE aliases, in both directions."""
    seen, queue = set(keys), deque(keys)
    while queue:
        k = queue.popleft()
        with store.engine.connect() as c:
            rows = c.execute(select(db.aliases.c.payload).where(or_(db.aliases.c.from_key == k,
                                                                      db.aliases.c.to_key == k)))  # fmt: skip
            aliases = [IdentifierAlias.model_validate_json(p) for (p,) in rows]
        for a in aliases:
            if a.status != "active":
                continue
            for other in (a.from_key, a.to_key):
                if other not in seen:
                    seen.add(other)
                    queue.append(other)
    return seen


def object_keys(store: EvidenceStore, object_instance_id: str) -> set[str]:
    obj = store.get(ObjectInstance, object_instance_id)
    return resolve_identity(store, {i.key for i in obj.identifiers if i.usable_for_identity})


# --- time --------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TimedScan:
    scan: ScanEvent
    t: datetime  # normalized when a sync exists, otherwise the raw device time
    synced: bool
    unc_ms: float | None
    sync_id: str | None
    late_upload: bool

    @property
    def t_ms(self) -> float:
        return self.t.timestamp() * 1000.0


def sync_for_domain(store: EvidenceStore, clock_domain_id: str, at: datetime) -> ClockSync | None:
    syncs = [s for s in store.find(ClockSync, clock_domain_id=clock_domain_id) if s.covers(at)]
    return syncs[-1] if syncs else None


def timed(store: EvidenceStore, scan: ScanEvent, _cache: dict | None = None) -> TimedScan:
    sync = None
    if scan.clock_domain_id:
        key = (scan.clock_domain_id, scan.device_time_utc)
        if _cache is not None and key in _cache:
            sync = _cache[key]
        else:
            sync = sync_for_domain(store, scan.clock_domain_id, scan.device_time_utc)
            if _cache is not None:
                _cache[key] = sync
    t = scan.device_time_utc + timedelta(milliseconds=sync.correction_ms(scan.device_time_utc)) if sync \
        else scan.device_time_utc  # fmt: skip
    late = scan.record_time_utc is not None and \
        (scan.record_time_utc - scan.device_time_utc).total_seconds() * 1000 > LATE_UPLOAD_FLAG_MS  # fmt: skip
    return TimedScan(scan, t, sync is not None, sync.uncertainty_ms if sync else None,
                     sync.sync_id if sync else None, late)  # fmt: skip


# --- scan timeline ----------------------------------------------------------------------------------------------------


@dataclass
class ScanTimeline:
    scans: list[TimedScan]
    keys: set[str]
    dropped_corrected: list[str] = field(default_factory=list)
    dropped_duplicates: list[str] = field(default_factory=list)
    unsynced: list[str] = field(default_factory=list)


def scans_for(store: EvidenceStore, keys: set[str], *, site_id: str | None = None,
              dedupe_ms: float = DEFAULT_DEDUPE_MS, resolve: bool = True) -> ScanTimeline:  # fmt: skip
    keys = resolve_identity(store, keys) if resolve else set(keys)
    raw = store.get_many(ScanEvent, store.scan_ids_for_keys(keys))
    if site_id is not None:
        raw = [s for s in raw if s.site_id == site_id]
    ids = [s.scan_event_id for s in raw]
    corrections = store.find(ScanEvent, corrects_id=ids) if ids else []
    corrected = {c.corrects_scan_event_id for c in corrections}
    # A correction with did_not_occur only retracts; with incorrect_data it replaces the original.
    replacements = [c for c in corrections if c.correction_reason == "incorrect_data"]
    timeline = ScanTimeline([], keys, dropped_corrected=sorted(corrected))
    cache: dict = {}
    candidates = [s for s in raw if s.scan_event_id not in corrected and s.corrects_scan_event_id is None]
    candidates += [r for r in replacements if set(r.identity_keys) & keys]
    out: list[TimedScan] = []
    for s in sorted((timed(store, s, cache) for s in candidates), key=lambda t: (t.t, t.scan.scan_event_id)):
        # UPU-style dedup: same identity, event kind and read point within a short tolerance.
        dup = next((o for o in reversed(out[-10:])
                    if o.scan.event_kind == s.scan.event_kind and o.scan.device_id == s.scan.device_id
                    and set(o.scan.identity_keys) & set(s.scan.identity_keys)
                    and abs(o.t_ms - s.t_ms) <= dedupe_ms), None)  # fmt: skip
        if dup is not None:
            timeline.dropped_duplicates.append(s.scan.scan_event_id)
            continue
        if not s.synced:
            timeline.unsynced.append(s.scan.scan_event_id)
        out.append(s)
    timeline.scans = out
    return timeline


# --- containers ------------------------------------------------------------------------------------------------------


def memberships_of(store: EvidenceStore, child_key: str) -> list[ContainerMembership]:
    """Latest version of every membership where `child_key` is the child."""
    latest: dict[str, ContainerMembership] = {}
    for m in store.find(ContainerMembership, child_key=child_key):
        if m.membership_id not in latest or m.version > latest[m.membership_id].version:
            latest[m.membership_id] = m
    return sorted(latest.values(), key=lambda m: m.valid_from)


def container_chain(store: EvidenceStore, key: str, at: datetime) -> list[ContainerMembership]:
    """parcel -> bag -> cage -> trailer memberships holding at time `at` (contradicted/retracted links excluded)."""
    chain: list[ContainerMembership] = []
    current, seen = key, {key}
    while True:
        holding = [m for m in memberships_of(store, current)
                   if m.status in (LinkStatus.ACTIVE, LinkStatus.CLOSED) and m.valid_from <= at
                   and (m.valid_to is None or at <= m.valid_to)]  # fmt: skip
        if not holding:
            return chain
        m = holding[-1]
        if m.parent_key in seen:  # defensive: never loop on bad data
            return chain
        chain.append(m)
        seen.add(m.parent_key)
        current = m.parent_key


def container_scans(store: EvidenceStore, container_key: str, site_id: str | None = None) -> list[TimedScan]:
    rows = store.find(ScanEvent, container_key=container_key)
    if site_id is not None:
        rows = [s for s in rows if s.site_id == site_id]
    cache: dict = {}
    return sorted((timed(store, s, cache) for s in rows), key=lambda t: t.t)


# --- facility visits: "scanned in but never out" ----------------------------------------------------------------------

VisitStatus = Literal["not_visited", "open_within_sla", "open_overdue", "closed_direct", "closed_inherited",
                      "closed_downstream"]  # fmt: skip


@dataclass
class FacilityVisit:
    site_id: str
    status: VisitStatus
    keys: set[str]
    opened_by: TimedScan | None = None
    closed_by: str | None = None  # scan_event_id or membership_id
    last_scan: TimedScan | None = None
    container_chain: list[ContainerMembership] = field(default_factory=list)
    label: EvidenceLabel = EvidenceLabel.UNKNOWN
    notes: list[str] = field(default_factory=list)


def facility_visit(store: EvidenceStore, site_id: str, keys: set[str], *, now: datetime,
                   sla: timedelta = timedelta(hours=6), late_upload_grace: timedelta = timedelta(minutes=45),
                   dedupe_ms: float = DEFAULT_DEDUPE_MS) -> FacilityVisit:  # fmt: skip
    """Classify the parcel's visit to `site_id`. Closure needs evidence: a direct departure/load scan, an inherited
    closure through a container that departed (estimated), or a later scan at another facility."""
    all_scans = scans_for(store, keys, dedupe_ms=dedupe_ms)
    keys = all_scans.keys
    here = [s for s in all_scans.scans if s.scan.site_id == site_id]
    visit = FacilityVisit(site_id, "not_visited", keys)
    if not here:
        return visit
    opening = next((s for s in here if s.scan.event_kind in VISIT_OPENING), here[0])
    if opening.scan.event_kind not in VISIT_OPENING:
        visit.notes.append(f"no arrival/induction scan; visit opened by first scan ({opening.scan.event_kind})")
    visit.opened_by, visit.last_scan = opening, here[-1]
    for s in here:
        a, b = s.scan.sort_destination_assigned, s.scan.sort_destination_actual
        if a and b and a != b:
            visit.notes.append(f"missort: assigned {a}, actual {b} ({s.scan.scan_event_id})")
    if any(s.late_upload for s in here):
        visit.notes.append("some scans were uploaded late (batch-synced device); their times carry more uncertainty")
    if all_scans.dropped_corrected:
        visit.notes.append(f"{len(all_scans.dropped_corrected)} corrected scan(s) excluded")

    # 1. direct closure
    direct = next((s for s in here if s.t >= opening.t and s.scan.event_kind == ScanEventKind.DEPARTED_FACILITY), None)
    if direct:
        visit.status, visit.closed_by, visit.label = "closed_direct", direct.scan.scan_event_id, EvidenceLabel.OBSERVED
        return visit

    # 2. downstream evidence at another facility
    downstream = next((s for s in all_scans.scans if s.scan.site_id != site_id and s.t > opening.t), None)
    if downstream:
        visit.status, visit.closed_by, visit.label = "closed_downstream", downstream.scan.scan_event_id, \
            EvidenceLabel.OBSERVED  # fmt: skip
        visit.notes.append(f"next seen at {downstream.scan.site_id}")
        return visit

    # 3. inherited closure through the container chain
    parcel_key = next(iter(sorted(k for k in keys if not k.startswith("container:"))), None)
    if parcel_key is not None:
        chain = container_chain(store, parcel_key, here[-1].t)
        visit.container_chain = chain
        for m in chain:
            left = [c for c in container_scans(store, m.parent_key, site_id)
                    if c.t >= m.valid_from and c.scan.event_kind in (ScanEventKind.CONTAINER_LOADED,
                                                                    ScanEventKind.DEPARTED_FACILITY)]  # fmt: skip
            if not left:
                continue
            # Downstream breakdown: was the container emptied elsewhere WITHOUT this parcel?
            emptied = [c for c in container_scans(store, m.parent_key)
                       if c.scan.site_id != site_id and c.scan.event_kind == ScanEventKind.CONTAINER_REMOVE
                       and c.scan.identifiers]  # fmt: skip
            if emptied and not any(set(c.scan.identity_keys) & keys for c in emptied):
                visit.notes.append(f"{m.parent_key} was emptied at {emptied[0].scan.site_id} without this parcel: "
                                   "inherited departure contradicted")
                break
            visit.status, visit.closed_by, visit.label = "closed_inherited", m.membership_id, EvidenceLabel.ESTIMATED
            visit.notes.append(f"estimated: inside {m.parent_key}, which was "
                               f"{left[0].scan.event_kind.value.replace('_', ' ')} at {left[0].t.isoformat()}")
            return visit

    elapsed = now - opening.t
    visit.status = "open_overdue" if elapsed > sla + late_upload_grace else "open_within_sla"
    visit.label = EvidenceLabel.UNKNOWN
    visit.notes.append(f"no departure evidence {elapsed} after the visit opened")
    return visit


# --- graded last seen --------------------------------------------------------------------------------------------------

SightingClass = Literal["fixed_scan", "handheld_scan", "video", "inherited_container", "candidate_video"]
CONFIDENT: frozenset[str] = frozenset({"fixed_scan", "handheld_scan", "video"})


@dataclass
class Sighting:
    klass: SightingClass
    t: datetime
    label: EvidenceLabel
    evidence_id: str
    where: str
    unc_ms: float | None


@dataclass
class GradedLastSeen:
    last_confident: Sighting | None
    confident: list[Sighting]
    leads: list[Sighting]  # inherited container locations and candidate video: shown separately, never "last seen"


def graded_last_seen(store: EvidenceStore, object_instance_id: str) -> GradedLastSeen:
    """Rank evidence classes: 1 fixed-scanner read, 2 handheld read, 3 video on a confirmed/scan-bound track,
    4 inherited container location (estimated), 5 candidate cross-camera video (hypothesized)."""
    keys = object_keys(store, object_instance_id)
    confident: list[Sighting] = []
    leads: list[Sighting] = []
    timeline = scans_for(store, keys, resolve=False) if keys else ScanTimeline([], keys)
    for ts in timeline.scans:
        s = ts.scan
        if s.read_outcome.value != "read":
            continue
        fixed = s.device_kind != DeviceKind.HANDHELD
        where = s.read_point_zone_id or s.station_id or s.device_id
        confident.append(Sighting("fixed_scan" if fixed else "handheld_scan", ts.t,
                                  EvidenceLabel.OBSERVED if fixed else EvidenceLabel.ESTIMATED,
                                  s.scan_event_id, f"{s.site_id}/{where}", ts.unc_ms))  # fmt: skip
    ls = last_confirmed(store, object_instance_id)
    if ls.observation is not None:
        confident.append(Sighting("video", ls.observation.source_frame.normalized_utc, EvidenceLabel.OBSERVED,
                                  ls.observation.observation_id, ls.observation.camera_id or "camera",
                                  ls.uncertainty_ms))  # fmt: skip
    tentative = object_evidence(store, object_instance_id, include_tentative=True).timed
    confirmed_ids = {t.obs.observation_id for t in object_evidence(store, object_instance_id).timed}
    cands = [t for t in tentative if t.obs.observation_id not in confirmed_ids]
    if cands:
        c = cands[-1]
        leads.append(Sighting("candidate_video", c.obs.source_frame.normalized_utc, EvidenceLabel.HYPOTHESIZED,
                              c.obs.observation_id, c.obs.camera_id or "camera", c.unc_ms))  # fmt: skip
    if confident and keys:
        last_t = max(s.t for s in confident)
        parcel_key = next(iter(sorted(k for k in keys if not k.startswith("container:"))), None)
        if parcel_key:
            for m in container_chain(store, parcel_key, last_t):
                later = [c for c in container_scans(store, m.parent_key) if c.t > last_t]
                if later:
                    c = later[-1]
                    leads.append(Sighting("inherited_container", c.t, EvidenceLabel.ESTIMATED, c.scan.scan_event_id,
                                          f"inside {m.parent_key}: {c.scan.event_kind.value} at "
                                          f"{c.scan.site_id}/{c.scan.station_id or c.scan.device_id}", c.unc_ms))
    confident.sort(key=lambda s: s.t)
    leads.sort(key=lambda s: s.t)
    return GradedLastSeen(confident[-1] if confident else None, confident, leads)

