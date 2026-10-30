"""Records vs video (QUEUE I6 / H5): where the scan records and the cameras disagree, as typed conflicts.

A conflict needs a record that claims an ONGOING place, and a confirmed sighting that contradicts it:
- custody: the parcel is in a container (bag / cage membership from the scan log) and that container's own scans put it
  in zone A, while a confirmed track of the parcel shows it in zone B after the claim (S3: bag vs floor);
- departure: a loading / departure scan says it left (directly or through its container), and a confirmed track
  shows it inside the hub afterwards (S2: cage "left on the truck" vs the exception store; S4: D08 vs D09);
- records timing: two scans of the same parcel are closer in time than the belt route allows (from the journey).
A sighting after a plain scan is movement, not a conflict. No confirmed track (no-key mode) = no video side yet: the
response says so instead of implying agreement."""

from dataclasses import dataclass
from datetime import datetime

from spoor.contracts import Case, ObjectInstance, ScanEvent, ScanEventKind
from spoor.store import EvidenceStore, ObjectView
from spoor.store.parcels import container_scans, memberships_of, object_keys

from .journey import build_journey, iso, latest_plan

DEPARTS = {ScanEventKind.CONTAINER_LOADED, ScanEventKind.DEPARTED_FACILITY}
TOL_MS = 2000  # clock tolerance before a sighting counts as "after" a claim


@dataclass
class Claim:
    t_ms: float
    kind: str  # "custody" | "departure"
    zone_id: str | None
    words: str
    evidence_ids: list[str]


def _claims(store: EvidenceStore, keys: set[str], site_id: str) -> list[Claim]:
    """Ongoing-place claims from container memberships and the containers' own scans (recursively, bag -> cage)."""
    out: list[Claim] = []
    frontier, seen = list(keys), set(keys)
    while frontier:
        key = frontier.pop()
        for m in memberships_of(store, key):
            parent = m.parent_key
            label = parent.split(":", 1)[-1]
            out.append(Claim(m.valid_from.timestamp() * 1000, "custody", None, f"inside {label} (from the scan log)",
                             [m.membership_id] + ([m.opened_by_event_id] if m.opened_by_event_id else [])))
            for ts in container_scans(store, parent, site_id):  # indexed by the same "container:<id>" key
                s: ScanEvent = ts.scan
                if ts.t < m.valid_from or (m.valid_to and ts.t > m.valid_to and s.event_kind not in DEPARTS):
                    continue
                kind = "departure" if s.event_kind in DEPARTS else "custody"
                where = s.station_id or s.device_id
                out.append(Claim(ts.t_ms, kind, s.read_point_zone_id,
                                 f"{label} {s.event_kind.value.replace('_', ' ')} at {where}", [s.scan_event_id]))
            if parent not in seen:
                seen.add(parent)
                frontier.append(parent)
    return sorted(out, key=lambda c: c.t_ms)


def records_vs_video(store: EvidenceStore, case_id: str) -> dict:
    case = store.get(Case, case_id)
    plan = latest_plan(store, case.site_id)
    journey = build_journey(store, case_id, plan=plan)
    objects = []
    for obj, oj in zip(store.find(ObjectInstance, case_id=case_id), journey["objects"], strict=True):
        keys = object_keys(store, obj.object_instance_id)
        claims = _claims(store, keys, case.site_id)
        for s in oj["scans"]:
            if s["event_kind"] in {k.value for k in DEPARTS}:
                claims.append(Claim(datetime.fromisoformat(s["t"]).timestamp() * 1000, "departure", s["zone_id"],
                                    f"{s['event_kind'].replace('_', ' ')} at {s['station_id'] or s['device_id']}",
                                    [s["scan_event_id"]]))
        claims.sort(key=lambda c: c.t_ms)
        view = ObjectView.load(store, obj.object_instance_id)
        sightings = [(t.t_ms, t.obs.observation_id, t.obs.camera_id, view.zone(t.obs.observation_id))
                     for t in view.evidence.timed]  # fmt: skip
        conflicts = []
        for g in oj["segments"]:
            if g["kind"] == "gap" and g["reason"] == "faster_than_belt":
                conflicts.append({"kind": "records_timing", "divergence_t": g["start"], "statement": g["note"],
                                  "claim": {"evidence_ids": g["evidence_ids"]}, "observation": None})  # fmt: skip
        for c in claims:
            for t_ms, oid, cam, zone in sightings:
                if t_ms <= c.t_ms + TOL_MS:
                    continue
                if c.kind == "departure" or (c.zone_id and zone and zone != c.zone_id):
                    what = "left the hub" if c.kind == "departure" else f"was in {c.zone_id}"
                    conflicts.append({
                        "kind": c.kind, "divergence_t": iso(t_ms),
                        "statement": f"The records say it {what} ({c.words}, {iso(c.t_ms)}); "
                                     f"{cam} saw it at {zone or 'its view'} at {iso(t_ms)}.",
                        "claim": {"t": iso(c.t_ms), "zone_id": c.zone_id, "words": c.words, "evidence_ids": c.evidence_ids},
                        "observation": {"observation_id": oid, "t": iso(t_ms), "camera_id": cam, "zone_id": zone},
                    })  # fmt: skip
                    break
        conflicts.sort(key=lambda x: x["divergence_t"])
        objects.append({
            "object_instance_id": obj.object_instance_id, "label": obj.label,
            "records": [{"t": s["t"], "words": f"{s['raw_code'] or s['event_kind']} at {s['station_id'] or s['device_id']}",
                         "zone_id": s["zone_id"], "evidence_id": s["scan_event_id"]} for s in oj["scans"]]
                       + [{"t": iso(c.t_ms), "words": c.words, "zone_id": c.zone_id, "evidence_id": c.evidence_ids[0],
                           "claim": c.kind} for c in claims],
            "video": [{"start": s["start"], "end": s["end"], "camera_id": s["camera_id"], "evidence_ids": s["evidence_ids"]}
                      for s in oj["segments"] if s["kind"] == "observed"],
            "conflicts": conflicts,
            "note": None if sightings else "no confirmed camera track yet: the video side is empty, which is not "
                                           "agreement (tracking needs SAM)",
        })  # fmt: skip
    for o in objects:
        o["records"].sort(key=lambda r: r["t"])
    return {"case_id": case_id, "objects": objects}
