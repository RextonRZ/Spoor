"""The customer update: verified answer only, safety terms never reach the customer, nothing without an answer."""

from datetime import UTC, datetime
from types import SimpleNamespace

from spoor.customer import draft
from spoor.store import AgentStep, EvidenceStore

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
INSIDE = {"place": "Exception store (Z11)", "iso": {"carried_in_at": "2026-10-28T14:32:31.750+08:00"}}


def case_with(answer: dict | None):
    store = EvidenceStore()
    case = SimpleNamespace(case_id="case_x", target_description="parcel CTX100200300400")
    if answer is not None:
        store.put(AgentStep(step_id="answer_x", case_id="case_x", request_id="r", seq=1, role="investigation",
                            kind="final", content=answer, at=NOW))
    return store, case


class Model:
    model = "spark-open-test"

    def __init__(self, words):
        self.words = words

    def complete(self, **_):
        return SimpleNamespace(data=SimpleNamespace(message=self.words))


def test_drafts_from_the_verified_answer_and_keeps_the_model_words_when_safe():
    store, case = case_with({"objects": [{"inside": INSIDE}]})
    out = draft(store, case, Model("Hello. Your parcel CTX100200300400 is at the hub and will be sent on soon."), now=NOW)
    assert out["status"] == "drafted" and out["model"] == "spark-open-test" and not out["sent"]
    assert any("exception store" in f and "28 Oct at 14:32" in f for f in out["facts"])


def test_unsafe_model_words_fall_back_to_the_plain_template():
    store, case = case_with({"objects": [{"inside": INSIDE}]})
    out = draft(store, case, Model("A worker stole your parcel."), now=NOW)
    assert out["model"] == "template" and "plain template used" in out["note"] and "stole" not in out["draft"]


def test_no_verified_answer_means_nothing_to_tell():
    store, case = case_with({"objects": [{"inside": None, "last_scan": {"located_by": "scan", "at": NOW.isoformat()}}]})
    assert draft(store, case, None, now=NOW)["status"] == "no_answer"
