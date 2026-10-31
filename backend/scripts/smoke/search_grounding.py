"""Smoke 9 (J3): search grounding for the report's Malaysian context (Muse Spark 1.3 + built-in web_search).

Usage: uv run python scripts/smoke/search_grounding.py <site_id> [--store]
Runs spoor.grounding (3 narrow questions, cited sentences only), records the result in scripts/smoke/out/, and with
--store also writes the LegalContext record (plus its cost entry) to the configured evidence store, so reports for that
site show it. Paid: tokens + $2.50 per 1,000 searches; estimate ≈ $0.06. The context is background, never evidence.
"""

import json
import sys
from datetime import UTC, datetime

from _common import meta_client, record, timed

from spoor.api.services import Services
from spoor.config import get_settings
from spoor.grounding import ESTIMATE, ground_legal_context
from spoor.store import CostEntry

site_id = sys.argv[1]
print(f"estimate: {ESTIMATE['model']} ≈ ${ESTIMATE['usd']} ({ESTIMATE['basis']})")
with timed() as t:
    rec, usage = ground_legal_context(meta_client(), site_id, now=datetime.now(UTC))
out = rec.model_dump(mode="json")
kept = sum(len(a.sentences) for a in rec.answers)
dropped = sum(a.dropped_uncited for a in rec.answers)
official = sum(s.official for s in rec.sources)
print(f"actual: ${rec.usd_estimate} · {usage['input_tokens']} in / {usage['output_tokens']} out · {rec.searches} searches "
      f"· {kept} cited sentences kept, {dropped} uncited dropped · {len(rec.sources)} sources ({official} official) "
      f"· {t['latency_s']} s")  # fmt: skip
record("search_grounding", {"model": rec.model, "usage": usage, "latency_s": t["latency_s"], "record": out})
for a in rec.answers:
    print("\nQ:", a.question)
    for s in a.sentences:
        print("  -", s.text, s.sources)
for s in rec.sources:
    print(f"[{s.n}] {s.title} · {s.domain}{' · official' if s.official else ''} · {s.url}")
if "--store" in sys.argv:
    svc = Services.from_settings(get_settings())
    svc.store.put(rec)
    svc.store.put(CostEntry(cost_id=f"cost_{rec.legal_context_id}", provider="meta_model_api", model=rec.model,
                            request_kind="legal_context_grounding", response_id=(rec.response_ids or [None])[0],
                            input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"],
                            billed_units=rec.searches, unit="tokens + web searches", usd_estimate=rec.usd_estimate,
                            at=rec.retrieved_at))  # fmt: skip
    print("stored", rec.legal_context_id, json.dumps({"sha256": rec.content_sha256}))
