"""Lead/Orchestrator (PRD §17.3): deterministic plan -> evidence agent -> hypothesis agent -> verifier -> answer.

The user-facing answer is composed here from verified findings and recorded hypothesis statuses only. Agent prose is
never copied into it, so an eloquent but unsupported claim cannot reach the investigator as fact.
"""

import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

from pydantic import ValidationError

from spoor.contracts import (
    Actor,
    ActorKind,
    AgentRequest,
    AgentRole,
    Camera,
    CameraCoverage,
    Hypothesis,
    HypothesisStatus,
    ObjectInstance,
    VerifiedFinding,
    new_id,
)
from spoor.reasoning import JsonBackend
from spoor.safety import find_forbidden
from spoor.store import epoch_ms, last_confirmed, transitions, unobserved_intervals
from spoor.verification import LastSeenClaim

from .roles import (
    EVIDENCE_PROMPT,
    EVIDENCE_TOOLS,
    HYPOTHESIS_PROMPT,
    HYPOTHESIS_TOOLS,
    EvidenceBundle,
    HypothesisSet,
)
from .runtime import AgentRun, AgentRunner
from .tools import EvidenceRequestArgs, ScopeError, ToolContext, iso, t_request_evidence

ORCHESTRATOR = Actor(kind=ActorKind.SYSTEM, id="spoor.agents.orchestrator/v1")


@dataclass
class InvestigationConfig:
    evidence_max_steps: int = 8
    hypothesis_max_steps: int = 6
    token_budget: int = 80_000
    deadline_s: float = 300.0
    max_hypotheses: int = 4


@dataclass
class HypothesisOutcome:
    hypothesis_id: str
    claim: str
    status: HypothesisStatus
    reasons: list[str]
    missing_evidence: list[str]
    verified_checks: list[str] = field(default_factory=list)  # deterministic descriptions of supported claims


@dataclass
class ObjectAnswer:
    object_instance_id: str
    label: str
    last_seen_finding: VerifiedFinding | None
    last_seen_text: str
    left_area: Literal["supported", "contradicted", "not_established"]
    observed_moves: list[str]
    unobserved: list[dict]


@dataclass
class InvestigationResult:
    status: Literal["answered", "abstained"]
    answer: str
    objects: list[ObjectAnswer]
    findings: list[VerifiedFinding]
    hypotheses: list[HypothesisOutcome]
    evidence_request_ids: list[str]
    rejected: list[str]
    revision_id: str | None
    agent_runs: dict[str, dict] = field(default_factory=dict)


def _run_summary(run: AgentRun) -> dict:
    return {"status": run.status, "steps": run.steps, "tool_calls": run.tool_calls, "model": run.model,
            "input_tokens": run.input_tokens, "output_tokens": run.output_tokens, "errors": run.errors,
            "step_ids": run.step_ids}  # fmt: skip


def _case_window(ctx: ToolContext) -> tuple[float, float] | None:
    if ctx.scope.window:
        return ctx.scope.window.start_utc.timestamp() * 1000, ctx.scope.window.end_utc.timestamp() * 1000
    site_cams = {c.camera_id for c in ctx.store.find(Camera, site_id=ctx.case.site_id)}
    if ctx.scope.camera_ids:
        site_cams &= set(ctx.scope.camera_ids)
    covs = ctx.store.find(CameraCoverage, camera_id=sorted(site_cams)) if site_cams else []
    if not covs:
        return None
    return min(epoch_ms(c.start_utc) for c in covs), max(epoch_ms(c.end_utc) for c in covs)


def _facts(ctx: ToolContext, obj: ObjectInstance, window) -> dict:
    ls = last_confirmed(ctx.store, obj.object_instance_id)
    gaps = unobserved_intervals(ctx.store, obj.object_instance_id, *window) if window else []
    return {
        "object_instance_id": obj.object_instance_id, "label": obj.label,
        "last_confirmed_observation_id": ls.observation.observation_id if ls.observation else None,
        "last_confirmed_time": iso(ls.t_ms), "last_confirmed_zone": ls.estimate.zone_id if ls.estimate else None,
        "ambiguous_with": ls.ambiguous_with, "unsynced_observation_ids": ls.unsynced_observation_ids,
        "transitions": [{"from": t.from_zone, "to": t.to_zone, "label": t.label.value,
                         "from_observation_id": t.from_observation_id, "to_observation_id": t.to_observation_id}
                        for t in transitions(ctx.store, obj.object_instance_id)],
        "unobserved_intervals": [{"start": iso(g.start_ms), "end": iso(g.end_ms), "reason": g.reason,
                                  "covering_camera_ids": g.covering_camera_ids} for g in gaps],
    }  # fmt: skip


def _existing_finding(ctx: ToolContext, statement: str, obs_ids: list[str]) -> VerifiedFinding | None:
    for f in ctx.store.find(VerifiedFinding, case_id=ctx.case.case_id):
        if f.statement == statement and f.observation_ids == obs_ids and not ctx.store.is_invalid(f.finding_id):
            return f
    return None


def _request(ctx: ToolContext, role: AgentRole, question: str, tools: list[str], steps: int,
             cfg: InvestigationConfig) -> AgentRequest:  # fmt: skip
    return AgentRequest(case_id=ctx.case.case_id, request_id=new_id("agent_request"), role=role, question=question,
                        evidence_scope=ctx.scope, available_tools=tools, token_budget=cfg.token_budget,
                        max_steps=steps, deadline=ctx.now() + timedelta(seconds=cfg.deadline_s),
                        output_schema="EvidenceBundle" if role == AgentRole.EVIDENCE else "HypothesisSet")


def investigate(
    ctx: ToolContext,
    *,
    evidence_backend: JsonBackend | None = None,
    hypothesis_backend: JsonBackend | None = None,
    config: InvestigationConfig | None = None,
) -> InvestigationResult:
    cfg = config or InvestigationConfig()
    zones = {z.zone_id: z.name for z in ctx.site.zones}
    objects = ctx.store.find(ObjectInstance, case_id=ctx.case.case_id)
    if ctx.scope.object_instance_ids:
        objects = [o for o in objects if o.object_instance_id in ctx.scope.object_instance_ids]
    if not objects:
        return InvestigationResult("abstained", "No target object is registered for this case; nothing to "
                                   "investigate.", [], [], [], [], [], None)  # fmt: skip

    window = _case_window(ctx)
    facts = {o.object_instance_id: _facts(ctx, o, window) for o in objects}
    findings: list[VerifiedFinding] = []
    answers: list[ObjectAnswer] = []
    changed: list[str] = []

    # 1. Deterministic baseline: last visibly confirmed position, verified and promoted.
    for obj in objects:
        f = facts[obj.object_instance_id]
        finding, text = None, "Never visibly confirmed in the available, synchronized footage."
        if (oid := f["last_confirmed_observation_id"]) is not None:
            claim = LastSeenClaim(statement="last visibly confirmed", object_instance_id=obj.object_instance_id,
                                  observation_id=oid)  # fmt: skip
            statement = ctx.verifier.describe(claim)
            result = ctx.verifier.verify(claim)
            finding = _existing_finding(ctx, statement, [oid]) or ctx.verifier.promote(
                claim, result, case_id=ctx.case.case_id, now=ctx.now())
            text = statement if finding else f"Last-seen check: {result.verdict.value} ({'; '.join(result.reasons)})"
            if finding:
                findings.append(finding)
                changed.append(finding.finding_id)
        answers.append(ObjectAnswer(
            obj.object_instance_id, obj.label, finding, text, "not_established",
            [f"{zones.get(t['from'], t['from'])} -> {zones.get(t['to'], t['to'])}" for t in f["transitions"]
             if t["label"] == "observed"],
            f["unobserved_intervals"],
        ))  # fmt: skip

    by_object = {a.object_instance_id: a for a in answers}
    runs: dict[str, dict] = {}
    rejected: list[str] = []
    outcomes: list[HypothesisOutcome] = []
    request_ids: list[str] = []

    # 2. Evidence agent (optional).
    bundle: EvidenceBundle | None = None
    if evidence_backend is not None:
        ctx.agent_actor = Actor(kind=ActorKind.AGENT, id="evidence", model=evidence_backend.model)
        req = _request(ctx, AgentRole.EVIDENCE, ctx.case.question, EVIDENCE_TOOLS, cfg.evidence_max_steps, cfg)
        run = AgentRunner(evidence_backend, ctx, system_prompt=EVIDENCE_PROMPT, output=EvidenceBundle).run(req)
        runs["evidence"] = _run_summary(run)
        bundle = run.output

    # 3. Hypothesis agent (optional) -> stored hypotheses -> deterministic verification.
    if hypothesis_backend is not None:
        actor = Actor(kind=ActorKind.AGENT, id="hypothesis", model=hypothesis_backend.model)
        ctx.agent_actor = actor
        question = json.dumps({"question": ctx.case.question, "verified_facts": list(facts.values()),
                               "evidence_summary": bundle.model_dump() if bundle else None,
                               "zones": [{"zone_id": z.zone_id, "name": z.name, "kind": z.kind.value}
                                         for z in ctx.site.zones]}, default=str)  # fmt: skip
        req = _request(ctx, AgentRole.HYPOTHESIS, question, HYPOTHESIS_TOOLS, cfg.hypothesis_max_steps, cfg)
        run = AgentRunner(hypothesis_backend, ctx, system_prompt=HYPOTHESIS_PROMPT, output=HypothesisSet).run(req)
        runs["hypothesis"] = _run_summary(run)
        proposed = run.output.hypotheses[: cfg.max_hypotheses] if run.output else []
        for p in proposed:
            if hits := find_forbidden(p.claim):
                rejected.append(f"hypothesis rejected (identity/intent language {sorted({t for _, t in hits})}): "
                                f"{p.claim[:120]}")  # fmt: skip
                continue
            claims, bad = [], []
            case_objects = {o.object_instance_id for o in objects}
            for spec in p.claims:
                try:
                    claim = spec.to_claim()
                except (ValidationError, ValueError) as e:
                    bad.append(f"malformed claim '{spec.statement[:60]}': {str(e)[:120]}")
                    continue
                if (oid := getattr(claim, "object_instance_id", None)) is not None and oid not in case_objects:
                    bad.append(f"claim about an object outside this case rejected: {oid}")
                    continue
                if foreign := [i for i in _obs_ids(claim) if not _on_site(ctx, i)]:
                    bad.append(f"claim cites evidence outside this case's site: {foreign[:3]}")
                    continue
                claims.append(claim)
            rejected += bad
            support = sorted({i for c in claims for i in _obs_ids(c) if ctx.store.exists(i)})
            h = ctx.store.put(Hypothesis(hypothesis_id=new_id("hypothesis"), case_id=ctx.case.case_id,
                                         claim=p.claim, support_observation_ids=support,
                                         missing_evidence=p.missing_evidence, proposed_by=actor,
                                         created_at=ctx.now()))  # fmt: skip
            changed.append(h.hypothesis_id)
            status, results = ctx.verifier.decide(h.hypothesis_id, claims, now=ctx.now(),
                                                  unchecked_claims=len(p.claims) - len(claims))  # fmt: skip
            verified = [ctx.verifier.describe(c) for c, r in zip(claims, results, strict=True)
                        if r.verdict.value == "supported"]  # fmt: skip
            outcomes.append(HypothesisOutcome(h.hypothesis_id, p.claim, status,
                                              [r for res in results for r in res.reasons] + bad,
                                              p.missing_evidence, verified))  # fmt: skip
            for c, res in zip(claims, results, strict=True):
                ans = by_object.get(getattr(c, "object_instance_id", ""))
                if c.kind != "exit" or ans is None:
                    continue
                if res.verdict.value == "supported":
                    ans.left_area = "supported"
                    if fnd := ctx.verifier.promote(c, res, case_id=ctx.case.case_id, now=ctx.now()):
                        findings.append(fnd)
                elif res.verdict.value == "contradicted" and ans.left_area != "supported":
                    ans.left_area = "contradicted"
            if status == HypothesisStatus.INSUFFICIENT_EVIDENCE and p.distinguishing_request:
                d = p.distinguishing_request
                try:
                    out = t_request_evidence(ctx, EvidenceRequestArgs(camera_id=d.camera_id, start_iso=d.start_iso,
                                                                      end_iso=d.end_iso, reason=d.reason))
                    request_ids.append(out["evidence_request_id"])
                except (ValueError, ValidationError) as e:
                    rejected.append(f"evidence request rejected: {str(e)[:120]}")

    # 4. Record a case revision and compose the answer from verified state only.
    head = ctx.store.head_revision(ctx.case.case_id)
    rev = ctx.store.append_revision(ctx.case.case_id, expected_parent=head.case_revision_id if head else None,
                                    actor=ORCHESTRATOR, reason="investigation run", changed_ids=changed,
                                    now=ctx.now())  # fmt: skip
    answered = any(a.last_seen_finding for a in answers)
    return InvestigationResult(
        "answered" if answered else "abstained", compose_answer(answers, outcomes, request_ids),
        answers, findings, outcomes, request_ids, rejected, rev.case_revision_id, runs,
    )


def _on_site(ctx: ToolContext, observation_id: str) -> bool:
    try:
        ctx.observation(observation_id)
    except ScopeError:
        return not ctx.store.exists(observation_id)  # unknown ids are left for the verifier to reject as unresolved
    return True


def _obs_ids(claim) -> list[str]:
    ids = []
    for name in ("observation_id", "from_observation_id", "to_observation_id", "first_observation_id",
                 "second_observation_id"):  # fmt: skip
        if (v := getattr(claim, name, None)) is not None:
            ids.append(v)
    return ids + list(getattr(claim, "observation_ids", []) or [])


def compose_answer(answers: list[ObjectAnswer], outcomes: list[HypothesisOutcome], request_ids: list[str]) -> str:
    lines = []
    for a in answers:
        lines.append(f"[{a.label}] {a.last_seen_text.rstrip('.')}.")
        if a.observed_moves:
            lines.append("  Observed movement (continuous tracking): " + "; ".join(a.observed_moves) + ".")
        blind = [u for u in a.unobserved if u["reason"] == "no_camera_coverage"]
        unconfirmed = [u for u in a.unobserved if u["reason"] != "no_camera_coverage"]
        if unconfirmed:
            lines.append(f"  Not visible during {len(unconfirmed)} recorded interval(s); position then is unknown.")
        if blind:
            lines.append(f"  {len(blind)} interval(s) had no camera coverage at all.")
        lines.append({
            "supported": "  Leaving the area: supported by footage beyond the door.",
            "contradicted": "  Leaving the area: contradicted by later in-room footage.",
            "not_established": "  Leaving the area: NOT established by the available evidence.",
        }[a.left_area])  # fmt: skip
    for o in outcomes:
        # Agent wording is shown as wording, never as a verified statement; verified checks are generated text.
        lines.append(f"Hypothesis ({o.status.value}) — agent's wording: \"{o.claim}\"")
        for check in o.verified_checks:
            lines.append(f"  verified: {check}")
    if request_ids:
        lines.append(f"{len(request_ids)} evidence request(s) await an authorized import.")
    return "\n".join(lines)
