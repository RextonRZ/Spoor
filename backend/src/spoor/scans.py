"""Scan-log import (parcel-hub pivot). JSON Lines, one scan per line; every batch declares real vs simulated.

Ingest derives the links a scan implies, in the same atomic write:
- CONTAINER_ADD    -> open ContainerMembership(child parcel -> container) per identifier
- CONTAINER_REMOVE -> close the open membership(s) of those identifiers in that container
- CONTAINER_LOADED -> open ContainerMembership(container -> parent container, e.g. trailer)
- RELABELED        -> IdentifierAlias(previous label -> new label). Convention: identifiers[0] is the NEW label,
                      the remaining identifiers are the labels it replaces.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from pydantic import ValidationError

from spoor.contracts import (
    ContainerMembership,
    IdentifierAlias,
    LinkStatus,
    ScanEvent,
    ScanEventKind,
    SourceType,
    new_id,
)
from spoor.store import EvidenceStore
from spoor.store.parcels import memberships_of

MAX_LINES = 200_000


class ScanImportError(ValueError):
    pass


def parse_scan_jsonl(text: str, *, site_id: str, import_batch: str, source: Literal["real", "simulated"],
                     now: datetime | None = None) -> list[ScanEvent]:  # fmt: skip
    """Parse a JSONL scan log. The batch-level `source` is mandatory: simulated logs stay labelled end to end."""
    now = now or datetime.now(UTC)
    source_type = {"real": SourceType.SCAN_REAL, "simulated": SourceType.SCAN_SIMULATED}[source]
    scans, errors = [], []
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if n > MAX_LINES:
            raise ScanImportError(f"more than {MAX_LINES} lines")
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise TypeError("each line must be a JSON object")
            for forbidden in ("scan_event_id", "site_id", "source_type", "import_batch"):
                row.pop(forbidden, None)  # assigned by the importer, never trusted from the file
            row.setdefault("record_time_utc", now.isoformat())
            scans.append(ScanEvent(scan_event_id=new_id("scan_event"), site_id=site_id, source_type=source_type,
                                   import_batch=import_batch, **row))  # fmt: skip
        except (json.JSONDecodeError, ValueError, ValidationError, TypeError) as e:
            errors.append(f"line {n}: {str(e)[:200]}")
    if errors:
        raise ScanImportError("; ".join(errors[:10]))
    return scans


@dataclass
class IngestSummary:
    scans: list[str] = field(default_factory=list)
    memberships_opened: list[str] = field(default_factory=list)
    memberships_closed: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    skipped_exact_duplicates: int = 0


def derive_links(store: EvidenceStore, scans: list[ScanEvent], now: datetime) -> tuple[list, IngestSummary]:
    """Records implied by the scans, in time order. Pending links within the batch are tracked so a bag can be
    filled and emptied inside one import."""
    summary = IngestSummary()
    records: list = []
    open_links: dict[tuple[str, str], ContainerMembership] = {}

    def open_for(child: str, parent: str) -> ContainerMembership | None:
        if (child, parent) in open_links:
            return open_links[(child, parent)]
        for m in reversed(memberships_of(store, child)):
            if m.parent_key == parent and m.status == LinkStatus.ACTIVE and m.valid_to is None:
                return m
        return None

    for s in sorted(scans, key=lambda x: x.device_time_utc):
        kind = s.event_kind
        if kind == ScanEventKind.CONTAINER_ADD:
            for child in s.identity_keys:
                m = ContainerMembership(membership_id=new_id("membership"), version=1, child_key=child,
                                        parent_key=s.container.key, valid_from=s.device_time_utc,
                                        opened_by_event_id=s.scan_event_id, basis="scan", status=LinkStatus.ACTIVE,
                                        reason="container_add scan", created_at=now)  # fmt: skip
                open_links[(child, s.container.key)] = m
                records.append(m)
                summary.memberships_opened.append(m.membership_id)
        elif kind == ScanEventKind.CONTAINER_LOADED:
            m = ContainerMembership(membership_id=new_id("membership"), version=1, child_key=s.container.key,
                                    parent_key=s.parent_container.key, valid_from=s.device_time_utc,
                                    opened_by_event_id=s.scan_event_id, basis="scan", status=LinkStatus.ACTIVE,
                                    reason="container_loaded scan", created_at=now)  # fmt: skip
            open_links[(s.container.key, s.parent_container.key)] = m
            records.append(m)
            summary.memberships_opened.append(m.membership_id)
        elif kind == ScanEventKind.CONTAINER_REMOVE:
            for child in s.identity_keys:
                prior = open_for(child, s.container.key)
                if prior is None:
                    continue  # removal without a recorded add: the scan itself remains as evidence
                closed = prior.model_copy(update={"version": prior.version + 1, "valid_to": s.device_time_utc,
                                                  "closed_by_event_id": s.scan_event_id, "status": LinkStatus.CLOSED,
                                                  "reason": "container_remove scan", "created_at": now})
                open_links.pop((child, s.container.key), None)
                records.append(closed)
                summary.memberships_closed.append(closed.membership_id)
        elif kind == ScanEventKind.RELABELED and len(s.identity_keys) >= 2:
            new_key, *old_keys = s.identity_keys
            for old in old_keys:
                a = IdentifierAlias(alias_id=new_id("alias"), from_key=old, to_key=new_key,
                                    linked_by_event_id=s.scan_event_id, basis="relabel_scan", created_at=now)
                records.append(a)
                summary.aliases.append(a.alias_id)
    return records, summary


def ingest_scans(store: EvidenceStore, scans: list[ScanEvent], *, now: datetime | None = None) -> IngestSummary:
    """Store scans and their implied links atomically. Exact re-imports (same identity, kind, device and device time
    already stored) are skipped, so importing a log twice is harmless."""
    now = now or datetime.now(UTC)
    fresh = []
    known = {_fingerprint(s) for s in store.get_many(ScanEvent, store.scan_ids_for_keys(
        {k for s in scans for k in s.identity_keys}))} if scans else set()  # fmt: skip
    known |= {_fingerprint(s) for s in _container_only_known(store, scans)}
    skipped = 0
    for s in scans:
        fp = _fingerprint(s)
        if fp in known:
            skipped += 1
            continue
        known.add(fp)
        fresh.append(s)
    links, summary = derive_links(store, fresh, now)
    store.put_many([*fresh, *links])
    summary.scans = [s.scan_event_id for s in fresh]
    summary.skipped_exact_duplicates = skipped
    return summary


def _fingerprint(s: ScanEvent) -> tuple:
    # A correction repeats the corrected scan's identity, device and time, so it must be part of the fingerprint or
    # the importer would drop every correction as a duplicate.
    return (s.site_id, tuple(sorted(s.identity_keys)), s.container.key if s.container else None, s.event_kind.value,
            s.device_id, s.device_time_utc.isoformat(), s.read_outcome.value, s.corrects_scan_event_id,
            s.correction_reason)  # fmt: skip


def _container_only_known(store: EvidenceStore, scans: list[ScanEvent]) -> list[ScanEvent]:
    keys = {s.container.key for s in scans if s.container and not s.identifiers}
    return [x for k in keys for x in store.find(ScanEvent, container_key=k)]
