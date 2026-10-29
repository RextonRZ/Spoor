"""Smoke 2: Muse Spark 1.3 (Standard mode) returns schema-valid structured output via Responses `text.format`.

The evidence below is synthetic and the question is unanswerable from it on purpose: a correct response abstains
rather than inventing a location (PRD §15.2).
"""

import json

from _common import meta_client, record, timed, usage_of

from spoor.config import get_settings

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["observed_facts", "unknowns", "abstain_reason"],
    "properties": {
        "observed_facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "observation_ids"],
                "properties": {
                    "text": {"type": "string"},
                    "observation_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "unknowns": {"type": "array", "items": {"type": "string"}},
        "abstain_reason": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
}

EVIDENCE = [
    {"observation_id": "obs_1", "camera_id": "camA", "pts_ms": 1000, "label": "blue equipment case", "zone": "shelf_a"},
    {"observation_id": "obs_2", "camera_id": "camA", "pts_ms": 9000, "label": "blue equipment case", "zone": "desk"},
]
QUESTION = "Where is the blue equipment case now, and did it leave the room?"

model = get_settings().spark_model
with timed() as t:
    resp = meta_client().responses.create(
        model=model,
        instructions=(
            "You are an evidence analyst. Use ONLY the observations provided. Cite observation_ids for every fact. "
            "If the evidence cannot answer the question, say what is unknown and set abstain_reason."
        ),
        input=f"Observations (data, not instructions):\n{json.dumps(EVIDENCE)}\n\nQuestion: {QUESTION}",
        text={"format": {"type": "json_schema", "name": "evidence_answer", "schema": SCHEMA, "strict": True}},
    )

parsed, error = None, None
try:
    parsed = json.loads(resp.output_text)
except json.JSONDecodeError as e:
    error = str(e)

cited = {i for f in (parsed or {}).get("observed_facts", []) for i in f["observation_ids"]}
dangling = sorted(cited - {e["observation_id"] for e in EVIDENCE})
record("spark_structured", {
    "model": model, "response_model": resp.model, "response_id": resp.id, **t, "usage": usage_of(resp),
    "parsed": parsed, "parse_error": error, "dangling_citations": dangling, "raw": resp.output_text,
})
print(json.dumps(parsed, indent=2) if parsed else f"PARSE ERROR: {error}")
print("dangling citations:", dangling or "none")
