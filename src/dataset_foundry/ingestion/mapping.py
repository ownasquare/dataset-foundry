"""Normalize supported tabular and JSON seed shapes into the canonical contract."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from dataset_foundry.domain import ChatMessage, MessageRole, TrainingExample


class SeedMappingError(ValueError):
    """Raised when a source row cannot be mapped without guessing required content."""


_KNOWN_FIELDS = {
    "id",
    "source_id",
    "messages",
    "instruction",
    "input",
    "output",
    "prompt",
    "completion",
    "metadata",
    "system",
}


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SeedMappingError(f"{key} must be a non-blank string")
    return value.strip()


def _optional_text(row: Mapping[str, Any], key: str) -> str | None:
    value = row.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise SeedMappingError(f"{key} must be a string when provided")
    stripped = value.strip()
    return stripped or None


def _parse_json_cell(value: str, *, field_name: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise SeedMappingError(f"{field_name} contains invalid JSON") from error


def _metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    raw_metadata = row.get("metadata", {})
    if isinstance(raw_metadata, str):
        raw_metadata = (
            {}
            if not raw_metadata.strip()
            else _parse_json_cell(raw_metadata, field_name="metadata")
        )
    if not isinstance(raw_metadata, Mapping):
        raise SeedMappingError("metadata must be an object")
    metadata = {str(key): value for key, value in raw_metadata.items()}
    for key, value in row.items():
        if key not in _KNOWN_FIELDS and value not in (None, ""):
            metadata[str(key)] = value
    return metadata


def _messages_from_explicit(row: Mapping[str, Any]) -> list[ChatMessage]:
    raw_messages = row.get("messages")
    if isinstance(raw_messages, str):
        raw_messages = _parse_json_cell(raw_messages, field_name="messages")
    if not isinstance(raw_messages, list):
        raise SeedMappingError("messages must be a JSON array")
    try:
        return [ChatMessage.model_validate(message) for message in raw_messages]
    except ValidationError as error:
        raise SeedMappingError("messages do not match the canonical chat schema") from error


def _instruction_messages(row: Mapping[str, Any]) -> list[ChatMessage]:
    instruction = _required_text(row, "instruction")
    context = _optional_text(row, "input")
    user_content = instruction if context is None else f"{instruction}\n\nContext:\n{context}"
    messages: list[ChatMessage] = []
    system = _optional_text(row, "system")
    if system is not None:
        messages.append(ChatMessage(role=MessageRole.system, content=system))
    messages.extend(
        [
            ChatMessage(role=MessageRole.user, content=user_content),
            ChatMessage(role=MessageRole.assistant, content=_required_text(row, "output")),
        ]
    )
    return messages


def _completion_messages(row: Mapping[str, Any]) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    system = _optional_text(row, "system")
    if system is not None:
        messages.append(ChatMessage(role=MessageRole.system, content=system))
    messages.extend(
        [
            ChatMessage(role=MessageRole.user, content=_required_text(row, "prompt")),
            ChatMessage(role=MessageRole.assistant, content=_required_text(row, "completion")),
        ]
    )
    return messages


def map_seed_row(row: Mapping[str, Any], *, position: int = 0) -> TrainingExample:
    """Map one supported row, rejecting ambiguous or incomplete shapes."""

    if "messages" in row and row.get("messages") not in (None, ""):
        messages = _messages_from_explicit(row)
    elif "instruction" in row or "output" in row:
        messages = _instruction_messages(row)
    elif "prompt" in row or "completion" in row:
        messages = _completion_messages(row)
    else:
        raise SeedMappingError(
            "row must contain messages, instruction/output, or prompt/completion fields"
        )

    raw_source_id = row.get("source_id", row.get("id"))
    source_id = str(raw_source_id).strip() if raw_source_id not in (None, "") else str(position)
    try:
        return TrainingExample(
            id=source_id,
            source_id=source_id,
            root_seed_id=source_id,
            messages=messages,
            metadata=_metadata(row),
        )
    except ValidationError as error:
        raise SeedMappingError("row violates the canonical training-example contract") from error
