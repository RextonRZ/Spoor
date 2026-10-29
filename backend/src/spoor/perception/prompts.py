"""SAM 3.1 prompt construction (dev.meta.ai/docs/sam/segmenting).

Concept prompts are one short, concrete, visual noun phrase. Box/point prompts are pixel tokens in the displayed
(post-rotation) frame, built with Meta's `build_object_prompt`.
"""

import re
from dataclasses import dataclass, field

from meta_sam_parser import FramePrompt, PromptBox, PromptObject, PromptPoint, build_object_prompt

from spoor.safety import find_forbidden

MAX_CONCEPT_WORDS = 6
_CONCEPT_RE = re.compile(r"^[a-z0-9][a-z0-9 '\-]*$")
# Not visual objects: SAM segments things, not roles or events (PRD §10.3).
_ABSTRACT = re.compile(r"\b(who|what|where|when|why|took|taking|moved|moving|left|leaving|event|incident)\b")


class PromptError(ValueError):
    pass


def validate_concept(text: str) -> str:
    concept = " ".join(text.lower().split())
    if not concept:
        raise PromptError("empty concept")
    if len(concept.split()) > MAX_CONCEPT_WORDS:
        raise PromptError(f"concept must be at most {MAX_CONCEPT_WORDS} words (one short noun phrase)")
    if not _CONCEPT_RE.match(concept):
        raise PromptError("concept may contain only letters, digits, spaces, hyphens and apostrophes")
    if find_forbidden(concept):
        raise PromptError(f"concept describes a role, identity or attribute, not a visible object: {concept!r}")
    if _ABSTRACT.search(concept) or " and " in f" {concept} ":
        raise PromptError("one concrete visual object per prompt; no questions, events or lists")
    return concept


@dataclass(frozen=True)
class InstancePrompt:
    """Operator-selected instance on a specific frame (box and/or points), for ambiguous or failed concepts."""

    frame_index: int
    box_ltrb_px: tuple[int, int, int, int] | None = None
    positive_points_px: list[tuple[int, int]] = field(default_factory=list)
    negative_points_px: list[tuple[int, int]] = field(default_factory=list)
    object_id: int = 1

    def render(self, frame_wh_px: tuple[int, int]) -> str:
        w, h = frame_wh_px
        points = [PromptPoint(x, y) for x, y in self.positive_points_px]
        points += [PromptPoint(x, y, label="negative") for x, y in self.negative_points_px]
        if self.box_ltrb_px is None and not points:
            raise PromptError("an instance prompt needs a box or at least one point")
        for x, y in [*self.positive_points_px, *self.negative_points_px]:
            if not (0 <= x < w and 0 <= y < h):
                raise PromptError("point outside the frame")
        box = None
        if self.box_ltrb_px is not None:
            left, top, right, bottom = self.box_ltrb_px
            if not (0 <= left < right <= w and 0 <= top < bottom <= h):
                raise PromptError("box outside the frame or degenerate")
            box = PromptBox(left, top, right, bottom)
        frame_prompt = FramePrompt(frame=self.frame_index, box=box, points=points or None)
        return build_object_prompt(size=(w, h), objects=[PromptObject(id=self.object_id, prompts=[frame_prompt])])
