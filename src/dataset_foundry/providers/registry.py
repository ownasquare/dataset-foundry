"""Explicit provider selection with no silent cross-provider fallback."""

from __future__ import annotations

from typing import Any

from dataset_foundry.config import Settings
from dataset_foundry.domain import ProviderName
from dataset_foundry.providers.anthropic import AnthropicProvider
from dataset_foundry.providers.base import GenerationProvider, ProviderConfigurationError
from dataset_foundry.providers.offline import OfflineProvider
from dataset_foundry.providers.openai import OpenAIProvider


class ProviderRegistry:
    """Construct and cache configured provider adapters on demand."""

    def __init__(
        self,
        settings: Settings,
        *,
        openai_client: Any | None = None,
        anthropic_client: Any | None = None,
    ) -> None:
        self.settings = settings
        self._openai_client = openai_client
        self._anthropic_client = anthropic_client
        self._providers: dict[tuple[ProviderName, str], GenerationProvider] = {}

    def get(self, provider: ProviderName | str, model: str | None = None) -> GenerationProvider:
        name = ProviderName(provider)
        resolved_model = model or self._default_model(name)
        key = (name, resolved_model)
        if key in self._providers:
            return self._providers[key]
        if name is ProviderName.offline:
            adapter: GenerationProvider = OfflineProvider(resolved_model)
        elif name is ProviderName.openai:
            if not self.settings.provider_configured(name.value) and self._openai_client is None:
                raise ProviderConfigurationError("OpenAI is not configured")
            adapter = OpenAIProvider(
                model=resolved_model,
                api_key=self.settings.openai_api_key,
                client=self._openai_client,
                retry_base_seconds=self.settings.provider_retry_base_seconds,
                timeout_seconds=self.settings.provider_timeout_seconds,
                max_output_tokens=self.settings.provider_max_output_tokens,
            )
        else:
            if not self.settings.provider_configured(name.value) and self._anthropic_client is None:
                raise ProviderConfigurationError("Anthropic is not configured")
            adapter = AnthropicProvider(
                model=resolved_model,
                api_key=self.settings.anthropic_api_key,
                client=self._anthropic_client,
                retry_base_seconds=self.settings.provider_retry_base_seconds,
                timeout_seconds=self.settings.provider_timeout_seconds,
                max_output_tokens=self.settings.provider_max_output_tokens,
            )
        self._providers[key] = adapter
        return adapter

    def status(self) -> dict[str, object]:
        providers = []
        for name in ProviderName:
            providers.append(
                {
                    "id": name.value,
                    "label": (
                        "OpenAI"
                        if name is ProviderName.openai
                        else name.value.replace("_", " ").title()
                    ),
                    "configured": self.settings.provider_configured(name.value),
                    "live": name is not ProviderName.offline,
                    "requires_external_data_transfer": name is not ProviderName.offline,
                    "model": self._default_model(name),
                }
            )
        return {
            "default_provider": self.settings.default_provider,
            "providers": providers,
        }

    def _default_model(self, provider: ProviderName) -> str:
        if provider is ProviderName.offline:
            return "offline-deterministic-v1"
        if provider is ProviderName.openai:
            return self.settings.openai_model
        return self.settings.anthropic_model
