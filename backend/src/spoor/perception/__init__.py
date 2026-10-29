"""Perception: SAM 3.1 object segmentation and per-clip tracking (PRD §10.3, §14)."""

from .backend import MetaSamBackend, SamBackend, SamDetection, SamRun, parse_sam_stream
from .prompts import InstancePrompt, PromptError, validate_concept
from .service import PerceptionRequest, PerceptionResult, track_target

__all__ = [
    "InstancePrompt",
    "MetaSamBackend",
    "PerceptionRequest",
    "PerceptionResult",
    "PromptError",
    "SamBackend",
    "SamDetection",
    "SamRun",
    "parse_sam_stream",
    "track_target",
    "validate_concept",
]
