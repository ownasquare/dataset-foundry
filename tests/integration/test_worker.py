from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import pytest

from dataset_foundry.domain import RunStatus
from dataset_foundry.generation.service import GenerationService
from dataset_foundry.jobs import Worker
from dataset_foundry.persistence.models import JobRecord
from tests.integration.test_generation_pipeline import create_run, make_container


class BlockingGeneration:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def process(self, _run_id: str) -> None:
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


@pytest.mark.asyncio
async def test_worker_honors_cancellation_before_generation(tmp_path: Path) -> None:
    container = make_container(tmp_path)
    run_id = create_run(container, target_count=3)
    container.repositories.runs.transition(run_id, RunStatus.cancelled)

    result = await container.worker().run_once()

    assert result is not None
    assert result.status == "cancelled"
    assert container.repositories.runs.get(run_id).status == "cancelled"
    assert container.repositories.candidates.list(run_id) == []


@pytest.mark.asyncio
async def test_worker_returns_none_when_queue_is_empty(tmp_path: Path) -> None:
    container = make_container(tmp_path)

    assert await container.worker().run_once() is None


@pytest.mark.asyncio
async def test_long_running_worker_reports_idle_and_graceful_stop(tmp_path: Path) -> None:
    container = make_container(tmp_path)
    stop = asyncio.Event()
    worker = Worker(
        container.repositories,
        container.generation,
        worker_id="presence-idle-test",
        lease_seconds=30,
        heartbeat_seconds=0.01,
        poll_seconds=0.01,
    )

    worker_task = asyncio.create_task(worker.run_forever(stop))
    await asyncio.sleep(0)
    status = container.repositories.workers.status()
    assert status.ready is True
    assert status.state == "idle"
    assert status.worker_id == "presence-idle-test"

    stop.set()
    await asyncio.wait_for(worker_task, timeout=1)
    stopped = container.repositories.workers.status()
    assert stopped.ready is False
    assert stopped.state == "stopped"


@pytest.mark.asyncio
async def test_long_running_worker_reports_busy_while_processing(tmp_path: Path) -> None:
    container = make_container(tmp_path)
    create_run(container, target_count=3)
    generation = BlockingGeneration()
    worker = Worker(
        container.repositories,
        cast(GenerationService, generation),
        worker_id="presence-busy-test",
        lease_seconds=30,
        heartbeat_seconds=0.01,
        poll_seconds=0.01,
    )

    worker_task = asyncio.create_task(worker.run_forever())
    await asyncio.wait_for(generation.started.wait(), timeout=1)
    status = container.repositories.workers.status()
    assert status.ready is True
    assert status.state == "busy"
    assert status.worker_id == "presence-busy-test"
    assert status.current_job_id is not None

    worker_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker_task
    assert generation.cancelled.is_set()
    assert container.repositories.workers.status().state == "stopped"


@pytest.mark.asyncio
async def test_worker_periodically_renews_and_interrupts_generation_on_lease_loss(
    tmp_path: Path,
) -> None:
    container = make_container(tmp_path)
    run_id = create_run(container, target_count=3)
    job = container.repositories.jobs.enqueue(run_id)
    generation = BlockingGeneration()
    worker = Worker(
        container.repositories,
        cast(GenerationService, generation),
        worker_id="lease-loss-test",
        lease_seconds=30,
        heartbeat_seconds=0.01,
    )

    worker_task = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(generation.started.wait(), timeout=1)
    with container.database.session() as session:
        stored_job = session.get(JobRecord, job.id)
        assert stored_job is not None
        stored_job.lease_owner = "replacement-worker"
        stored_job.lease_token = "replacement-token"
        stored_job.lease_epoch += 1

    result = await asyncio.wait_for(worker_task, timeout=1)

    assert result is not None
    assert result.status == "lease_lost"
    assert result.error_type == "LeaseLostError"
    assert generation.cancelled.is_set()
    assert container.repositories.jobs.get(job.id).lease_owner == "replacement-worker"
