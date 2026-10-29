"""Database schema. Every record is stored as validated JSON plus indexed columns for structured queries (PRD §16.2).

Append-only tables get database triggers that abort any UPDATE, so immutability holds even against buggy code.
SQLite is used for local development; the same schema targets PostgreSQL (triggers provided for both dialects).
"""

from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    event,
)

metadata = MetaData()

_PG_FUNCTION = DDL(
    "CREATE OR REPLACE FUNCTION spoor_append_only() RETURNS trigger AS $$ "
    "BEGIN RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME; END $$ LANGUAGE plpgsql"
)


def _table(name: str, *cols: Column, immutable: bool = True) -> Table:
    t = Table(
        name, metadata,
        Column("id", String(96), primary_key=True),
        *cols,
        Column("seq", BigInteger, nullable=False, index=True),
        Column("payload", Text, nullable=False),
    )  # fmt: skip
    t.info["immutable"] = immutable
    if immutable:
        event.listen(t, "after_create", DDL(
            f"CREATE TRIGGER {name}_append_only BEFORE UPDATE ON {name} "
            f"BEGIN SELECT RAISE(ABORT, '{name} is append-only'); END"
        ).execute_if(dialect="sqlite"))  # fmt: skip
        event.listen(t, "after_create", _PG_FUNCTION.execute_if(dialect="postgresql"))
        event.listen(t, "after_create", DDL(
            f"CREATE TRIGGER {name}_append_only BEFORE UPDATE ON {name} "
            "FOR EACH ROW EXECUTE FUNCTION spoor_append_only()"
        ).execute_if(dialect="postgresql"))  # fmt: skip
    return t


def _idx(name: str, type_=None) -> Column:
    return Column(name, type_ if type_ is not None else String(96), index=True)


# --- site & calibration -------------------------------------------------------
sites = _table("sites", immutable=False)
cameras = _table("cameras", _idx("site_id"), immutable=False)
calibrations = _table("calibrations", _idx("camera_id"))
clock_syncs = _table("clock_syncs", _idx("camera_id"), _idx("clock_domain_id"))
clock_domains = _table("clock_domains", _idx("site_id"))

# --- media ----------------------------------------------------------------------
authorizations = _table("authorizations", _idx("site_id"))
media = _table("media", _idx("site_id"), _idx("camera_id"), _idx("kind", String(32)), _idx("parent_id"),
               _idx("sha256", String(64)))  # fmt: skip
coverage = _table("coverage", _idx("camera_id"), _idx("media_id"), _idx("start_ms", BigInteger),
                  _idx("end_ms", BigInteger))  # fmt: skip

# --- observations ----------------------------------------------------------------
tracks = _table("tracks", _idx("camera_id"), _idx("media_id"))
observations = _table(
    "observations",
    _idx("camera_id"), _idx("media_id"), _idx("track_id"), _idx("label", String(120)),
    _idx("source_type", String(32)), Column("frame_index", Integer), Column("pts_ms", Float),
    _idx("t_norm_ms", BigInteger), Column("t_unc_ms", Float), Column("observed", Boolean),
)  # fmt: skip
estimates = _table("estimates", _idx("spatial_mode", String(32)), _idx("zone_id"), _idx("calibration_id"))
estimates_xyz = _table("estimates_xyz", _idx("correspondence_id"))
sensor_events = _table("sensor_events", _idx("site_id"), _idx("kind", String(32)), _idx("zone_id"), _idx("t_ms", BigInteger),
                       _idx("source_type", String(32)))  # fmt: skip
object_instances = _table("object_instances", _idx("case_id"))
associations = _table("associations", _idx("object_instance_id"), _idx("track_id"), _idx("status", String(32)),
                      Column("version", Integer))  # fmt: skip

# --- case -------------------------------------------------------------------------
cases = _table("cases", _idx("site_id"), immutable=False)
case_revisions = _table("case_revisions", _idx("case_id"), _idx("parent_id"))
events = _table("events", _idx("case_id"), _idx("object_instance_id"), _idx("start_ms", BigInteger),
                _idx("end_ms", BigInteger), _idx("label", String(32)))  # fmt: skip
hypotheses = _table("hypotheses", _idx("case_id"))
status_changes = _table("status_changes", _idx("hypothesis_id"))
findings = _table("findings", _idx("case_id"))
evidence_requests = _table("evidence_requests", _idx("case_id"))
reports = _table("reports", _idx("case_id"))

# --- operations ------------------------------------------------------------------
invalidations = _table("invalidations", _idx("target_id"))
audit = _table("audit", _idx("target_id"), _idx("action", String(64)))
cost_ledger = _table("cost_ledger", _idx("case_id"), _idx("provider", String(32)))
agent_steps = _table("agent_steps", _idx("case_id"), _idx("request_id"), _idx("idempotency_key", String(128)))

# --- parcels & scans (parcel-hub pivot) -------------------------------------------
scan_events = _table("scan_events", _idx("site_id"), _idx("event_kind", String(32)), _idx("device_id"),
                     _idx("clock_domain_id"), _idx("container_key", String(300)), _idx("t_device_ms", BigInteger),
                     _idx("corrects_id"))  # fmt: skip
memberships = _table("memberships", _idx("membership_id"), _idx("child_key", String(300)),
                     _idx("parent_key", String(300)), Column("version", Integer))  # fmt: skip
aliases = _table("aliases", _idx("from_key", String(300)), _idx("to_key", String(300)))
# Identifier -> scan index: one row per identifier on a scan (a scan can carry several IDs).
scan_identifiers = Table(
    "scan_identifiers", metadata,
    Column("scan_event_id", String(96), primary_key=True),
    Column("key", String(300), primary_key=True, index=True),
)  # fmt: skip
event.listen(scan_identifiers, "after_create", DDL(
    "CREATE TRIGGER scan_identifiers_append_only BEFORE UPDATE ON scan_identifiers "
    "BEGIN SELECT RAISE(ABORT, 'scan_identifiers is append-only'); END"
).execute_if(dialect="sqlite"))  # fmt: skip

# Dependency edges: `src` was derived from / cites `dst`. Drives invalidation propagation and deletion (§16.4).
refs = Table(
    "refs", metadata,
    Column("src_id", String(96), primary_key=True),
    Column("dst_id", String(96), primary_key=True, index=True),
    Column("rel", String(32), primary_key=True),
)  # fmt: skip
event.listen(refs, "after_create", DDL(
    "CREATE TRIGGER refs_append_only BEFORE UPDATE ON refs BEGIN SELECT RAISE(ABORT, 'refs is append-only'); END"
).execute_if(dialect="sqlite"))  # fmt: skip
