"""Parcel identity and scan evidence (parcel-hub pivot; see reports/Parcel hub tracking and investigations.md).

A barcode scan is the opposite of a sensor event: strongest *identity* evidence, weakest *location* evidence (a
handheld read proves the ID was read near the device, not where the parcel went next). Scans therefore get their own
record. Field names follow the research synthesis of UPU EMSEVT, GS1 EPCIS 2.0.1 and carrier tracking APIs.
"""

import re
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .base import (
    ImmutableRecord,
    MediaId,
    SiteId,
    ZoneId,
    _id_type,
)
from .enums import SourceType

ScanEventId = _id_type("scan")
MembershipId = _id_type("cmem")
AliasId = _id_type("alias")
ClockDomainId = _id_type("clkd")


class IdentifierScheme(StrEnum):
    S10 = "s10"  # UPU S10 postal item ID, e.g. EE123456785MY
    SSCC = "sscc"  # GS1 Serial Shipping Container Code, 18 digits
    CARRIER_WAYBILL = "carrier_waybill"
    INTERNAL = "internal"
    DL_URI = "dl_uri"  # GS1 Digital Link URI
    CONTAINER = "container"  # bag / cage / pallet / trailer label (UPU S9 receptacle IDs are 29 chars)


_S10 = re.compile(r"^[A-Z]{2}\d{8}\d[A-Z]{2}$")
_S10_WEIGHTS = (8, 6, 4, 2, 3, 5, 9, 7)


def s10_check_digit(serial8: str) -> int:
    """UPU S10: weights 8 6 4 2 3 5 9 7, mod 11; 10 -> 0, 11 -> 5."""
    c = 11 - sum(int(d) * w for d, w in zip(serial8, _S10_WEIGHTS, strict=True)) % 11
    return {10: 0, 11: 5}.get(c, c)


def gs1_check_digit(body: str) -> int:
    """GS1 mod-10: weights 3,1,3,... from the rightmost data digit."""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10


class ParcelIdentifier(ImmutableRecord):
    """One identifier on a parcel or container. A parcel can carry several at once (waybill + SSCC + S10)."""

    scheme: IdentifierScheme
    value: str = Field(min_length=1, max_length=256)
    # Computed for schemes with check digits; a failed check (e.g. an OCR misread) is kept as evidence but never
    # used to bind identity.
    check_digit_valid: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _check(cls, data):
        if not isinstance(data, dict):
            return data
        scheme, value = data.get("scheme"), str(data.get("value", "")).strip()
        data = {**data, "value": value}
        if scheme == IdentifierScheme.S10 or scheme == "s10":
            value = value.upper()
            data["value"] = value
            data["check_digit_valid"] = bool(_S10.match(value)) and s10_check_digit(value[2:10]) == int(value[10])
        elif scheme == IdentifierScheme.SSCC or scheme == "sscc":
            data["check_digit_valid"] = len(value) == 18 and value.isdigit() and \
                gs1_check_digit(value[:17]) == int(value[17])  # fmt: skip
        return data

    @property
    def key(self) -> str:
        """Canonical key used for lookups, aliases and container membership: '<scheme>:<value>'."""
        return f"{self.scheme.value}:{self.value}"

    @property
    def usable_for_identity(self) -> bool:
        return self.check_digit_valid is not False


class ReadOutcome(StrEnum):
    READ = "read"
    NO_READ = "no_read"  # nothing decoded (damaged/wrinkled label, poly-mailer glare, orientation)
    NO_SOLVE = "no_solve"  # decoded but could not be resolved to a parcel record
    MULTI_READ = "multi_read"  # several conflicting IDs in one read


class ScanEventKind(StrEnum):
    # opens a facility visit
    ARRIVED_FACILITY = "arrived_facility"
    INDUCTED = "inducted"
    TUNNEL_READ = "tunnel_read"
    RETURN_INDUCTED = "return_inducted"
    # in-hub progress
    TUNNEL_NO_READ = "tunnel_no_read"
    SORT_ASSIGNED = "sort_assigned"
    DIVERT_CONFIRMED = "divert_confirmed"
    RECIRCULATED = "recirculated"
    EXCEPTION_DIVERTED = "exception_diverted"
    MANUAL_ENCODED = "manual_encoded"
    RELABELED = "relabeled"
    DAMAGE_HOLD = "damage_hold"
    MISSORT_DETECTED = "missort_detected"
    # containers
    CONTAINER_ADD = "container_add"
    CONTAINER_CLOSED = "container_closed"
    CONTAINER_REMOVE = "container_remove"
    CONTAINER_LOADED = "container_loaded"
    # closes a facility visit
    DEPARTED_FACILITY = "departed_facility"
    # investigation lifecycle (cf. USPS VM/VO)
    CASE_OPENED = "case_opened"
    CASE_CLOSED = "case_closed"


VISIT_OPENING = frozenset({ScanEventKind.ARRIVED_FACILITY, ScanEventKind.INDUCTED, ScanEventKind.TUNNEL_READ,
                           ScanEventKind.RETURN_INDUCTED})  # fmt: skip
VISIT_CLOSING = frozenset({ScanEventKind.DEPARTED_FACILITY, ScanEventKind.CONTAINER_LOADED})
CONTAINER_KINDS = frozenset({ScanEventKind.CONTAINER_ADD, ScanEventKind.CONTAINER_CLOSED,
                             ScanEventKind.CONTAINER_REMOVE, ScanEventKind.CONTAINER_LOADED})  # fmt: skip


class DeviceKind(StrEnum):
    TUNNEL = "tunnel"  # fixed multi-side scan tunnel / DWS on the sorter
    DWS_STATIC = "dws_static"
    SORTER_PLC = "sorter_plc"  # sorter control (divert confirmations)
    SHIP_SORTER = "ship_sorter"
    HANDHELD = "handheld"
    RFID_PORTAL = "rfid_portal"


FIXED_DEVICES = frozenset({DeviceKind.TUNNEL, DeviceKind.DWS_STATIC, DeviceKind.SORTER_PLC, DeviceKind.SHIP_SORTER,
                           DeviceKind.RFID_PORTAL})  # fmt: skip


class ContainerType(StrEnum):
    BAG = "bag"
    CAGE = "cage"
    PALLET = "pallet"
    GAYLORD = "gaylord"
    TRAILER = "trailer"


SCAN_SOURCES = frozenset({SourceType.SCAN_REAL, SourceType.SCAN_SIMULATED})
_OPERATOR_REF = re.compile(r"^op_[A-Za-z0-9]{4,64}$")


class ScanEvent(ImmutableRecord):
    """One barcode/RFID read or machine event about a parcel or container. Append-only; corrections are new events
    that point at the event they correct (EPCIS errorDeclaration), never edits."""

    scan_event_id: ScanEventId
    site_id: SiteId
    source_type: SourceType
    import_batch: str
    # identity
    identifiers: list[ParcelIdentifier] = []
    read_outcome: ReadOutcome = ReadOutcome.READ
    # event
    event_kind: ScanEventKind
    raw_code: str | None = None
    raw_description: str | None = Field(default=None, max_length=500, description="Stored as data, never prompts")
    reason_code: str | None = None
    action_code: str | None = None
    epcis_action: Literal["ADD", "OBSERVE", "DELETE"] | None = None
    biz_step: str | None = None
    disposition: str | None = None
    # time (EPCIS eventTime vs recordTime)
    device_time_utc: AwareDatetime
    record_time_utc: AwareDatetime | None = None
    clock_domain_id: ClockDomainId | None = None
    # where (EPCIS readPoint vs bizLocation)
    device_id: str = Field(min_length=1)
    device_kind: DeviceKind
    station_id: str | None = None
    read_point_zone_id: ZoneId | None = Field(default=None, description="Zone of the read point (camera FOV lookup)")
    biz_location_id: str | None = None
    # routing
    sort_destination_assigned: str | None = None
    sort_destination_actual: str | None = None
    divert_confirmed: bool | None = None
    # containers
    container: ParcelIdentifier | None = None
    container_type: ContainerType | None = None
    parent_container: ParcelIdentifier | None = None
    # physical
    weight_g: float | None = Field(default=None, ge=0)
    dims_mm: tuple[float, float, float] | None = None
    image_refs: list[MediaId] = []
    # custody: pseudonymous token from the scan-gun login, never a name (PDPA; PRD §7.2)
    operator_ref: str | None = None
    # correction
    corrects_scan_event_id: ScanEventId | None = None
    correction_reason: Literal["did_not_occur", "incorrect_data"] | None = None

    @field_validator("source_type")
    @classmethod
    def _scan_source(cls, v: SourceType) -> SourceType:
        if v not in SCAN_SOURCES:
            raise ValueError("scan events must be scan_real or scan_simulated")
        return v

    @field_validator("operator_ref")
    @classmethod
    def _pseudonymous(cls, v: str | None) -> str | None:
        if v is not None and not _OPERATOR_REF.match(v):
            raise ValueError("operator_ref must be a pseudonymous token like 'op_7f3a91', never a name")
        return v

    @model_validator(mode="after")
    def _consistent(self) -> "ScanEvent":
        # Container-level events (a bag loaded, a trailer departing) identify the container, not the parcels.
        if self.read_outcome in (ReadOutcome.READ, ReadOutcome.MULTI_READ) and not self.identifiers \
                and self.event_kind not in CONTAINER_KINDS and self.container is None:  # fmt: skip
            raise ValueError("a read must carry at least one identifier (or a container for container-level events)")
        if self.read_outcome in (ReadOutcome.NO_READ, ReadOutcome.NO_SOLVE) and self.identifiers:
            raise ValueError("a no-read carries no identifier; identity may later be bound by video")
        if self.event_kind in CONTAINER_KINDS:
            if self.container is None or self.container.scheme != IdentifierScheme.CONTAINER:
                raise ValueError(f"{self.event_kind} needs a container identifier")
            if self.event_kind == ScanEventKind.CONTAINER_LOADED and self.parent_container is None:
                raise ValueError("container_loaded needs the parent container (e.g. the trailer)")
        if (self.corrects_scan_event_id is None) != (self.correction_reason is None):
            raise ValueError("a correction needs both corrects_scan_event_id and correction_reason")
        if self.dims_mm is not None and any(d <= 0 for d in self.dims_mm):
            raise ValueError("dimensions must be positive")
        return self

    @property
    def identity_keys(self) -> list[str]:
        return [i.key for i in self.identifiers if i.usable_for_identity]

    @property
    def is_fixed_read(self) -> bool:
        return self.device_kind in FIXED_DEVICES and self.read_outcome == ReadOutcome.READ


class LinkStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"  # membership ended normally (e.g. unbagged)
    CONTRADICTED = "contradicted"  # evidence shows the link never held (e.g. video: parcel left beside the bag)
    RETRACTED = "retracted"


class ContainerMembership(ImmutableRecord):
    """'child was inside parent from valid_from to valid_to'. Versioned: a change is a new version, history kept.
    Location inherited through membership is a presumption 'until contradicted' (EPCIS AggregationEvent), shown as
    estimated, never observed."""

    membership_id: MembershipId
    version: int = Field(ge=1)
    child_key: str = Field(description="'<scheme>:<value>' of the parcel or container inside")
    parent_key: str = Field(description="'container:<value>' of the enclosing container")
    valid_from: AwareDatetime
    valid_to: AwareDatetime | None = None
    opened_by_event_id: ScanEventId | None = None
    closed_by_event_id: ScanEventId | None = None
    basis: Literal["scan", "video_observed", "inferred"]
    status: LinkStatus
    reason: str = ""
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _ordered(self) -> "ContainerMembership":
        if not self.parent_key.startswith("container:"):
            raise ValueError("parent must be a container key")
        if self.child_key == self.parent_key:
            raise ValueError("a container cannot contain itself")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("membership ends before it starts")
        return self


class IdentifierAlias(ImmutableRecord):
    """Two identifiers denote the same physical parcel (relabel, manual encode). Without this a relabelled parcel
    appears to vanish while a new one appears from nowhere: exactly the false 'lost parcel' Spoor must not produce."""

    alias_id: AliasId
    from_key: str
    to_key: str
    linked_by_event_id: ScanEventId | None = None
    basis: Literal["relabel_scan", "manual_encode", "human_confirmed", "video_candidate"]
    status: Literal["active", "retracted"] = "active"
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _distinct(self) -> "IdentifierAlias":
        if self.from_key == self.to_key:
            raise ValueError("an alias links two different identifiers")
        return self


class ClockDomain(ImmutableRecord):
    """A set of devices that share one clock: the sorter WCS/PLC, the handheld fleet, an NVR, a single camera."""

    clock_domain_id: ClockDomainId
    site_id: SiteId
    kind: Literal["wcs_plc", "handheld_fleet", "nvr", "camera", "rfid", "other"]
    name: str
    device_ids: list[str] = []
    camera_ids: list[str] = []
