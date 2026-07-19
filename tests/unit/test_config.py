from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from dataset_foundry.config import Settings


def test_blank_credentials_are_normalized_to_unset() -> None:
    settings = Settings(
        api_key="   ",
        OPENAI_API_KEY="\t",
        ANTHROPIC_API_KEY=SecretStr("\n"),
        _env_file=None,
    )

    assert settings.api_key is None
    assert settings.openai_api_key is None
    assert settings.anthropic_api_key is None
    assert not settings.provider_configured("openai")
    assert not settings.provider_configured("anthropic")


def test_provider_credentials_accept_python_field_names() -> None:
    settings = Settings(
        openai_api_key=" unit-openai-key ",
        anthropic_api_key=SecretStr(" unit-anthropic-key "),
        _env_file=None,
    )

    assert settings.provider_configured("openai")
    assert settings.provider_configured("anthropic")


def test_blank_api_key_cannot_authorize_a_non_loopback_binding() -> None:
    with pytest.raises(ValidationError, match="non-loopback binding requires"):
        Settings(host="0.0.0.0", api_key=" ", _env_file=None)  # noqa: S104


def test_container_wildcard_requires_explicit_loopback_publish_opt_in() -> None:
    with pytest.raises(ValidationError, match="non-loopback binding requires"):
        Settings(
            environment="container",
            host="0.0.0.0",  # noqa: S104
            api_key=None,
            _env_file=None,
        )

    settings = Settings(
        environment="container",
        host="0.0.0.0",  # noqa: S104
        api_key=None,
        allow_unauthenticated_container_loopback=True,
        _env_file=None,
    )
    assert settings.allow_unauthenticated_container_loopback

    with pytest.raises(ValidationError, match="non-loopback binding requires"):
        Settings(
            environment="development",
            host="0.0.0.0",  # noqa: S104
            api_key=None,
            allow_unauthenticated_container_loopback=True,
            _env_file=None,
        )
