"""Bounded clip questions to Muse Spark (PRD §15). Outputs are PROPOSALS: timestamps are candidates until grounded
against SAM observations or frame checks, and nothing here writes findings."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from spoor.contracts import FrameRef, new_id
from spoor.ingest import FrameTable
from spoor.safety import NON_ACCUSATION_RULE, UNTRUSTED_DATA_RULE, as_untrusted_data, find_forbidden
from spoor.store import CostEntry, EvidenceStore

from .backends import BackendError, BackendReply, JsonBackend
from .clips import ClipWindow


class Fact(BaseModel):
    statement: str = Field(description="One visible fact about the target object, no interpretation")
    approx_time_s: float | None = Field(description="Seconds from the START OF THIS CLIP, or null if not timed")
    visibility: Literal["clear", "partial", "unclear"]


class EvidenceAsk(BaseModel):
    what: str = Field(description="What additional footage or log would distinguish the explanations")
    why: str


class ClipAnswer(BaseModel):
    observed_facts: list[Fact]
    candidate_hypotheses: list[str]
    unknowns: list[str]
    requested_evidence: list[EvidenceAsk]
    not_observable: bool = Field(description="True if the question cannot be answered from this clip")
    abstain_reason: str | None


SYSTEM = f"""You are the clip-interpretation step of an evidence system for locating physical objects in CCTV footage.
Report only what is visible in THIS clip. Times are seconds from the start of this clip.
Separate observed facts from candidate hypotheses. If something cannot be seen, say so: set not_observable or list it
under unknowns. Never guess.
{NON_ACCUSATION_RULE}
{UNTRUSTED_DATA_RULE}"""

TEMPLATES = {
    "presence_v1": "Is the target object visible in this clip? For each period it is clearly visible, give a fact "
                   "with the time it is first and last clearly visible. Note if it becomes hidden or leaves the view.",
    "interaction_v1": "Describe visible changes to the target object in this clip: picked up, carried, set down, "
                      "covered, or leaving the view, each with a time. Do not describe who the person is.",
    "contradiction_v1": "Consider the hypothesis given as data. Which visible facts in this clip support it, which "
                        "contradict it, and what is not visible? Put supporting/contradicting facts in "
                        "observed_facts and anything unresolved in unknowns.",
    "next_evidence_v1": "Which additional camera views, time ranges or sensor logs would best distinguish the "
                        "candidate explanations given as data? Use requested_evidence.",
}  # fmt: skip


@dataclass
class CandidateFact:
    statement: str
    visibility: str
    frame_ref: FrameRef | None  # candidate only; grounding decides whether it stands
    outside_window: bool = False


@dataclass
class ClipAnalysis:
    status: Literal["ok", "not_observable", "analysis_unavailable", "not_authorized_for_hosted_processing"]
    template: str
    window: ClipWindow | None
    facts: list[CandidateFact] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    requested_evidence: list[EvidenceAsk] = field(default_factory=list)
    rejected_statements: list[tuple[str, list]] = field(default_factory=list)
    uninspected: list[tuple[float, float]] = field(default_factory=list)  # original pts ranges not in the window
    abstain_reason: str | None = None
    reply: BackendReply | None = None
    error: str | None = None


def _ledger(store, backend, reply, case_id, kind, outcome, now):
    if store is None:
        return
    store.record_cost(CostEntry(
        cost_id=new_id("ledger"), provider=backend.provider, model=reply.model if reply else backend.model,
        request_kind=kind, case_id=case_id, response_id=reply.response_id if reply else None,
        input_tokens=reply.input_tokens if reply else 0, output_tokens=reply.output_tokens if reply else 0,
        outcome=outcome, latency_s=reply.latency_s if reply else None, at=now,
    ))  # fmt: skip


def ask_clip(
    *,
    backend: JsonBackend,
    upload_file_id: str,
    window: ClipWindow,
    table: FrameTable,
    template: str,
    target: str,
    hosted_processing_allowed: bool,
    context: dict | None = None,
    store: EvidenceStore | None = None,
    case_id: str | None = None,
    now: datetime | None = None,
) -> ClipAnalysis:
    now = now or datetime.now(UTC)
    if not hosted_processing_allowed:
        return ClipAnalysis("not_authorized_for_hosted_processing", template, window)
    if not backend.supports_video:
        raise BackendError(f"{backend.provider} cannot read video")
    text = "\n\n".join(filter(None, [
        TEMPLATES[template],
        as_untrusted_data("target_object", target),
        as_untrusted_data("context", context) if context else None,
    ]))  # fmt: skip
    content = [{"type": "input_text", "text": text}, {"type": "input_video", "file_id": upload_file_id}]
    try:
        reply = backend.complete(system=SYSTEM, content=content, output=ClipAnswer, name="clip_answer")
    except Exception as e:  # noqa: BLE001 — any provider failure leaves evidence intact and analysis unavailable
        _ledger(store, backend, None, case_id, f"spark_clip:{template}", "error", now)
        return ClipAnalysis("analysis_unavailable", template, window, error=f"{type(e).__name__}: {e}")
    _ledger(store, backend, reply, case_id, f"spark_clip:{template}", "ok", now)

    answer: ClipAnswer = reply.data
    out = ClipAnalysis("not_observable" if answer.not_observable else "ok", template, window, reply=reply,
                       abstain_reason=answer.abstain_reason)  # fmt: skip
    for fact in answer.observed_facts:
        if hits := find_forbidden(fact.statement):
            out.rejected_statements.append((fact.statement, hits))
            continue
        idx = window.to_original(fact.approx_time_s) if fact.approx_time_s is not None else None
        ref = FrameRef(media_id=window.source_media_id, pts_ms=table.pts_ms[idx], frame_index=idx) \
            if idx is not None else None  # fmt: skip
        out.facts.append(CandidateFact(fact.statement, fact.visibility, ref,
                                       outside_window=fact.approx_time_s is not None and idx is None))
    for h in answer.candidate_hypotheses:
        (out.rejected_statements.append((h, hits)) if (hits := find_forbidden(h)) else out.hypotheses.append(h))
    out.unknowns = [u for u in answer.unknowns if not find_forbidden(u)]
    out.requested_evidence = [r for r in answer.requested_evidence if not find_forbidden(r.what + " " + r.why)]
    first, last = table.pts_ms[0], table.pts_ms[-1]
    start, end = table.pts_ms[window.start_frame], table.pts_ms[window.end_frame]  # in ORIGINAL time
    out.uninspected = [(a, b) for a, b in ((first, start), (end, last)) if b > a]
    return out
