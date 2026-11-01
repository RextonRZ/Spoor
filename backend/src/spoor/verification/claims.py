"""Structured claims (PRD §17.4). Agents express factual assertions in these shapes, never as free prose; the
`statement` is a human-readable summary that is itself screened for overreach."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=3)


class LastSeenClaim(_Claim):
    kind: Literal["last_seen"] = "last_seen"
    object_instance_id: str
    observation_id: str


class PresenceClaim(_Claim):
    kind: Literal["presence"] = "presence"
    object_instance_id: str
    observation_ids: list[str] = Field(min_length=1)
    zone_id: str | None = None


class TransitionClaim(_Claim):
    kind: Literal["transition"] = "transition"
    object_instance_id: str
    from_observation_id: str
    to_observation_id: str
    asserted_label: Literal["observed", "hypothesized"]


class ExitClaim(_Claim):
    """'The object left through door D.' Needs video beyond the door; sensors can only corroborate."""

    kind: Literal["exit"] = "exit"
    object_instance_id: str
    door_zone_id: str
    observation_ids: list[str] = Field(min_length=1)
    sensor_event_ids: list[str] = []


class TransferClaim(_Claim):
    """Object moved from one place to another by contact. Without visible contact + before/after, stays a hypothesis."""

    kind: Literal["transfer"] = "transfer"
    object_instance_id: str
    observation_ids: list[str] = Field(min_length=2)


class ParcelMatchClaim(_Claim):
    """'This sighting is parcel X' (a look-alike check). The parcel's own scans can rule a sighting out: if they place it
    on the belt, or at a station, at that moment, and the sighting is elsewhere. They can never prove it."""

    kind: Literal["parcel_match"] = "parcel_match"
    observation_ids: list[str] = Field(min_length=1)
    waybill: str = Field(min_length=3)


class OrderClaim(_Claim):
    kind: Literal["order"] = "order"
    first_observation_id: str
    second_observation_id: str


StructuredClaim = Annotated[
    LastSeenClaim | PresenceClaim | TransitionClaim | ExitClaim | TransferClaim | OrderClaim | ParcelMatchClaim,
    Field(discriminator="kind"),
]
