"""Floor search (QUEUE I7 / H12): a task listing the places to look, and what a person found there.

An outcome is a HUMAN observation: who (pseudonymous user id, never a name), when, which place, found or not, an optional
note and photo hash; its content is hashed so it can be cited. "Not here" is negative evidence a person supplied; "found"
is a confirmed sighting by a person. Both revise the case on the next read (possible area, status, journey)."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints

from .base import CaseId, ImmutableRecord, Sha256

SearchTaskId = Annotated[str, StringConstraints(pattern=r"^srch_[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=96)]
SearchOutcomeId = Annotated[str, StringConstraints(pattern=r"^sout_[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=96)]


class SearchPlace(ImmutableRecord):
    area_id: str
    name: str
    zone_id: str | None = None
    centroid_xy: tuple[float, float]
    why: list[str] = []


class SearchTask(ImmutableRecord):
    search_task_id: SearchTaskId
    case_id: CaseId
    places: Annotated[list[SearchPlace], Field(min_length=1, max_length=12)]
    plan_id: str | None = None
    created_by: str
    created_at: AwareDatetime


class SearchOutcome(ImmutableRecord):
    search_outcome_id: SearchOutcomeId
    search_task_id: SearchTaskId
    case_id: CaseId
    area_id: str
    outcome: Literal["found", "not_found"]
    note: str | None = Field(default=None, max_length=500)
    photo_sha256: Sha256 | None = None
    recorded_by: str = Field(description="pseudonymous user id of the person who searched")
    recorded_at: AwareDatetime
    content_sha256: Sha256
