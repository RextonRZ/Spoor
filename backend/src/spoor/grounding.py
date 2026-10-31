"""Search grounding for the report's Malaysian context (QUEUE J3).

Muse Spark 1.3 answers a few narrow questions with the Model API's built-in `web_search` tool (Responses API,
`tools=[{"type": "web_search"}]`; citations arrive as `url_citation` annotations with character offsets into the answer
text, per dev.meta.ai/docs/search-grounding). One request per question: the docs advise narrow queries over one
multi-hop request.

Deterministic check before anything is stored: the answer is split into sentences; a sentence is kept only if a citation
falls on it, and the rest are dropped and counted. Inline markdown links and bare URLs are removed from the shown text
(the [n] numbers carry the source). Sources on .gov.my are marked official. The result is background for the report
reader, never case evidence, and it is dated."""

import hashlib
import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from spoor.contracts import ContextAnswer, ContextSentence, ContextSource, LegalContext, new_id

MODEL = "muse-spark-1.3"  # standard mode: Contributor mode is only for synthetic footage (QUEUE keys rule)
PRICE = {
    "in": 1.25e-6,
    "out": 4.25e-6,
    "search": 2.50 / 1000,
}  # dev.meta.ai/docs/pricing-rate-limits, 31 Oct 2026
ESTIMATE = {
    "model": MODEL,
    "usd": 1.00,
    "basis": "measured 31 Oct 2026: 3 questions, 52 searches, 654k input tokens (search results) + 12k output = $1.00",
}

SYSTEM = ("You answer questions about Malaysian law and regulation for the background section of a lost-parcel "
          "investigation report. Use web search. Prefer official sources: lom.agc.gov.my (Laws of Malaysia; cite it "
          "for statute text, not mirror copies), "
          "mcmc.gov.my, other .gov.my sites. Answer in at most 5 short plain sentences. Every sentence must carry a "
          "citation. If a point cannot be found in a source, say so instead of guessing. Give the act or standard name "
          "and section where you can. No legal advice.")  # fmt: skip

QUESTIONS = [
    (
        "Under Malaysia's Postal Services Act 2012 (Act 741), what is the Malaysian Communications and Multimedia "
        "Commission's (MCMC) role over courier and parcel delivery licensees, and what does the Act say about a "
        "licensee's liability for the loss of or damage to a postal article?"
    ),
    (
        "In Malaysia, how does a consumer complain about a lost courier parcel: what must they do first with the courier "
        "company, within what time limits, and when can they escalate the complaint to MCMC?"
    ),
    (
        "What compensation limits or claim time limits apply in Malaysia to a lost domestic courier parcel under MCMC's "
        "courier service standards (for example a mandatory standard on quality of service) or the courier's own terms?"
    ),
]

_END = re.compile(
    r"[.!?]+(?=\s+[A-Z(\"']|\s*$)"
)  # a sentence ends before a capital, not at "s. 10" or "No. 5"
_MD_LINK = re.compile(r"\s*\(?\[([^\]]*)\]\((https?://[^)]+)\)\)?")
_URL = re.compile(r"\s*\(?https?://[^\s)]+\)?")
# the model narrating its own tool use ("Now I'll open the official documents…") is not an answer sentence
_NARRATION = re.compile(r"\b(I'll|I will|I'm going to|Let me|I need to|I'll now)\b")


def _get(o: Any, k: str, default: Any = None) -> Any:
    return o.get(k, default) if isinstance(o, dict) else getattr(o, k, default)


def _clean(text: str) -> str:
    text = _MD_LINK.sub("", text)
    text = _URL.sub("", text)
    return re.sub(r"\s+([.,;:])", r"\1", re.sub(r"\s{2,}", " ", text)).strip()


def parse_grounded(
    text: str, annotations: list[Any], sources: dict[str, ContextSource]
) -> tuple[list[ContextSentence], int, int]:
    """(kept cited sentences, dropped uncited, dropped narration). `sources` (url → source) is shared across answers so
    a URL keeps one number in the whole report; `_finalize` later drops sources no kept sentence cites."""
    # links blanked to spaces of the same length: offsets stay valid and the dots in URLs never end a sentence
    masked = _MD_LINK.sub(lambda m: " " * len(m.group()), text)
    masked = _URL.sub(lambda m: " " * len(m.group()), masked)
    cuts = [0] + [m.end() for m in _END.finditer(masked)]
    spans = [
        (a, b)
        for a, b in zip(cuts, cuts[1:] + ([len(masked)] if cuts[-1] < len(masked) else []))
        if masked[a:b].strip()
    ]
    cited: dict[int, list[int]] = {}
    for a in annotations:
        if _get(a, "type") != "url_citation" or not _get(a, "url"):
            continue
        url, start = _get(a, "url"), int(_get(a, "start_index", 0) or 0)
        if url not in sources:
            dom = (urlparse(url).hostname or "").removeprefix("www.")
            sources[url] = ContextSource(n=len(sources) + 1, url=url, title=(_get(a, "title") or dom)[:200], domain=dom,
                                         official=dom.endswith(".gov.my"))  # fmt: skip
        # the sentence the citation starts in; a citation in the gap after a sentence belongs to that sentence
        idx = max((i for i, (s, _) in enumerate(spans) if s <= start), default=0)
        n = sources[url].n
        if n not in cited.setdefault(idx, []):
            cited[idx].append(n)
    kept, narration = [], 0
    for i, (s, e) in enumerate(spans):
        shown = _clean(masked[s:e])
        if shown and _NARRATION.search(shown):
            narration += 1
        elif i in cited and shown:
            kept.append(ContextSentence(text=shown, sources=sorted(cited[i])))
    return kept, len(spans) - len(kept) - narration, narration


def _finalize(
    answers: list[ContextAnswer], sources: list[ContextSource]
) -> tuple[list[ContextAnswer], list[ContextSource]]:
    """Drop sources no kept sentence cites and renumber the rest 1..n in order of first use."""
    order: dict[int, int] = {}
    for a in answers:
        for s in a.sentences:
            for n in s.sources:
                order.setdefault(n, len(order) + 1)
    by_n = {s.n: s for s in sources}
    answers = [a.model_copy(update={"sentences": [s.model_copy(update={"sources": sorted(order[n] for n in s.sources)})
                                                  for s in a.sentences]}) for a in answers]  # fmt: skip
    return answers, [
        by_n[old].model_copy(update={"n": new}) for old, new in sorted(order.items(), key=lambda kv: kv[1])
    ]


def _record(
    site_id: str, answers: list[ContextAnswer], sources: list[ContextSource], **kw: Any
) -> LegalContext:
    answers, sources = _finalize(answers, sources)
    body = {"answers": [a.model_dump() for a in answers], "sources": [s.model_dump() for s in sources],
            "retrieved_at": kw["retrieved_at"].isoformat(), "model": kw["model"]}  # fmt: skip
    return LegalContext(site_id=site_id, answers=answers, sources=sources,
                        content_sha256=hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(), **kw)  # fmt: skip


def strip_narration(rec: LegalContext) -> LegalContext:
    """Apply the narration rule to a record made before it existed (the first J3 run): such sentences are removed,
    never edited; orphaned sources go and the rest are renumbered. A new id and hash: it is a new version."""
    answers = []
    for a in rec.answers:
        keep = [s for s in a.sentences if not _NARRATION.search(s.text)]
        answers.append(
            a.model_copy(
                update={
                    "sentences": keep,
                    "dropped_narration": a.dropped_narration + len(a.sentences) - len(keep),
                }
            )
        )
    kw = rec.model_dump(exclude={"site_id", "answers", "sources", "content_sha256", "legal_context_id"})
    return _record(rec.site_id, answers, rec.sources, legal_context_id=new_id("legal_context"), **kw)


def _answer_parts(resp: Any) -> tuple[str, list[Any], int]:
    """(answer text, url_citation annotations, number of web searches) from a Responses API result."""
    text, notes, searches = "", [], 0
    for item in _get(resp, "output", []) or []:
        kind = _get(item, "type")
        if kind == "web_search_call":
            searches += 1
        elif kind == "message":
            text, notes = "", []  # only the final message is the answer; earlier ones narrate the search
            for part in _get(item, "content", []) or []:
                if _get(part, "type") == "output_text":
                    off = len(text)
                    text += _get(part, "text", "") or ""
                    for a in _get(part, "annotations", []) or []:
                        d = a if isinstance(a, dict) else a.model_dump()
                        notes.append({**d, "start_index": (d.get("start_index") or 0) + off})
    return text, notes, searches


def ground_legal_context(
    client: Any, site_id: str, *, now: datetime, questions: list[str] = QUESTIONS
) -> tuple[LegalContext, dict]:
    """Run the grounded questions (paid: tokens + $2.50 per 1,000 searches). Returns the record and token usage."""
    sources: dict[str, ContextSource] = {}
    answers, ids, tin, tout, searches = [], [], 0, 0, 0
    for q in questions:
        resp = client.responses.create(model=MODEL, instructions=SYSTEM, input=q,
                                       tools=[{"type": "web_search", "user_location": {"type": "approximate", "country": "MY"}}])  # fmt: skip
        text, notes, n = _answer_parts(resp)
        sentences, dropped, narration = parse_grounded(text, notes, sources)
        answers.append(ContextAnswer(question=q, sentences=sentences, dropped_uncited=dropped,
                                     dropped_narration=narration, searches=n))  # fmt: skip
        usage = _get(resp, "usage")
        tin += int(_get(usage, "input_tokens", 0) or 0)
        tout += int(_get(usage, "output_tokens", 0) or 0)
        searches += n
        if _get(resp, "id"):
            ids.append(_get(resp, "id"))
    usd = round(tin * PRICE["in"] + tout * PRICE["out"] + searches * PRICE["search"], 4)
    rec = _record(site_id, answers, list(sources.values()), legal_context_id=new_id("legal_context"), model=MODEL,
                  response_ids=ids, searches=searches, usd_estimate=usd, retrieved_at=now)  # fmt: skip
    return rec, {"input_tokens": tin, "output_tokens": tout}


def latest_legal_context(store: Any, site_id: str) -> LegalContext | None:
    recs = store.find(LegalContext, site_id=site_id)
    return max(recs, key=lambda r: r.retrieved_at) if recs else None
