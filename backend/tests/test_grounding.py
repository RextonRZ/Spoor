"""J3 search grounding: only cited sentences are kept, sources keep one number across answers, cost is recorded, the
report shows the context as dated background (never evidence), and no-key mode is honest."""

from types import SimpleNamespace

from builders import World
from fastapi.testclient import TestClient

from spoor.api.app import create_app
from spoor.api.auth import Principal, Role, TokenRegistry
from spoor.api.services import Services
from spoor.config import Settings
from spoor.contracts import ContextSource
from spoor.grounding import ground_legal_context, latest_legal_context, parse_grounded
from spoor.reports import build_report, render_html
from spoor.store import EvidenceStore

ACT = "https://lom.agc.gov.my/ilims/upload/portal/akta/outputaktap/act741.pdf"
BLOG = "https://www.example-courier-news.com/claims"


def test_parse_keeps_only_cited_sentences_and_strips_links():
    sources: dict[str, ContextSource] = {}
    text = (f"The Act gives MCMC licensing powers under s. 10 [Act 741]({ACT}). "
            f"Licensees answer for loss as set by regulations ({BLOG}). An uncited claim.")  # fmt: skip
    notes = [{"type": "url_citation", "url": ACT, "title": "Act 741", "start_index": 48, "end_index": 60},
             {"type": "url_citation", "url": BLOG, "title": "Courier claims", "start_index": 160, "end_index": 170}]  # fmt: skip
    kept, dropped, narration = parse_grounded(text, notes, sources)
    assert [s.text for s in kept] == ["The Act gives MCMC licensing powers under s. 10.",
                                      "Licensees answer for loss as set by regulations."]  # fmt: skip
    assert [s.sources for s in kept] == [[1], [2]] and dropped == 1 and narration == 0
    assert (
        sources[ACT].official
        and not sources[BLOG].official
        and sources[BLOG].domain == "example-courier-news.com"
    )


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        i = len(self.calls)
        text = f"Answer {i} is cited [src]({ACT}). Answer {i} part two is not."
        return {"id": f"resp_{i}", "usage": {"input_tokens": 1000, "output_tokens": 200},
                "output": [{"type": "web_search_call", "id": f"ws_{i}", "status": "completed"},
                           {"type": "message", "content": [{"type": "output_text", "text": text, "annotations": [
                               {"type": "url_citation", "url": ACT, "title": "Act 741", "start_index": 0, "end_index": 10}]}]}]}  # fmt: skip


def test_ground_records_sources_once_and_prices_searches(site, now):
    client = SimpleNamespace(responses=FakeResponses())
    rec, usage = ground_legal_context(client, site.site_id, now=now, questions=["q1", "q2"])
    call = client.responses.calls[0]
    assert call["model"] == "muse-spark-1.3" and call["tools"][0]["type"] == "web_search"
    assert len(rec.sources) == 1 and [s.sources for a in rec.answers for s in a.sentences] == [[1], [1]]
    assert [a.dropped_uncited for a in rec.answers] == [1, 1] and rec.searches == 2
    assert usage == {"input_tokens": 2000, "output_tokens": 400}
    assert rec.usd_estimate == round(2000 * 1.25e-6 + 400 * 4.25e-6 + 2 * 0.0025, 4)
    assert rec.response_ids == ["resp_1", "resp_2"] and rec.retrieved_at == now


def test_report_shows_context_as_dated_background(site, now):
    w = World(EvidenceStore(), site, now)
    html_before = render_html(build_report(w.store, w.case.case_id, site=site, now=now), status="draft")
    assert "Not retrieved" in html_before
    rec, _ = ground_legal_context(
        SimpleNamespace(responses=FakeResponses()), site.site_id, now=now, questions=["q1"]
    )
    w.store.put(rec)
    assert latest_legal_context(w.store, site.site_id) == rec
    report = build_report(w.store, w.case.case_id, site=site, now=now)
    assert report["legal_context"]["content_sha256"] == rec.content_sha256
    out = render_html(report, status="draft")
    assert "Malaysian context" in out and "<sup>[1]</sup>" in out and "lom.agc.gov.my · official" in out
    assert "Not case evidence" in out and "1 uncited sentence(s) left out" in out


def test_api_no_key_is_honest(tmp_path):
    svc = Services.from_settings(Settings(data_dir=tmp_path, model_api_key=None, agent_backend="none"))
    svc.tokens = TokenRegistry({"t-admin": Principal("admin", Role.SITE_ADMIN, frozenset({"site_demo"})),
                                "t-inv": Principal("inv", Role.INVESTIGATOR, frozenset({"site_demo"}))})  # fmt: skip
    c = TestClient(create_app(services=svc))
    auth = lambda t: {"Authorization": f"Bearer {t}"}
    assert c.post("/v1/sites/site_demo/legal-context", headers=auth("t-inv")).status_code == 403
    r = c.post("/v1/sites/site_demo/legal-context", headers=auth("t-admin"))
    assert r.status_code == 503 and "no API key" in r.json()["detail"]
    got = c.get("/v1/sites/site_demo/legal-context", headers=auth("t-inv")).json()
    assert (
        got["context"] is None and got["available"] is False and got["estimate"]["model"] == "muse-spark-1.3"
    )


def test_narration_is_dropped_and_orphan_sources_pruned(site, now):
    """First J3 run: tool narration ("Now I'll open…") was glued to a cited sentence; it goes, never edited."""
    from spoor.contracts import ContextAnswer, ContextSentence, LegalContext
    from spoor.grounding import strip_narration

    src = [
        ContextSource(n=1, url=ACT, title="Act 741", domain="lom.agc.gov.my", official=True),
        ContextSource(n=2, url=BLOG, title="Blog", domain="example-courier-news.com", official=False),
    ]
    rec = LegalContext(legal_context_id="lctx_old", site_id=site.site_id, model="muse-spark-1.3", response_ids=[],
                       answers=[ContextAnswer(question="q", searches=1, dropped_uncited=0, sentences=[
                           ContextSentence(text="Now I'll open the documents.MCMC oversees couriers.", sources=[1]),
                           ContextSentence(text="Claims follow the courier's terms.", sources=[2])])],
                       sources=src, searches=1, usd_estimate=0.1, retrieved_at=now, content_sha256="0" * 64)  # fmt: skip
    new = strip_narration(rec)
    assert [s.text for s in new.answers[0].sentences] == ["Claims follow the courier's terms."]
    assert new.answers[0].dropped_narration == 1 and new.answers[0].sentences[0].sources == [1]
    assert [(s.n, s.url) for s in new.sources] == [(1, BLOG)] and new.legal_context_id != "lctx_old"
    assert new.retrieved_at == now and new.content_sha256 != rec.content_sha256


def test_four_eyes_is_a_site_setting(site, now):
    """Review F-047..051: real sites keep the second approver (DRAFT banner until approved); the one-user demo site
    turns it off and its shared report reads as an investigation summary."""
    w = World(EvidenceStore(), site, now)
    report = build_report(w.store, w.case.case_id, site=site, now=now)
    assert site.require_second_approver is True
    on = render_html(report, status="draft")
    off = render_html(report, status="draft", second_approver=False)
    assert "DRAFT · not reviewer-approved" in on and "DRAFT" not in off and "Investigation summary" in off


def test_spend_sums_the_cost_ledger(tmp_path):
    """Proof of spend: the ledger summed by provider/model/job; the open-weights share counts Baseten calls."""
    from datetime import UTC, datetime

    svc = Services.from_settings(Settings(data_dir=tmp_path, model_api_key=None, agent_backend="none"))
    svc.tokens = TokenRegistry({"t-admin": Principal("admin", Role.SITE_ADMIN, frozenset({"site_demo"}))})
    from spoor.store import CostEntry

    at = datetime(2026, 10, 31, 1, 0, tzinfo=UTC)
    svc.store.put(CostEntry(cost_id="cost_a", provider="meta_model_api", model="muse-spark-1.3", request_kind="legal_context_grounding",
                            input_tokens=10, output_tokens=5, usd_estimate=0.5, at=at))
    svc.store.put(CostEntry(cost_id="cost_b", provider="baseten", model="muse-spark-open", request_kind="agent", input_tokens=7,
                            output_tokens=3, usd_estimate=0.25, at=at))
    got = TestClient(create_app(services=svc)).get("/v1/spend", headers={"Authorization": "Bearer t-admin"}).json()
    assert got["total_usd"] == 0.75 and got["calls"] == 2 and got["open_weights_share"] == 0.5
    assert got["rows"][0]["job"] == "legal_context_grounding" and got["rows"][0]["input_tokens"] == 10
