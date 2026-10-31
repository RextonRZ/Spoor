"""Malaysian legal context for reports (QUEUE J3): web-search-grounded answers with inline citations, dated.

This is BACKGROUND for the reader of a report (what the Postal Services Act 2012 and MCMC rules say about lost parcels),
never case evidence. Every kept sentence carries at least one citation; sentences the model wrote without one are
dropped and counted. Sources on a .gov.my domain are marked official. The record is site-level, immutable and hashed,
so a report cites exactly the version it showed."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints

from .base import ImmutableRecord, Sha256, SiteId

LegalContextId = Annotated[str, StringConstraints(pattern=r"^lctx_[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=96)]


class ContextSource(ImmutableRecord):
    n: int = Field(ge=1, description="citation number as shown in the report, [n]")
    url: str
    title: str
    domain: str
    official: bool = Field(description="a .gov.my source (statute portal, regulator)")


class ContextSentence(ImmutableRecord):
    text: str
    sources: Annotated[list[int], Field(min_length=1)]


class ContextAnswer(ImmutableRecord):
    question: str
    sentences: list[ContextSentence]
    dropped_uncited: int = Field(ge=0, description="sentences the model wrote without a citation (not shown)")
    dropped_narration: int = Field(
        default=0, ge=0, description="the model's own tool narration, e.g. 'Now I'll open…'"
    )
    searches: int = Field(ge=0)


class LegalContext(ImmutableRecord):
    legal_context_id: LegalContextId
    site_id: SiteId
    jurisdiction: Literal["MY"] = "MY"
    model: str
    provider: Literal["meta_model_api"] = "meta_model_api"
    response_ids: list[str]
    answers: list[ContextAnswer]
    sources: list[ContextSource]
    searches: int = Field(ge=0)
    usd_estimate: float
    retrieved_at: AwareDatetime
    label: str = (
        "Background from the web, cited and dated. Not case evidence; check the source before relying on it."
    )
    content_sha256: Sha256
