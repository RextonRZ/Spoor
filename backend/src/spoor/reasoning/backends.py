"""Structured-output LLM backends behind one interface.

- MetaResponsesBackend: Muse Spark via Meta Model API `/v1/responses` with `text.format` json_schema (strict subset,
  dev.meta.ai/docs/structured-output). Accepts video content parts.
- BasetenChatBackend: Muse Spark Open via Baseten's OpenAI-compatible chat API (text only). The schema is given in the
  prompt and the reply is validated locally; one bounded repair attempt on invalid JSON.

Model output is always validated against a Pydantic model before anything uses it.
"""

import copy
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class BackendError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackendReply:
    data: BaseModel
    raw: str
    model: str
    provider: str
    response_id: str | None
    input_tokens: int
    output_tokens: int
    latency_s: float
    reasoning_chars: int = 0  # length of the model's separate reasoning (never validated, never shown as evidence)


class JsonBackend(Protocol):
    provider: str
    model: str
    supports_video: bool

    def complete(self, *, system: str, content: list[dict] | str, output: type[T], name: str) -> BackendReply: ...


def strict_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON Schema -> Meta strict subset: root object, additionalProperties false, every key required,
    no oneOf/allOf, no defaults. Optional fields stay nullable via anyOf."""
    schema = copy.deepcopy(model.model_json_schema())

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            node.pop("title", None)
            if "allOf" in node and len(node["allOf"]) == 1:
                node.update(node.pop("allOf")[0])
            if "oneOf" in node:
                node["anyOf"] = node.pop("oneOf")
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema


def _usage(resp: Any, a: str, b: str) -> tuple[int, int]:
    u = getattr(resp, "usage", None)
    return (getattr(u, a, 0) or 0, getattr(u, b, 0) or 0) if u else (0, 0)


class MetaResponsesBackend:
    provider = "meta_model_api"
    supports_video = True
    supports_images = True  # Muse Spark reads images (input_image) as well as video

    def __init__(self, client: Any, model: str = "muse-spark-1.3"):
        if model.endswith("-contributor"):
            raise ValueError("contributor-mode models are not used for authorized footage (PRD §7.1)")
        self.client, self.model = client, model

    def complete(self, *, system: str, content: list[dict] | str, output: type[T], name: str) -> BackendReply:
        start = time.perf_counter()
        user = content if isinstance(content, list) else [{"type": "input_text", "text": content}]
        resp = self.client.responses.create(
            model=self.model,
            instructions=system,
            input=[{"role": "user", "content": user}],
            text={"format": {"type": "json_schema", "name": name, "schema": strict_schema(output), "strict": True}},
        )
        raw = resp.output_text
        try:
            data = output.model_validate_json(raw)
        except ValidationError as e:
            raise BackendError(f"schema-invalid output from {self.model}: {e.error_count()} errors") from e
        tin, tout = _usage(resp, "input_tokens", "output_tokens")
        return BackendReply(data, raw, getattr(resp, "model", self.model), self.provider, getattr(resp, "id", None),
                            tin, tout, round(time.perf_counter() - start, 3))  # fmt: skip


def split_reasoning(message: Any) -> tuple[str, str]:
    """(answer, reasoning). Muse Spark Open always reasons (J2a): the reasoning arrives as `reasoning_content` /
    `reasoning`, or inline as a <think>...</think> block. Only the answer goes to the JSON validator."""
    text = getattr(message, "content", None) or ""
    reasoning = getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None) or ""
    if "</think>" in text:
        head, text = text.split("</think>", 1)
        reasoning = reasoning or head.replace("<think>", "")
    return text.strip(), reasoning if isinstance(reasoning, str) else ""


def _chat_parts(content: list[dict]) -> list[dict]:
    """Meta-style parts -> OpenAI chat parts. Text and images (key frames) only (J2b); video stays with Meta Spark."""
    out = []
    for part in content:
        kind = part.get("type")
        if kind == "input_text":
            out.append({"type": "text", "text": part["text"]})
        elif kind == "input_image":
            out.append({"type": "image_url", "image_url": {"url": part["image_url"]}})
        else:
            raise BackendError("Baseten backend takes text and images only; route video questions to Muse Spark on Meta")
    return out


class BasetenChatBackend:
    provider = "baseten"
    supports_video = False
    supports_images = True

    def __init__(self, client: Any, model: str, max_repairs: int = 1):
        self.client, self.model, self.max_repairs = client, model, max_repairs

    def complete(self, *, system: str, content: list[dict] | str, output: type[T], name: str) -> BackendReply:
        if isinstance(content, list):
            parts = _chat_parts(content)
            content = parts if any(x["type"] == "image_url" for x in parts) else "\n\n".join(x["text"] for x in parts)
        schema = json.dumps(strict_schema(output))
        messages = [
            {"role": "system", "content": f"{system}\n\nReply with ONE JSON object matching this JSON Schema "
                                          f"({name}), and nothing else:\n{schema}"},
            {"role": "user", "content": content},
        ]  # fmt: skip
        start, tin, tout = time.perf_counter(), 0, 0
        for attempt in range(self.max_repairs + 1):
            resp = self.client.chat.completions.create(model=self.model, messages=messages,
                                                       response_format={"type": "json_object"})  # fmt: skip
            a, b = _usage(resp, "prompt_tokens", "completion_tokens")
            tin, tout = tin + a, tout + b
            raw, reasoning = split_reasoning(resp.choices[0].message)
            try:
                data = output.model_validate_json(raw)
                return BackendReply(data, raw, getattr(resp, "model", self.model), self.provider,
                                    getattr(resp, "id", None), tin, tout, round(time.perf_counter() - start, 3),
                                    len(reasoning))  # fmt: skip
            except ValidationError as e:
                if attempt == self.max_repairs:
                    raise BackendError(f"schema-invalid output from {self.model} after {attempt + 1} tries") from e
                messages += [{"role": "assistant", "content": raw},
                             {"role": "user", "content": f"That JSON did not match the schema: {e.errors()[:3]}. "
                                                         "Reply again with only the corrected JSON object."}]
        raise AssertionError("unreachable")
