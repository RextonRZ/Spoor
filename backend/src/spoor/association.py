"""Cross-camera tracklet association with hard gates and abstention (PRD §14.3, step 11b). Optional.

Signals: time feasibility, camera topology (minimum travel time), floor geometry (speed), and an OPTIONAL object
appearance vector supplied by an evaluated encoder (none is bundled — see docs/DECISIONS.md). Output is always
`candidate_cross_camera`, `unresolved` or `rejected`; only a human can confirm a cross-camera link.
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
from scipy.optimize import linear_sum_assignment

from spoor.contracts import AssociationStatus, RawObservation, Track, TrackAssociation
from spoor.store import EvidenceStore, epoch_ms, estimate_for

GATED = 1e9


@dataclass(frozen=True)
class Tracklet:
    track_id: str
    camera_id: str
    start_ms: float
    end_ms: float
    time_uncertainty_ms: float
    start_xy: tuple[float, float] | None
    end_xy: tuple[float, float] | None
    appearance: np.ndarray | None = None


@dataclass
class Topology:
    """Minimum plausible travel time between cameras' views (seconds); missing pair = not directly connected."""

    min_travel_s: dict[tuple[str, str], float] = field(default_factory=dict)
    overlapping: set[frozenset[str]] = field(default_factory=set)

    def travel(self, a: str, b: str) -> float | None:
        if a == b:
            return 0.0
        return self.min_travel_s.get((a, b), self.min_travel_s.get((b, a)))


@dataclass
class AssociationConfig:
    max_speed_mps: float = 2.5
    max_gap_s: float = 120.0
    min_appearance_cos: float = 0.6
    accept_cost: float = 1.0
    ambiguity_margin: float = 0.15  # second-best within this cost margin -> abstain
    w_time: float = 0.5
    w_distance: float = 0.3
    w_appearance: float = 0.5


@dataclass
class LinkProposal:
    from_track_id: str
    to_track_id: str
    status: AssociationStatus
    cost: float | None
    signals: dict[str, float]
    reason: str


def tracklet(store: EvidenceStore, track_id: str, appearance: np.ndarray | None = None) -> Tracklet | None:
    obs = [o for o in store.find(RawObservation, track_id=track_id)
           if o.source_frame and o.source_frame.normalized_utc and not store.is_invalid(o.observation_id)]
    if not obs:
        return None
    obs.sort(key=lambda o: o.source_frame.normalized_utc)

    def xy(o):
        e = estimate_for(store, o.observation_id)
        return e.floor_xy_m if e else None

    track = store.get(Track, track_id)
    return Tracklet(track_id, track.camera_id, float(epoch_ms(obs[0].source_frame.normalized_utc)),
                    float(epoch_ms(obs[-1].source_frame.normalized_utc)),
                    max(o.source_frame.time_uncertainty_ms or 0 for o in obs), xy(obs[0]), xy(obs[-1]), appearance)


def pair_cost(a: Tracklet, b: Tracklet, topo: Topology, cfg: AssociationConfig) -> tuple[float, dict, str]:
    """Cost of 'b continues a'. Returns (GATED, ..., reason) when physically or topologically impossible."""
    tol_s = (a.time_uncertainty_ms + b.time_uncertainty_ms) / 1000.0
    gap_s = (b.start_ms - a.end_ms) / 1000.0
    signals: dict[str, float] = {"gap_s": gap_s}
    overlapping = frozenset({a.camera_id, b.camera_id}) in topo.overlapping
    if gap_s < -tol_s and not overlapping:
        return GATED, signals, "simultaneous sightings in non-overlapping views (negative constraint)"
    if gap_s > cfg.max_gap_s:
        return GATED, signals, f"gap {gap_s:.0f}s exceeds {cfg.max_gap_s:.0f}s"
    travel = topo.travel(a.camera_id, b.camera_id)
    if travel is None and not overlapping:
        return GATED, signals, "cameras are not connected in the site topology"
    if travel is not None and gap_s + tol_s < travel:
        return GATED, signals, f"needs >= {travel:.1f}s between these views, had {gap_s:.1f}s"
    dist_term = 0.0
    if a.end_xy and b.start_xy:
        dist = math.dist(a.end_xy, b.start_xy)
        signals["distance_m"] = dist
        if dist > cfg.max_speed_mps * max(gap_s + tol_s, 1e-3):
            return GATED, signals, f"{dist:.1f} m in {gap_s:.1f}s exceeds {cfg.max_speed_mps} m/s"
        dist_term = dist / (cfg.max_speed_mps * max(gap_s + tol_s, 1.0))
    app_term = 0.5  # unknown appearance contributes neutral, not favourable, evidence
    if a.appearance is not None and b.appearance is not None:
        cos = float(np.dot(a.appearance, b.appearance) / (np.linalg.norm(a.appearance) * np.linalg.norm(b.appearance)))
        signals["appearance_cos"] = cos
        if cos < cfg.min_appearance_cos:
            return GATED, signals, f"appearance similarity {cos:.2f} below {cfg.min_appearance_cos}"
        app_term = 1.0 - cos
    cost = cfg.w_time * max(gap_s, 0) / cfg.max_gap_s + cfg.w_distance * dist_term + cfg.w_appearance * app_term
    return cost, signals, "feasible"


def propose_links(ends: list[Tracklet], starts: list[Tracklet], topo: Topology,
                  cfg: AssociationConfig | None = None) -> list[LinkProposal]:  # fmt: skip
    """One-to-one assignment after hard gating; ambiguous or weak matches abstain as `unresolved`."""
    cfg = cfg or AssociationConfig()
    if not ends or not starts:
        return []
    costs = np.full((len(ends), len(starts)), GATED)
    info: dict[tuple[int, int], tuple[dict, str]] = {}
    for i, a in enumerate(ends):
        for j, b in enumerate(starts):
            if a.track_id == b.track_id:
                continue
            c, sig, why = pair_cost(a, b, topo, cfg)
            costs[i, j], info[(i, j)] = c, (sig, why)
    rows, cols = linear_sum_assignment(costs)
    out = []
    for i, j in zip(rows, cols, strict=True):
        sig, why = info.get((i, j), ({}, "same track"))
        c = costs[i, j]
        if c >= GATED:
            out.append(LinkProposal(ends[i].track_id, starts[j].track_id, AssociationStatus.REJECTED, None, sig, why))
            continue
        rivals = sorted([costs[i, k] for k in range(len(starts)) if k != j and costs[i, k] < GATED]
                        + [costs[k, j] for k in range(len(ends)) if k != i and costs[k, j] < GATED])  # fmt: skip
        if rivals and rivals[0] - c <= cfg.ambiguity_margin:
            out.append(LinkProposal(ends[i].track_id, starts[j].track_id, AssociationStatus.UNRESOLVED, c, sig,
                                    f"ambiguous: another feasible match within {cfg.ambiguity_margin} cost"))
        elif c > cfg.accept_cost:
            out.append(LinkProposal(ends[i].track_id, starts[j].track_id, AssociationStatus.UNRESOLVED, c, sig,
                                    "feasible but weak"))
        else:
            out.append(LinkProposal(ends[i].track_id, starts[j].track_id, AssociationStatus.CANDIDATE_CROSS_CAMERA,
                                    c, sig, "best feasible match; requires human confirmation"))
    return out


def to_association(object_instance_id: str, p: LinkProposal, *, version: int, created_by: str,
                   now: datetime | None = None) -> TrackAssociation:  # fmt: skip
    return TrackAssociation(object_instance_id=object_instance_id, track_id=p.to_track_id, status=p.status,
                            signals={k: float(v) for k, v in p.signals.items()}, reason=p.reason, version=version,
                            created_at=now or datetime.now(UTC), created_by=created_by)  # fmt: skip
