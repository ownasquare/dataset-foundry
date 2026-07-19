"""Explainable deterministic quality components and aggregate weighting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, Protocol

from dataset_foundry.domain import GeneratedCandidate, MessageRole, QualityComponent
from dataset_foundry.quality.embeddings import normalize_text

_WORD_PATTERN = re.compile(r"\b\w+\b", flags=re.UNICODE)
_BOILERPLATE = (
    "as an ai language model",
    "generated response",
    "insert answer here",
    "lorem ipsum",
)


@dataclass(frozen=True, slots=True)
class ScoreResult:
    score: float
    components: tuple[QualityComponent, ...]


class CandidateScorer(Protocol):
    """Replaceable scoring contract used by :class:`QualityPipeline`."""

    def score(
        self,
        candidate: GeneratedCandidate,
        *,
        seed_similarity: float,
        accepted_similarity: float,
        constraints: list[str] | None = None,
    ) -> ScoreResult:
        """Return one bounded aggregate score plus explainable components."""


def candidate_instruction(candidate: GeneratedCandidate) -> str:
    return next(
        message.content for message in candidate.messages if message.role is MessageRole.user
    )


def candidate_response(candidate: GeneratedCandidate) -> str:
    return next(
        message.content for message in candidate.messages if message.role is MessageRole.assistant
    )


def candidate_text(candidate: GeneratedCandidate) -> str:
    return "\n".join(message.content for message in candidate.messages)


def _component(
    name: str,
    score: float,
    explanation: str,
    *,
    pass_at: float = 0.5,
    reason_code: str | None = None,
) -> QualityComponent:
    bounded = max(0.0, min(1.0, score))
    passed = bounded >= pass_at
    return QualityComponent(
        name=name,
        score=bounded,
        passed=passed,
        reason_code=None if passed else reason_code,
        explanation=explanation,
    )


def _length_score(instruction: str, response: str) -> float:
    instruction_length = len(instruction)
    response_length = len(response)
    instruction_score = min(1.0, instruction_length / 24) if instruction_length < 24 else 1.0
    response_score = min(1.0, response_length / 80) if response_length < 80 else 1.0
    if instruction_length > 4_000:
        instruction_score *= 4_000 / instruction_length
    if response_length > 12_000:
        response_score *= 12_000 / response_length
    return (instruction_score + response_score) / 2


def _lexical_richness(text: str) -> float:
    tokens = _WORD_PATTERN.findall(normalize_text(text))
    if not tokens:
        return 0.0
    unique_ratio = len(set(tokens)) / len(tokens)
    volume = min(1.0, len(tokens) / 24)
    return min(1.0, unique_ratio * 1.25) * volume


def _instruction_response_overlap(instruction: str, response: str) -> float:
    instruction_tokens = set(_WORD_PATTERN.findall(normalize_text(instruction)))
    response_tokens = set(_WORD_PATTERN.findall(normalize_text(response)))
    if not instruction_tokens or not response_tokens:
        return 0.0
    union = instruction_tokens | response_tokens
    overlap = len(instruction_tokens & response_tokens) / len(union)
    if overlap > 0.8:
        return max(0.0, 1 - (overlap - 0.8) * 5)
    return min(1.0, 0.6 + overlap)


def _constraint_score(text: str, constraints: list[str]) -> tuple[float, str]:
    checked = 0
    passed = 0
    normalized = normalize_text(text)
    for constraint in constraints:
        key, separator, value = constraint.partition(":")
        if not separator or not value.strip():
            continue
        key = key.strip().casefold()
        needle = normalize_text(value)
        if key == "must_include":
            checked += 1
            passed += int(needle in normalized)
        elif key == "must_not_include":
            checked += 1
            passed += int(needle not in normalized)
    if not checked:
        return 1.0, "No machine-checkable must_include or must_not_include constraints."
    return passed / checked, f"Satisfied {passed} of {checked} machine-checkable constraints."


class ExplainableScorer:
    """Compute stable components without invoking an LLM judge."""

    weights: ClassVar[dict[str, float]] = {
        "completeness": 0.15,
        "useful_length": 0.15,
        "instruction_response_overlap": 0.15,
        "lexical_richness": 0.15,
        "boilerplate": 0.10,
        # Novelty and pool diversity also have explicit duplicate hard gates in
        # QualityPipeline. Keep their soft weights bounded so the same evidence
        # is not counted twice while still rewarding more original examples.
        "seed_novelty": 0.10,
        "accepted_pool_diversity": 0.10,
        "constraints": 0.10,
    }

    def score(
        self,
        candidate: GeneratedCandidate,
        *,
        seed_similarity: float,
        accepted_similarity: float,
        constraints: list[str] | None = None,
    ) -> ScoreResult:
        instruction = candidate_instruction(candidate)
        response = candidate_response(candidate)
        full_text = candidate_text(candidate)
        normalized = normalize_text(full_text)
        constraint_score, constraint_explanation = _constraint_score(full_text, constraints or [])
        boilerplate_hits = [phrase for phrase in _BOILERPLATE if phrase in normalized]
        components = (
            _component("completeness", 1.0, "Canonical user and assistant content is present."),
            _component(
                "useful_length",
                _length_score(instruction, response),
                "Instruction and response lengths are measured against useful bounded ranges.",
                reason_code="insufficient_or_excessive_length",
            ),
            _component(
                "instruction_response_overlap",
                _instruction_response_overlap(instruction, response),
                "Instruction and response have related but non-copying vocabulary.",
                reason_code="unhelpful_instruction_response_overlap",
            ),
            _component(
                "lexical_richness",
                _lexical_richness(full_text),
                "Lexical variety and token volume are measured deterministically.",
                reason_code="low_lexical_richness",
            ),
            _component(
                "boilerplate",
                0.0 if boilerplate_hits else 1.0,
                "No known placeholder or model-disclaimer boilerplate was found."
                if not boilerplate_hits
                else f"Found boilerplate: {', '.join(boilerplate_hits)}.",
                reason_code="boilerplate_detected",
            ),
            _component(
                "seed_novelty",
                1 - max(0.0, seed_similarity),
                f"Nearest seed similarity is {seed_similarity:.3f}.",
                reason_code="low_seed_novelty",
            ),
            _component(
                "accepted_pool_diversity",
                1 - max(0.0, accepted_similarity),
                f"Nearest accepted-candidate similarity is {accepted_similarity:.3f}.",
                reason_code="low_pool_diversity",
            ),
            _component(
                "constraints",
                constraint_score,
                constraint_explanation,
                pass_at=1.0,
                reason_code="constraint_violation",
            ),
        )
        score = sum(self.weights[component.name] * component.score for component in components)
        return ScoreResult(score=round(score, 6), components=components)
