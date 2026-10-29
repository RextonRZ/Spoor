"""Smoke 1: the key can see the models Spoor depends on."""

from _common import meta_client, record

from spoor.config import get_settings

REQUIRED = {get_settings().spark_model, get_settings().sam_model}

models = sorted(m.id for m in meta_client().models.list())
missing = REQUIRED - set(models)
record("list_models", {"models": models, "required": sorted(REQUIRED), "missing": sorted(missing)})
print("available:", models)
print("MISSING:" if missing else "OK: all required models listed", sorted(missing) if missing else "")
