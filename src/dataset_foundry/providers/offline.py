"""Deterministic lexical generator used for demos, tests, and air-gapped runs."""

from __future__ import annotations

import hashlib
import random
from typing import Final

from dataset_foundry.domain import (
    CandidateBatch,
    ChatMessage,
    GeneratedCandidate,
    GenerationBatchRequest,
    MessageRole,
    ProviderName,
    ProviderTrace,
)
from dataset_foundry.generation.prompts import PROMPT_VERSION
from dataset_foundry.providers.base import (
    ProviderConfigurationError,
    fingerprint_messages,
    validate_batch_size,
)


class OfflineProvider:
    """Produce reproducible, labeled template variations without network access."""

    name: Final = ProviderName.offline

    _tones: Final = (
        "clear and direct",
        "patient and reassuring",
        "concise and practical",
        "detailed and methodical",
        "friendly and professional",
        "technical but accessible",
        "empathetic and action-oriented",
    )
    _scenarios: Final = (
        "onboarding",
        "troubleshooting",
        "day-to-day operations",
        "an edge case",
        "a time-sensitive request",
        "a comparison decision",
        "a follow-up conversation",
        "a multi-step workflow",
    )
    _audiences: Final = (
        "first-time user",
        "experienced operator",
        "team lead",
        "support specialist",
        "small-business owner",
        "technical evaluator",
    )
    _response_patterns: Final = (
        "Lead with the answer, then give a short verification step.",
        "Explain the reasoning, provide numbered actions, and close with a check.",
        "Acknowledge the situation, give the safest next step, and name one fallback.",
        "Summarize the outcome, show the procedure, and identify a common pitfall.",
        "Give a concise recommendation followed by one concrete example.",
    )

    def __init__(self, model: str = "offline-deterministic-v1") -> None:
        self.model = model

    async def generate_batch(self, request: GenerationBatchRequest) -> CandidateBatch:
        if request.recipe.provider is not ProviderName.offline:
            raise ProviderConfigurationError(
                "OfflineProvider can only execute recipes whose provider is offline"
            )

        # Deterministic fixture generation is the requirement; this is not a security RNG.
        rng = random.Random(  # noqa: S311  # nosec B311
            request.recipe.random_seed + request.batch_index * 1_000_003
        )
        candidates: list[GeneratedCandidate] = []
        for offset in range(request.requested_count):
            global_index = request.batch_index * request.recipe.batch_size + offset
            seed = request.seed_examples[rng.randrange(len(request.seed_examples))]
            tone = self._tones[rng.randrange(len(self._tones))]
            scenario = self._scenarios[rng.randrange(len(self._scenarios))]
            audience = self._audiences[rng.randrange(len(self._audiences))]
            response_pattern = self._response_patterns[rng.randrange(len(self._response_patterns))]
            axis_values = {
                name: options[rng.randrange(len(options))]
                for name, options in sorted(request.recipe.diversity_axes.items())
            }
            impact = 2 + rng.randrange(97)
            elapsed_minutes = 3 + rng.randrange(238)

            instruction = self._instruction(
                seed_instruction=seed.instruction,
                scenario=scenario,
                audience=audience,
                tone=tone,
                impact=impact,
                elapsed_minutes=elapsed_minutes,
                axis_values=axis_values,
            )
            response = self._response(
                seed_response=seed.response,
                scenario=scenario,
                audience=audience,
                tone=tone,
                response_pattern=response_pattern,
                impact=impact,
            )
            messages: list[ChatMessage] = []
            if seed.system_prompt:
                messages.append(ChatMessage(role=MessageRole.system, content=seed.system_prompt))
            messages.extend(
                [
                    ChatMessage(role=MessageRole.user, content=instruction),
                    ChatMessage(role=MessageRole.assistant, content=response),
                ]
            )
            fingerprint = fingerprint_messages(messages)
            candidate_id = hashlib.sha256(
                f"{request.run_id}:{fingerprint}:{global_index}".encode()
            ).hexdigest()[:32]
            metadata = {
                "generator": "offline-deterministic",
                "scenario": scenario,
                "audience": audience,
                "tone": tone,
                "impact": impact,
                "elapsed_minutes": elapsed_minutes,
                "diversity_axes": axis_values,
            }
            candidates.append(
                GeneratedCandidate(
                    id=candidate_id,
                    messages=messages,
                    metadata=metadata,
                    source_seed_ids=[seed.id],
                    generation_index=global_index,
                    provider_trace=ProviderTrace(
                        provider=ProviderName.offline,
                        model=self.model,
                        mode="offline-deterministic",
                        prompt_version=PROMPT_VERSION,
                    ),
                    candidate_fingerprint=fingerprint,
                )
            )

        batch = CandidateBatch(candidates=candidates)
        validate_batch_size(batch, request)
        return batch

    @staticmethod
    def _instruction(
        *,
        seed_instruction: str,
        scenario: str,
        audience: str,
        tone: str,
        impact: int,
        elapsed_minutes: int,
        axis_values: dict[str, str],
    ) -> str:
        axis_context = ""
        if axis_values:
            values = ", ".join(f"{name}: {value}" for name, value in axis_values.items())
            axis_context = f" Account for these conditions: {values}."
        return (
            f"A {audience} is handling {scenario} and asks: {seed_instruction} "
            f"The situation has affected {impact} records over {elapsed_minutes} minutes. "
            f"Provide a {tone} answer with a concrete next action and a way to verify the "
            f"result.{axis_context}"
        )

    @staticmethod
    def _response(
        *,
        seed_response: str,
        scenario: str,
        audience: str,
        tone: str,
        response_pattern: str,
        impact: int,
    ) -> str:
        return (
            f"For this {audience}, use a {tone} approach. {seed_response.strip()} "
            f"Because this is {scenario}, apply the change to one record first, confirm the "
            f"expected result, and then continue with the remaining {impact - 1}. "
            f"{response_pattern} If the verification fails, stop and preserve the observed "
            "error before trying the fallback."
        )
