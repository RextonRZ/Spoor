"""Optional sensor ingestion (PRD §20, step 11a). CSV first; every row must say whether it is real or simulated.

Expected header: device_id,kind,value,zone_id,device_time_utc,clock_quality,source
  kind   = door_contact | weight_delta_kg | rfid_tag_seen | motion_trigger
  source = real | simulated   (no default: an unlabelled row is rejected, PRD §8.1)
"""

import csv
import io
from datetime import datetime

from pydantic import ValidationError

from spoor.contracts import SensorEvent, SensorKind, SourceType, new_id

REQUIRED = ["device_id", "kind", "value", "zone_id", "device_time_utc", "clock_quality", "source"]
MAX_ROWS = 100_000


class SensorImportError(ValueError):
    pass


def _value(kind: SensorKind, raw: str) -> str | float | bool:
    raw = raw.strip()
    if kind == SensorKind.WEIGHT_DELTA_KG:
        return float(raw)
    if kind == SensorKind.DOOR_CONTACT:
        if raw.lower() not in ("open", "closed"):
            raise ValueError("door_contact value must be open|closed")
        return raw.lower()
    if kind == SensorKind.MOTION_TRIGGER:
        return raw.lower() in ("1", "true", "yes", "on")
    return raw  # rfid tag id (consented tagged equipment only)


def parse_sensor_csv(text: str, *, import_batch: str, site_id: str) -> list[SensorEvent]:
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
    if missing:
        raise SensorImportError(f"missing columns: {missing}")
    events, errors = [], []
    for n, row in enumerate(reader, start=2):
        if n > MAX_ROWS + 1:
            raise SensorImportError(f"more than {MAX_ROWS} rows")
        try:
            source = {"real": SourceType.SENSOR_REAL, "simulated": SourceType.SENSOR_SIMULATED}[row["source"].strip()]
            kind = SensorKind(row["kind"].strip())
            t = datetime.fromisoformat(row["device_time_utc"].strip())
            if t.tzinfo is None:
                raise ValueError("device_time_utc needs a timezone")
            events.append(SensorEvent(
                sensor_event_id=new_id("sensor_event"), site_id=site_id, source_type=source,
                device_id=row["device_id"].strip(),
                kind=kind, value=_value(kind, row["value"]), zone_id=row["zone_id"].strip() or None,
                device_time_utc=t, clock_quality=row["clock_quality"].strip() or "unknown", import_batch=import_batch,
            ))  # fmt: skip
        except (KeyError, ValueError, ValidationError) as e:
            errors.append(f"row {n}: {str(e)[:160]}")
    if errors:
        raise SensorImportError("; ".join(errors[:10]))
    return events
