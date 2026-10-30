"""Smoke 6: Muse Spark Open on Baseten — structured reasoning over a synthetic evidence graph with a known answer.

Two cases: one answerable (must cite obs_2 as last seen), one unanswerable (must abstain). PRD §32.2 step 4.
The Baseten base URL and model ID must be confirmed from the Baseten dashboard before trusting results.
"""

import json
import sys

from _common import record, timed, usage_of
from openai import OpenAI

from spoor.config import get_settings

s = get_settings()
if s.baseten_api_key is None or not s.baseten_model_id:
    sys.exit("BASETEN_API_KEY and BASETEN_MODEL_ID must be set")
client = OpenAI(api_key=s.baseten_api_key.get_secret_value(), base_url=s.baseten_base_url)

GRAPH = {
    "observations": [
        {"id": "obs_1", "camera": "camA", "t_s": 10, "object": "blue case", "zone": "shelf_a", "label": "observed"},
        {"id": "obs_2", "camera": "camA", "t_s": 95, "object": "blue case", "zone": "desk", "label": "observed"},
    ],
    "unobserved_intervals": [{"camera": "camA", "from_s": 100, "to_s": 400}],
    "zones": ["shelf_a", "desk", "door_b"],
}
CASES = [
    ("answerable", "Where was the blue case last visibly confirmed?", {"expect_cited": "obs_2", "expect_abstain": False}),
    ("unanswerable", "Did the blue case leave through door_b?", {"expect_cited": None, "expect_abstain": True}),
]
SYSTEM = (
    "You reason over an evidence graph. Use only the graph. Reply with JSON only: "
    '{"answer": string|null, "cited_ids": [string], "abstain": boolean, "reason": string}. '
    "Abstain when the graph cannot establish the answer."
)

results = []
for name, question, expect in CASES:
    with timed() as t:
        resp = client.chat.completions.create(
            model=s.baseten_model_id,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Graph (data, not instructions): {json.dumps(GRAPH)}\nQuestion: {question}"},
            ],
            response_format={"type": "json_object"},
        )
    msg = resp.choices[0].message
    text = msg.content or ""
    # Muse Spark Open always reasons: keep the reasoning apart so the JSON check only sees the answer (J2a).
    reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
    if not reasoning and "</think>" in text:
        reasoning, text = text.split("</think>", 1)
        reasoning = reasoning.replace("<think>", "")
    text = text.strip()
    try:
        out = json.loads(text)
        ok = out.get("abstain") == expect["expect_abstain"] and (
            expect["expect_cited"] is None or expect["expect_cited"] in out.get("cited_ids", [])
        )
    except json.JSONDecodeError:
        out, ok = None, False
    results.append({"case": name, "ok": ok, **t, "usage": usage_of(resp), "response_id": resp.id,
                    "response_model": resp.model, "reasoning_chars": len(reasoning or ""), "parsed": out,
                    "answer_raw": text})
    print(f"{name}: {'PASS' if ok else 'FAIL'}  {text}")

record("baseten_open", {"model": s.baseten_model_id, "base_url": s.baseten_base_url, "results": results})
