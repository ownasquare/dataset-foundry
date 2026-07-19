from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from scripts.benchmark_durable import benchmark


@pytest.mark.scale
def test_complete_durable_workflow_benchmark() -> None:
    seed_path = Path(__file__).resolve().parents[2] / "examples/customer-support-seeds.jsonl"

    result = asyncio.run(benchmark(25, seed_path))

    assert result["mode"] == "offline-durable-workflow"
    assert result["target"] == 25
    assert result["accepted"] == 25
    assert result["exported"] == 25
    assert result["generated"] >= result["accepted"]
