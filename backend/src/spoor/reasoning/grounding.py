"""Ground model-proposed facts against SAM observations (PRD §10.2: a model timestamp is a candidate until verified)."""

from dataclasses import dataclass
from typing import Literal

from spoor.store import EvidenceStore, object_evidence

from .spark import CandidateFact


@dataclass
class GroundedFact:
    fact: CandidateFact
    status: Literal["grounded", "ungrounded", "untimed", "outside_window"]
    observation_ids: list[str]


def ground_facts(store: EvidenceStore, object_instance_id: str, facts: list[CandidateFact], *,
                 tolerance_frames: int = 5) -> list[GroundedFact]:  # fmt: skip
    """A fact is grounded only if a confirmed observation of the same object exists in the same media within
    `tolerance_frames` of the model's candidate frame. Otherwise it stays a proposal."""
    ev = object_evidence(store, object_instance_id)
    by_media: dict[str, list] = {}
    for obs in [t.obs for t in ev.timed] + ev.unsynced:
        f = obs.source_frame
        by_media.setdefault(f.media_id, []).append((f.frame_index, obs.observation_id))
    out = []
    for fact in facts:
        if fact.outside_window:
            out.append(GroundedFact(fact, "outside_window", []))
        elif fact.frame_ref is None:
            out.append(GroundedFact(fact, "untimed", []))
        else:
            near = [oid for idx, oid in by_media.get(fact.frame_ref.media_id, [])
                    if abs(idx - fact.frame_ref.frame_index) <= tolerance_frames]  # fmt: skip
            out.append(GroundedFact(fact, "grounded" if near else "ungrounded", near))
    return out
