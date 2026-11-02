"""The scan-to-camera handshake (six checkpoints, Rexton 2 Nov): at a scan the scanner gives IDENTITY (the barcode),
PLACE (its scan point) and TIME. The site plan says which cameras see that point (visible_by, ray-checked), the
calibration puts the point in each camera's picture, and the camera's clock fit gives the frame. A SAM prompt there
outlines THAT carton; SAM then follows it for a few seconds. The scan says which parcel; the camera shows what happened.

Rules by where the carton is at the scan instant (general, from the record and the plan, never a scenario):
- a sorter / divert point: the carton is at the point at the confirm instant (point prompt then);
- a scan tunnel: the reader sits under an arch where the carton is hidden, so it is the first carton out of the exit
  just after the read (belts keep order): the prompt is at the exit a moment later;
- a handheld scan: the carton is in the worker's hands in the work area at the scan instant (area prompt, keep the
  carton that leaves the area after it);
- RFID (a cage's tag) and scan points no camera sees get a record saying so ("not on camera"), never a fake clip;
- a camera whose clock is not fitted (only the uploader's declared start) gets "clock not fitted" at belt points: belts
  pass a carton a second, so its frame at the scan's second could show any of several. A handheld point is looked at
  over the clock's whole +- window instead, only when no other scan at that point falls in the same window, and counts
  only if exactly one carton is handled there (in the area and moved: put in or taken out) in all of it.

Which outlines carry the tracking number (labelled), by rule, from the truth check (eval_handshakes.py):
- divert point: the carton is moving at the confirm (it leaves its tray); an outline that stands still at the point
  is something resting there (a carton already in the chute) -> "can't tell", not labelled;
- tunnel exit: no picture signal tells the scanned carton from the one queued before it at the exit, so the CCTV
  outline is not labelled; the tunnel's own photo, taken by the reader at the read, identifies it;
- handheld: exactly one carton handled in the work area in the window -> labelled.
Nothing here reads the scenario truth."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from spoor.contracts import CameraCoverage, ClockSync, MediaAsset, ScanEvent, SitePlan
from spoor.contracts.parcels import DeviceKind, ReadOutcome
from spoor.store import EvidenceStore
from spoor.store.parcels import effective, timed

TUNNEL_EXIT_S = 0.3  # the first carton out of the exit: this long after the read (the reader sits at the exit)
FOLLOW_S = 5.0  # how long SAM follows it after the scan
BEFORE_S = 0.5
STILL_M = 0.3  # a divert's carton moves more than this in the 1.7 s around the confirm
CLOCK_MS = 1000  # a camera clock known only to the uploader's +-5 s can't say which carton was at the point


@dataclass
class Planned:
    scan: ScanEvent
    waybill: str | None
    scan_point_id: str
    camera_id: str
    media_id: str | None
    at: datetime
    rule: str  # point | tunnel_exit | work_area
    reason: str  # "" when it can run; else why not (no_footage / not_on_camera / clock_not_fitted / cant_tell)
    note: str = ""


def waybill_of(scan: ScanEvent) -> str | None:
    return next((i.value for i in scan.identifiers if i.scheme == "carrier_waybill"), None) or \
        next((i.value for i in scan.identifiers), None)  # fmt: skip


def plan_handshakes(store: EvidenceStore, plan: SitePlan, scans: list[ScanEvent], start: datetime | None = None,
                    end: datetime | None = None) -> list[Planned]:  # fmt: skip
    """Every parcel scan in [start, end] (shared clock): one row per camera that sees its scan point."""
    out: list[Planned] = []
    media = [m for m in store.find(MediaAsset) if m.kind.value == "original" and not store.is_invalid(m.media_id)]
    covs = {m.media_id: store.find(CameraCoverage, media_id=m.media_id) for m in media}
    at_point: dict[str, list[datetime]] = {}  # every read's time at each scan point (who else was handled there)
    for s in effective(scans):
        if s.read_outcome == ReadOutcome.READ and s.identifiers:
            at_point.setdefault(s.station_id or s.device_id, []).append(timed(store, s).t)
    for s in effective(scans):
        if s.read_outcome != ReadOutcome.READ or not s.identifiers or s.device_kind == DeviceKind.RFID_PORTAL:
            continue
        ts = timed(store, s)
        if (start and ts.t < start) or (end and ts.t > end):
            continue
        sp = s.station_id or s.device_id
        rp = plan.read_point(sp)
        rule = ("tunnel_exit" if s.device_kind == DeviceKind.TUNNEL else
                "work_area" if s.device_kind == DeviceKind.HANDHELD else "point")
        at = ts.t + timedelta(seconds=TUNNEL_EXIT_S if rule == "tunnel_exit" else 0.0)
        if rp is None or not rp.visible_by:
            out.append(Planned(s, waybill_of(s), sp, "", None, at, rule, "not_on_camera"))
            continue
        for cam in rp.visible_by:
            m = next((m for m in media if m.camera_id == cam and covs[m.media_id]
                      and covs[m.media_id][-1].start_utc <= at - timedelta(seconds=BEFORE_S)
                      and at + timedelta(seconds=1.0) <= covs[m.media_id][-1].end_utc), None)  # fmt: skip
            why = "" if m else "no_footage"
            unc_ms = store.get(ClockSync, covs[m.media_id][-1].sync_id).uncertainty_ms if m else 0.0
            note = ""
            if m and unc_ms > CLOCK_MS and rule != "work_area":
                why = "clock_not_fitted"  # a belt passes a carton a second: the scan's second could be any of them
            elif m and unc_ms > CLOCK_MS:
                near = sorted(o for o in at_point.get(sp, []) if o != ts.t and abs((o - ts.t).total_seconds()) * 1000 < 2 * unc_ms)
                if near:  # other cartons handled here inside the clock's window: on camera they can't be told apart
                    why, note = "cant_tell", crowd_words(len(near) + 1, [ts.t, *near])
            out.append(Planned(s, waybill_of(s), sp, cam, m.media_id if m else None, at, rule, why, note))
    return out


NUMBER = {2: "Two", 3: "Three", 4: "Four", 5: "Five"}


def crowd_words(n: int, times: list[datetime]) -> str:
    """'Two cartons scanned 0.2 s apart here' / 'Three cartons scanned here within 1.0 s' (why a handshake is withheld)."""
    span = (max(times) - min(times)).total_seconds()
    if n == 2:
        return f"Two cartons scanned {span:.1f} s apart here"
    return f"{NUMBER.get(n, str(n))} cartons scanned here within {span:.1f} s"


def sam_frames(rows: list[Planned], fps: float = 10.0) -> int:
    """SAM frames these handshakes would send (for the estimate before a paid run)."""
    return int(sum((BEFORE_S + FOLLOW_S) * fps + 1 for r in rows if not r.reason))
