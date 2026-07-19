"""Structured generation provider adapters."""

from dataset_foundry.providers.anthropic import AnthropicProvider
from dataset_foundry.providers.base import (
    GenerationProvider,
    ProviderCandidate,
    ProviderCandidateBatch,
    ProviderConfigurationError,
    ProviderError,
    ProviderIncompleteError,
    ProviderPrivacyError,
    ProviderRefusalError,
    ProviderResponseError,
    ProviderTransientError,
)
from dataset_foundry.providers.offline import OfflineProvider
from dataset_foundry.providers.openai import OpenAIProvider
from dataset_foundry.providers.registry import ProviderRegistry

__all__ = [
    "AnthropicProvider",
    "GenerationProvider",
    "OfflineProvider",
    "OpenAIProvider",
    "ProviderCandidate",
    "ProviderCandidateBatch",
    "ProviderConfigurationError",
    "ProviderError",
    "ProviderIncompleteError",
    "ProviderPrivacyError",
    "ProviderRefusalError",
    "ProviderRegistry",
    "ProviderResponseError",
    "ProviderTransientError",
]
