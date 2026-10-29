"""Muse Spark video reasoning and structured LLM backends (PRD §10.2, §15)."""

from .backends import (
    BackendError,
    BackendReply,
    BasetenChatBackend,
    JsonBackend,
    MetaResponsesBackend,
    strict_schema,
)
from .clips import ClipWindow, cut_clip, uploaded
from .grounding import GroundedFact, ground_facts
from .spark import TEMPLATES, CandidateFact, ClipAnalysis, ClipAnswer, ask_clip

__all__ = [
    "TEMPLATES",
    "BackendError",
    "BackendReply",
    "BasetenChatBackend",
    "CandidateFact",
    "ClipAnalysis",
    "ClipAnswer",
    "ClipWindow",
    "GroundedFact",
    "JsonBackend",
    "MetaResponsesBackend",
    "ask_clip",
    "cut_clip",
    "ground_facts",
    "strict_schema",
    "uploaded",
]
