"""Anthropic Messages API adapter using native Pydantic structured outputs."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from anthropic import AsyncAnthropic
from pydantic import SecretStr, ValidationError

from dataset_foundry.domain import CandidateBatch, GenerationBatchRequest, ProviderName
from dataset_foundry.generation.prompts import PROMPT_VERSION, build_generation_prompt
from dataset_foundry.providers.base import (
    ProviderCandidateBatch,
    ProviderConfigurationError,
    ProviderIncompleteError,
    ProviderRefusalError,
    ProviderResponseError,
    normalize_live_batch,
    require_external_transfer_consent,
    retry_transient,
)


class AnthropicProvider:
    """Generate candidates through ``messages.parse`` without JSON repair loops."""

    name = ProviderName.anthropic

    def __init__(
        self,
        *,
        model: str,
        api_key: SecretStr | str | None = None,
        client: Any | None = None,
        max_retries: int = 2,
        retry_base_seconds: float = 0.25,
        timeout_seconds: float = 120,
        max_output_tokens: int = 8_192,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if client is None and api_key is None:
            raise ProviderConfigurationError("Anthropic is not configured")
        key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        self._client = client or AsyncAnthropic(
            api_key=key,
            max_retries=0,
            timeout=timeout_seconds,
        )
        self.model = model
        self.max_retries = max_retries
        self.retry_base_seconds = retry_base_seconds
        self.max_output_tokens = max_output_tokens
        self._sleep = sleep

    async def generate_batch(self, request: GenerationBatchRequest) -> CandidateBatch:
        require_external_transfer_consent(request)
        if request.recipe.provider is not ProviderName.anthropic:
            raise ProviderConfigurationError(
                "AnthropicProvider can only execute recipes whose provider is anthropic"
            )
        system, user = build_generation_prompt(request)

        async def operation() -> Any:
            return await self._client.messages.parse(
                model=self.model,
                max_tokens=self.max_output_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=ProviderCandidateBatch,
            )

        started = time.perf_counter()
        retry_kwargs: dict[str, Any] = {
            "max_retries": min(self.max_retries, request.recipe.max_retries),
            "base_delay_seconds": self.retry_base_seconds,
            "is_transient": _is_transient,
        }
        if self._sleep is not None:
            retry_kwargs["sleep"] = self._sleep
        try:
            message = await retry_transient(operation, **retry_kwargs)
        except Exception as exc:
            name = type(exc).__name__
            if name in {"LengthFinishReasonError", "IncompleteOutputError"}:
                raise ProviderIncompleteError("Anthropic output was truncated") from exc
            if name in {"ContentFilterFinishReasonError", "SafetyError"}:
                raise ProviderRefusalError("Anthropic refused the generation request") from exc
            if name in {"AuthenticationError", "PermissionDeniedError"}:
                raise ProviderConfigurationError("Anthropic authentication failed") from exc
            if isinstance(
                exc,
                (
                    ProviderConfigurationError,
                    ProviderIncompleteError,
                    ProviderRefusalError,
                    ProviderResponseError,
                ),
            ):
                raise
            if type(exc).__name__ == "ProviderTransientError":
                raise
            raise ProviderResponseError("Anthropic request failed") from exc
        latency_ms = (time.perf_counter() - started) * 1_000

        stop_reason = getattr(message, "stop_reason", None)
        if stop_reason == "max_tokens":
            raise ProviderIncompleteError("Anthropic returned a truncated structured response")
        if stop_reason == "refusal":
            raise ProviderRefusalError("Anthropic refused the generation request")
        parsed = getattr(message, "parsed_output", None)
        if parsed is None:
            raise ProviderResponseError("Anthropic returned no parsed structured output")
        try:
            batch = (
                parsed
                if isinstance(parsed, ProviderCandidateBatch)
                else ProviderCandidateBatch.model_validate(parsed)
            )
        except ValidationError as exc:
            raise ProviderResponseError("Anthropic output violated the candidate schema") from exc

        usage = getattr(message, "usage", None)
        return normalize_live_batch(
            batch,
            request,
            provider=self.name,
            model=self.model,
            prompt_version=PROMPT_VERSION,
            request_id=getattr(message, "id", None),
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )


def _is_transient(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429 or (isinstance(status_code, int) and status_code >= 500):
        return True
    return type(exc).__name__ in {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
    }
