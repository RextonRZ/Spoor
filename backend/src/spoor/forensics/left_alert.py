"""Live alert "left without a scan" (six checkpoints, addendum 4 #2): a carton scanned into an open container (a cage,
a pallet) is seen leaving that container's work area on camera, and no scan of it follows. Bags are not watched: a
carton inside a closed sack can't be seen leaving as a carton, and loose cartons cross a bagging area all the time. The alert is raised at that
moment, before anyone complains. General: any container scan at any handheld point, any parcel; it never fires for a
parcel scanned out again (any later scan of it), and a container leaving with its own RFID read is a scan of the
container, not a carton taken out of it.

What is planned here is pure (scan log + site plan + footage coverage); the camera part (SAM on the watching
cameras, keeping cartons that start inside the work area and leave it) is the service's job, run on request."""

from dataclasses import dataclass
from datetime import datetime

from spoor.contracts import CameraCoverage, MediaAsset, ScanEvent, SitePlan
from spoor.contracts.parcels import ContainerType, DeviceKind, IdentifierScheme, ReadOutcome, ScanEventKind
from spoor.store import EvidenceStore
from spoor.store.parcels import effective, timed

from .handshake import waybill_of

CONTAINER_LEVEL = frozenset({ScanEventKind.CONTAINER_LOADED, ScanEventKind.CONTAINER_REMOVE})
OPEN_CONTAINERS = frozenset({ContainerType.CAGE, ContainerType.PALLET, ContainerType.GAYLORD})  # cartons stay in view


@dataclass
class Watch:
    scan_point_id: str
    camera_id: str
    media_id: str
    start: datetime  # the clip's part after the container scans
    end: datetime
    parcels: list[dict]  # [{waybill, container, scanned_in}]: in the container at this point, no scan since


def plan_watches(store: EvidenceStore, plan: SitePlan, scans: list[ScanEvent]) -> list[Watch]:
    """For every handheld open-container point: the parcels whose LAST scan put them into a container there, and the clips
    of the cameras watching it that start after those scans."""
    last: dict[str, tuple] = {}
    for s in effective(scans):
        w = waybill_of(s)
        if not w or s.read_outcome != ReadOutcome.READ:
            continue
        ts = timed(store, s)
        if w not in last or ts.t > last[w][1]:
            last[w] = (s, ts.t)
    moved: dict[str, list] = {}  # container -> times it was itself scanned (loaded, removed, closed)
    for s in effective(scans):
        if s.event_kind in CONTAINER_LEVEL and s.container:
            moved.setdefault(s.container.value, []).append(timed(store, s).t)
    by_point: dict[str, list[dict]] = {}
    for w, (s, t) in last.items():
        if any(i.scheme == IdentifierScheme.CONTAINER for i in s.identifiers):
            continue  # a bag put in a cage is not a carton: the alert is about parcels
        if (s.event_kind == ScanEventKind.CONTAINER_ADD and s.device_kind == DeviceKind.HANDHELD
                and s.container_type in OPEN_CONTAINERS):
            by_point.setdefault(s.station_id or s.device_id, []).append(
                {"waybill": w, "container": s.container.value if s.container else None, "scanned_in": t,
                 # once its container leaves with its own read the parcel is accounted for through it; a carton seen
                 # leaving BEFORE that read is still one taken out (the cage then leaves without it)
                 "container_left": min((m for m in moved.get(s.container.value, []) if m > t), default=None)
                 if s.container else None})
    media = [m for m in store.find(MediaAsset) if m.kind.value == "original" and not store.is_invalid(m.media_id)]
    out: list[Watch] = []
    for sp, parcels in by_point.items():
        rp = plan.read_point(sp)
        if rp is None or not rp.work_area_m:
            continue
        first_in = min(p["scanned_in"] for p in parcels)
        for m in (m for m in media if m.camera_id in rp.visible_by):
            covs = store.find(CameraCoverage, media_id=m.media_id)
            if covs and covs[-1].end_utc > first_in:
                inside = [p for p in parcels if p["scanned_in"] < covs[-1].end_utc]
                out.append(Watch(sp, m.camera_id, m.media_id, max(covs[-1].start_utc, first_in), covs[-1].end_utc, inside))
    return out
