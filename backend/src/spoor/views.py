"""Read models for the investigation UI and demo (PRD §19): replay paths and "what changed" between revisions.

Replay obeys the rendering contract (PRD §13.5, §18.1): solid `observed` segments only inside one camera's
continuous track; `hypothesized` dashed links between segments; explicit `gap` entries; every point keeps its
observation ID, spatial mode and uncertainty so the UI can never draw more certainty than the evidence has.
"""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import pairwise

from spoor.contracts import CaseRevision, Hypothesis, ObjectInstance, VerifiedFinding
from spoor.spatial import site_to_renderer
from spoor.store import (
    EvidenceRequest,
    EvidenceStore,
    Invalidation,
    ObjectView,
    track_segments,
    unobserved_intervals,
)

DEFAULT_MAX_POINTS = 120


def _iso(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="milliseconds")


def _thin(items: list, n: int) -> list:
    """Keep first, last and evenly spaced points so long tracks stay light for the browser."""
    if len(items) <= n:
        return items
    step = (len(items) - 1) / (n - 1)
    return [items[round(i * step)] for i in range(n)]


def replay(store: EvidenceStore, case_id: str, *, max_points_per_segment: int = DEFAULT_MAX_POINTS) -> dict:
    objects = []
    for obj in store.find(ObjectInstance, case_id=case_id):
        view = ObjectView.load(store, obj.object_instance_id)
        segments = track_segments(store, obj.object_instance_id, view=view)
        pieces: list[dict] = []
        for seg in segments:
            points = []
            for t in _thin(seg.observations, max_points_per_segment):
                est = view.estimates.get(t.obs.observation_id)
                xy = est.floor_xy_m if est else None
                points.append({
                    "t": _iso(t.t_ms), "observation_id": t.obs.observation_id,
                    "spatial_mode": est.spatial_mode.value if est else "image_only",
                    "floor_xy_m": xy, "zone_id": est.zone_id if est else None,
                    "uncertainty_radius_m": est.uncertainty_radius_m if est else None,
                    "renderer_xyz_y_up": site_to_renderer((*xy, est.height_m or 0.0)) if xy else None,
                })  # fmt: skip
            pieces.append({"kind": "observed", "style": "solid", "camera_id": seg.camera_id,
                           "track_id": seg.track_id, "start": _iso(seg.start_ms), "end": _iso(seg.end_ms),
                           "points": points})  # fmt: skip
        # Links between consecutive segments are hypotheses (dashed), never observed motion.
        ordered = sorted(pieces, key=lambda p: p["start"])
        links = []
        for a, b in pairwise(ordered):
            pa = next((p for p in reversed(a["points"]) if p["floor_xy_m"]), None)
            pb = next((p for p in b["points"] if p["floor_xy_m"]), None)
            if b["start"] > a["end"] and pa and pb:
                links.append({"kind": "hypothesized", "style": "dashed", "from": pa["observation_id"],
                              "to": pb["observation_id"], "start": a["end"], "end": b["start"]})
        gaps = []
        if view.evidence.timed:
            t0, t1 = view.evidence.timed[0].t_ms, view.evidence.timed[-1].t_ms
            gaps = [{"kind": "unknown", "style": "grey", "start": _iso(g.start_ms), "end": _iso(g.end_ms),
                     "reason": g.reason, "covering_camera_ids": g.covering_camera_ids}
                    for g in unobserved_intervals(store, obj.object_instance_id, t0, t1)]  # fmt: skip
        objects.append({"object_instance_id": obj.object_instance_id, "label": obj.label,
                        "segments": ordered, "links": links, "gaps": gaps})
    return {"case_id": case_id, "contract": "solid=observed within one camera track; dashed=hypothesized; "
                                            "grey=unknown. Never draw solid across a gap.", "objects": objects}


@dataclass
class CaseDiff:
    from_revision: str | None
    to_revision: str
    new_findings: list[dict] = field(default_factory=list)
    invalidated_findings: list[str] = field(default_factory=list)
    status_changes: list[dict] = field(default_factory=list)
    new_hypotheses: list[dict] = field(default_factory=list)
    new_evidence_requests: list[dict] = field(default_factory=list)
    last_seen_changed: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def case_diff(store: EvidenceStore, case_id: str, from_revision: str | None, to_revision: str | None = None) -> CaseDiff:
    """What changed between two case revisions — the 'new evidence added' moment (PRD §19.3). Derived only from
    timestamps of append-only records, so it is reproducible."""
    revs = store.find(CaseRevision, case_id=case_id)
    if not revs:
        raise KeyError(f"{case_id} has no revisions")
    by_id = {r.case_revision_id: r for r in revs}
    to_rev = by_id[to_revision] if to_revision else revs[-1]
    from_rev = by_id[from_revision] if from_revision else None
    lo = from_rev.at if from_rev else datetime.min.replace(tzinfo=UTC)
    hi = to_rev.at

    def window(at: datetime) -> bool:
        return lo < at <= hi

    diff = CaseDiff(from_rev.case_revision_id if from_rev else None, to_rev.case_revision_id)
    findings = store.find(VerifiedFinding, case_id=case_id)
    invalid = store.invalid_ids()
    for f in findings:
        if f.finding_id in invalid and any(window(i.at) for i in store.find(Invalidation, target_id=f.finding_id)):
            diff.invalidated_findings.append(f.finding_id)
        if window(f.at):
            diff.new_findings.append({"finding_id": f.finding_id, "statement": f.statement,
                                      "observation_ids": f.observation_ids, "invalidated": f.finding_id in invalid})
    for h in store.find(Hypothesis, case_id=case_id):
        if window(h.created_at):
            diff.new_hypotheses.append({"hypothesis_id": h.hypothesis_id, "claim": h.claim})
        history = store.status_history(h.hypothesis_id)
        before = next((c.to_status.value for c in reversed(history) if c.at <= lo), "proposed")
        after = next((c.to_status.value for c in reversed(history) if c.at <= hi), "proposed")
        if before != after:
            diff.status_changes.append({"hypothesis_id": h.hypothesis_id, "claim": h.claim, "from": before,
                                        "to": after})
    for r in store.find(EvidenceRequest, case_id=case_id):
        if window(r.at):
            diff.new_evidence_requests.append({"reason": r.reason, "camera_id": r.camera_id})
    # Last-seen statement per object before vs after (latest finding whose text starts with the object label).
    for obj in store.find(ObjectInstance, case_id=case_id):
        mine = sorted((f for f in findings if f.statement.startswith(obj.label)), key=lambda f: f.at)
        before = next((f for f in reversed(mine) if f.at <= lo), None)
        after = next((f for f in reversed(mine) if f.at <= hi), None)
        if after and (before is None or before.finding_id != after.finding_id):
            diff.last_seen_changed.append({"object": obj.label, "before": before.statement if before else None,
                                           "after": after.statement})
    return diff


def annotate_png(png: bytes, box_xyxy_px: tuple[float, float, float, float], label: str) -> bytes:
    """Draw a SAM box on a frame. The result is an ANNOTATED DERIVATIVE and says so on the image (PRD §7.3)."""
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not a decodable image")
    x1, y1, x2, y2 = (round(v) for v in box_xyxy_px)
    cv2.rectangle(img, (x1, y1), (max(x1, x2 - 1), max(y1, y2 - 1)), (0, 200, 255), 2)
    cv2.putText(img, label[:60], (x1, max(12, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1,
                cv2.LINE_AA)  # fmt: skip
    h, w = img.shape[:2]
    cv2.rectangle(img, (0, h - 18), (w, h), (0, 0, 0), -1)
    cv2.putText(img, "ANNOTATED DERIVATIVE - not the original frame", (4, h - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (255, 255, 255), 1, cv2.LINE_AA)  # fmt: skip
    ok, out = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("encoding failed")
    return out.tobytes()
