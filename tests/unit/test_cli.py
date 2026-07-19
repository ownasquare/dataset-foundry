from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from dataset_foundry import cli
from dataset_foundry.config import Settings
from dataset_foundry.container import Container

runner = CliRunner()


def make_container(tmp_path: Path) -> Container:
    return Container(
        Settings(
            environment="test",
            data_dir=tmp_path,
            database_url=f"sqlite:///{tmp_path / 'cli.sqlite3'}",
            artifact_dir=tmp_path / "artifacts",
            frontend_dist=tmp_path / "frontend-dist",
            _env_file=None,
        )
    )


def test_cli_help_lists_operational_commands() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    for command in ("serve", "worker", "demo", "generate", "export", "doctor"):
        assert command in result.stdout


def test_doctor_is_secret_safe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    container = make_container(tmp_path)
    monkeypatch.setattr(cli, "_container", lambda: container)

    result = runner.invoke(cli.app, ["doctor"])

    assert result.exit_code == 0
    assert "Database" in result.stdout
    assert "offline" in result.stdout
    assert "api_key" not in result.stdout.lower()


def test_worker_once_reports_empty_queue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    container = make_container(tmp_path)
    monkeypatch.setattr(cli, "_container", lambda: container)

    result = runner.invoke(cli.app, ["worker", "--once"])

    assert result.exit_code == 0
    assert "No queued jobs" in result.stdout
