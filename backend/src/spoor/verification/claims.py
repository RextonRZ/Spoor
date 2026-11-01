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


class StayedInAreaClaim(_Claim):
    """'The object is inside area A' for an area no camera sees inside (a store room, a blind corner): last confirmed
    at A's edge, a likely carrier went in with it, and it is not seen again on any camera until the recording ends.
    General: any plan area or zone, any camera that watches its doorway."""

    kind: Literal["stayed_in_area"] = "stayed_in_area"
    object_instance_id: str
    area_id: str = Field(description="a site-plan area id or a zone id")
    observation_id: str = Field(description="the object's last confirmed observation, at the area's edge")


class OrderClaim(_Claim):
    kind: Literal["order"] = "order"
    first_observation_id: str
    second_observation_id: str


StructuredClaim = Annotated[
    LastSeenClaim | PresenceClaim | TransitionClaim | ExitClaim | TransferClaim | OrderClaim | ParcelMatchClaim
    | StayedInAreaClaim,
    Field(discriminator="kind"),
]


_KINDS = {c.model_fields["kind"].default: c for c in (LastSeenClaim, PresenceClaim, TransitionClaim, ExitClaim,
                                                      TransferClaim, OrderClaim, ParcelMatchClaim, StayedInAreaClaim)}
_ANY_FIELD = {f for c in _KINDS.values() for f in c.model_fields}


def normalize_claim(data: dict) -> dict:
    """A claim as a model writes it against a strict schema: every field of every claim kind present, the unused ones
    null or empty. Keep the chosen kind's fields; drop empties and fields that belong to OTHER kinds. A field no claim
    kind has is kept, so it is still refused: the rules are not loosened, only the form."""
    kind = data.get("kind")
    if kind not in _KINDS:
        return data
    allowed = set(_KINDS[kind].model_fields)
    out = {k: v for k, v in data.items() if v not in (None, [], "") and (k in allowed or k not in _ANY_FIELD)}
    ids = data.get("observation_ids") or []
    if "observation_id" in allowed and "observation_id" not in out and len(ids) == 1:
        out["observation_id"] = ids[0]  # one cited observation, sent as a one-item list
    out.setdefault("statement", f"{kind.replace('_', ' ')} claim")
    return out

