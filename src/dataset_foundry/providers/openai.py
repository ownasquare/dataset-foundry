"""OpenAI Responses API adapter using native Pydantic structured outputs."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from openai import AsyncOpenAI
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


class OpenAIProvider:
    """Generate candidates through ``responses.parse`` without JSON repair loops."""

    name = ProviderName.openai

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
            raise ProviderConfigurationError("OpenAI is not configured")
        key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        self._client = client or AsyncOpenAI(
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
        if request.recipe.provider is not ProviderName.openai:
            raise ProviderConfigurationError(
                "OpenAIProvider can only execute recipes whose provider is openai"
            )
        system, user = build_generation_prompt(request)

        async def operation() -> Any:
            return await self._client.responses.parse(
                model=self.model,
                instructions=system,
                input=user,
                text_format=ProviderCandidateBatch,
                max_output_tokens=self.max_output_tokens,
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
            response = await retry_transient(operation, **retry_kwargs)
        except Exception as exc:
            name = type(exc).__name__
            if name in {"LengthFinishReasonError", "IncompleteOutputError"}:
                raise ProviderIncompleteError("OpenAI output was truncated") from exc
            if name in {"ContentFilterFinishReasonError", "SafetyError"}:
                raise ProviderRefusalError("OpenAI refused the generation request") from exc
            if name in {"AuthenticationError", "PermissionDeniedError"}:
                raise ProviderConfigurationError("OpenAI authentication failed") from exc
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
            raise ProviderResponseError("OpenAI request failed") from exc
        latency_ms = (time.perf_counter() - started) * 1_000

        if getattr(response, "status", None) == "incomplete":
            raise ProviderIncompleteError("OpenAI returned an incomplete structured response")
        refusal = _extract_refusal(response)
        if refusal:
            raise ProviderRefusalError("OpenAI refused the generation request")
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            raise ProviderResponseError("OpenAI returned no parsed structured output")
        try:
            batch = (
                parsed
                if isinstance(parsed, ProviderCandidateBatch)
                else ProviderCandidateBatch.model_validate(parsed)
            )
        except ValidationError as exc:
            raise ProviderResponseError("OpenAI output violated the candidate schema") from exc

        usage = getattr(response, "usage", None)
        return normalize_live_batch(
            batch,
            request,
            provider=self.name,
            model=self.model,
            prompt_version=PROMPT_VERSION,
            request_id=getattr(response, "id", None),
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


def _extract_refusal(response: Any) -> bool:
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            if getattr(content, "type", None) == "refusal":
                return True
    return False
