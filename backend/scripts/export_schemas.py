"""Export the evidence contract as JSON Schema files: uv run python scripts/export_schemas.py"""

import json
from pathlib import Path

from spoor.contracts import SCHEMA_MODELS

OUT = Path(__file__).resolve().parents[1] / "schemas"
OUT.mkdir(exist_ok=True)
for model in SCHEMA_MODELS:
    path = OUT / f"{model.__name__}.schema.json"
    path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
print(f"wrote {len(SCHEMA_MODELS)} schemas to {OUT}")
