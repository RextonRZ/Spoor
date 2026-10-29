"""Step 08 acceptance tests: orchestration, tool scope, budgets, checkpoints, verification and revision history.

ScriptedBackend replays hand-written agent turns (test fixture) — it exercises the real runtime, not a model.
"""

import json
from datetime import timedelta

import pytest
from builders import World

from spoor.agents import InvestigationConfig, ToolContext, investigate
from spoor.agents.roles import EvidenceBundle
from spoor.agents.runtime import AgentRunner
from spoor.contracts import (
    AgentRequest,
    AgentRole,
    AssociationStatus,
    EvidenceScope,
    Hypothesis,
    HypothesisStatus,
)
from spoor.reasoning import BackendError, BackendReply
from spoor.store import AgentStep, EvidenceRequest, EvidenceStore
from spoor.verification import Verifier


class ScriptedBackend:
    provider, model, supports_video = "test", "scripted-fixture", False

    def __init__(self, turns, fail=False):
        self.turns, self.fail, self.prompts = list(turns), fail, []

    def complete(self, *, system, content, output, name):
        self.prompts.append((system, content))
        if self.fail:
            raise BackendError("provider down")
        turn = self.turns.pop(0) if self.turns else {"note": "stall", "action": "call_tool", "tool": "list_case_objects",
                                                       "args_json": "{}", "final_json": None}
        data = output.model_validate(turn)
        return BackendReply(data, json.dumps(turn), self.model, self.provider, None, 100, 20, 0.0)


def call(tool, args=None):
    return {"note": "n", "action": "call_tool", "tool": tool, "args_json": json.dumps(args or {}), "final_json": None}


def final(obj):
    return {"note": "done", "action": "final", "tool": None, "args_json": None, "final_json": json.dumps(obj)}


@pytest.fixture
def scene(site, now):
    w = World(EvidenceStore(), site, now)
    w.camera("cam_a")
    clip = w.clip("cam_a", 0, 20)
    t1 = w.track("cam_a", clip)
    o = {t: w.obs(t1, t, xy=(1.0, 3.6), zone="zone_shelf_a") for t in (0.0, 0.5, 1.0)}
    t2 = w.track("cam_a", clip)
    o |= {t: w.obs(t2, t, xy=(5.5, 0.2), zone="zone_door_b") for t in (10.0, 10.5)}
    obj = w.obj("blue equipment case", t1, t2)
    ctx = ToolContext(store=w.store, site=site, case=w.case, verifier=Verifier(w.store, site), scope=EvidenceScope(),
                      now=lambda: now)  # fmt: skip
    return w, obj, o, ctx


def agent_request(ctx, tools, max_steps=6, budget=10_000, request_id="req_test1"):
    return AgentRequest(case_id="case_w", request_id=request_id, role=AgentRole.EVIDENCE, question="Where is it?",
                        evidence_scope=EvidenceScope(), available_tools=tools, token_budget=budget,
                        max_steps=max_steps, deadline=ctx.now() + timedelta(minutes=5),
                        output_schema="EvidenceBundle")  # fmt: skip


BUNDLE = {"summary": "seen at door", "observation_ids": [], "unknowns": ["10.5 s onward"], "followups": []}


def test_deterministic_baseline_without_any_model(scene):
    w, obj, o, ctx = scene
    res = investigate(ctx)
    assert res.status == "answered" and res.findings[0].observation_ids == [o[10.5]]
    assert "Door B" in res.answer and "NOT established" in res.answer
    assert res.objects[0].left_area == "not_established" and res.revision_id
    assert res.agent_runs == {}


def test_evidence_agent_runs_tools_and_checkpoints(scene):
    w, obj, o, ctx = scene
    backend = ScriptedBackend([call("last_confirmed", {"object_instance_id": obj}),
                               call("visibility_timeline", {"object_instance_id": obj}), final(BUNDLE)])
    run = AgentRunner(backend, ctx, system_prompt="evidence", output=EvidenceBundle).run(
        agent_request(ctx, ["last_confirmed", "visibility_timeline"]))
    assert run.status == "ok" and run.tool_calls == 2 and run.output.unknowns == ["10.5 s onward"]
    kinds = [s.kind for s in w.store.find(AgentStep, request_id="req_test1")]
    assert kinds[0] == "request" and kinds[-1] == "final" and kinds.count("tool_result") == 2
    # Tool results are passed back as untrusted data.
    assert '<untrusted_data name="tool_result:last_confirmed">' in backend.prompts[1][1]
    assert o[10.5] in backend.prompts[1][1]


def test_scope_and_tool_enforcement(scene):
    w, obj, o, ctx = scene
    backend = ScriptedBackend([
        call("delete_case"),
        call("last_confirmed", {"object_instance_id": "objinst_other_case"}),
        call("last_confirmed", {"object_instance_id": obj, "extra": 1}),
        final(BUNDLE),
    ])  # fmt: skip
    run = AgentRunner(backend, ctx, system_prompt="e", output=EvidenceBundle).run(
        agent_request(ctx, ["last_confirmed"]))
    rejected = [s.content["reason"] for s in w.store.find(AgentStep, request_id="req_test1") if s.kind == "rejected"]
    assert len(rejected) == 3 and "not available" in rejected[0] and "unknown object" in rejected[1]
    assert run.status == "ok" and run.tool_calls == 1


def test_repeated_tool_call_served_from_checkpoint(scene):
    w, obj, o, ctx = scene
    backend = ScriptedBackend([call("last_confirmed", {"object_instance_id": obj})] * 2 + [final(BUNDLE)])
    run = AgentRunner(backend, ctx, system_prompt="e", output=EvidenceBundle).run(
        agent_request(ctx, ["last_confirmed"]))
    assert run.tool_calls == 1 and "_from_checkpoint" in backend.prompts[2][1]


def test_budget_exhaustion_stops_agent(scene):
    w, obj, o, ctx = scene
    run = AgentRunner(ScriptedBackend([]), ctx, system_prompt="e", output=EvidenceBundle).run(
        agent_request(ctx, ["list_case_objects"], max_steps=3))
    assert run.status == "budget_exhausted" and run.steps == 3
    run = AgentRunner(ScriptedBackend([]), ctx, system_prompt="e", output=EvidenceBundle).run(
        agent_request(ctx, ["list_case_objects"], budget=200, request_id="req_test2"))
    assert run.status == "budget_exhausted" and run.steps == 2


def claim(kind, statement, obj, **kw):
    base = {"kind": kind, "statement": statement, "object_instance_id": obj, "observation_ids": [], "zone_id": None,
            "door_zone_id": None, "from_observation_id": None, "to_observation_id": None, "asserted_label": None,
            "sensor_event_ids": []}  # fmt: skip
    return base | kw


def hypotheses(obj, o):
    return {"hypotheses": [
        {"claim": "Case moved through Door B", "missing_evidence": ["hallway camera after 10.5 s"],
         "claims": [claim("exit", "Case moved through Door B", obj, door_zone_id="zone_door_b",
                          observation_ids=[o[10.5]])],
         "distinguishing_request": {"camera_id": "cam_a", "start_iso": None, "end_iso": None,
                                    "reason": "Footage beyond Door B after the last sighting"}},
        {"claim": "The suspect stole the case", "missing_evidence": [], "claims": [], "distinguishing_request": None},
        {"claim": "Case went shelf to door unseen", "missing_evidence": [],
         "claims": [claim("transition", "Case went shelf to door", obj, from_observation_id=o[1.0],
                          to_observation_id=o[10.0], asserted_label="observed"),
                    claim("presence", "broken", None)],
         "distinguishing_request": None},
    ]}  # fmt: skip


def test_hypotheses_verified_rejected_and_requests_created(scene):
    w, obj, o, ctx = scene
    hb = ScriptedBackend([final(hypotheses(obj, o))])
    res = investigate(ctx, hypothesis_backend=hb)
    by_claim = {h.claim: h for h in res.hypotheses}
    assert by_claim["Case moved through Door B"].status == HypothesisStatus.INSUFFICIENT_EVIDENCE
    assert by_claim["Case went shelf to door unseen"].status == HypothesisStatus.INSUFFICIENT_EVIDENCE
    assert "The suspect stole the case" not in by_claim and "suspect" not in res.answer
    assert any("identity/intent" in r for r in res.rejected) and any("malformed" in r for r in res.rejected)
    assert len(res.evidence_request_ids) == 1 and w.store.find(EvidenceRequest, case_id="case_w")
    stored = w.store.find(Hypothesis, case_id="case_w")
    assert all(h.proposed_by.kind == "agent" and h.proposed_by.model == "scripted-fixture" for h in stored)
    # Ground truth never appears in prompts: only store-derived facts and the case question.
    assert "ground_truth" not in hb.prompts[0][0] + hb.prompts[0][1]


def test_new_evidence_revises_without_deleting_history(scene):
    w, obj, o, ctx = scene
    first = investigate(ctx, hypothesis_backend=ScriptedBackend([final(hypotheses(obj, o))]))
    assert first.objects[0].left_area == "not_established"
    # Authorized import of a hallway camera (C06-style revision).
    w.camera("cam_hall")
    th = w.track("cam_hall", w.clip("cam_hall", 0, 30))
    out = w.obs(th, 13.0, xy=(5.0, -1.0), zone="zone_hall")
    w.link(obj, th, AssociationStatus.HUMAN_CONFIRMED)
    revised = {"hypotheses": [{"claim": "Case moved through Door B", "missing_evidence": [],
                               "claims": [claim("exit", "Case moved through Door B into the hallway", obj,
                                                door_zone_id="zone_door_b", observation_ids=[o[10.5], out])],
                               "distinguishing_request": None}]}  # fmt: skip
    second = investigate(ctx, hypothesis_backend=ScriptedBackend([final(revised)]))
    assert second.objects[0].left_area == "supported" and "supported by footage beyond" in second.answer
    assert second.findings[0].observation_ids == [out]  # last seen is now the hallway sighting
    # Earlier hypotheses (2 stored; the accusatory one was rejected) are retained alongside the new one.
    assert len(w.store.find(Hypothesis, case_id="case_w")) == 3
    assert w.store.head_revision("case_w").parent_revision_id == first.revision_id


def test_backend_failure_keeps_deterministic_answer(scene):
    w, obj, o, ctx = scene
    res = investigate(ctx, evidence_backend=ScriptedBackend([], fail=True),
                      hypothesis_backend=ScriptedBackend([], fail=True), config=InvestigationConfig())
    assert res.status == "answered" and res.agent_runs["evidence"]["status"] == "error"
    assert res.hypotheses == []
