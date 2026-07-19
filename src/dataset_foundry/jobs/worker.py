"""Single-writer worker with bounded claims, renewals, retries, and cancellation."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass

from dataset_foundry.domain import RunStatus
from dataset_foundry.generation.service import GenerationService
from dataset_foundry.persistence import Repositories
from dataset_foundry.persistence.models import RunRecord
from dataset_foundry.persistence.repositories import LeaseClaim, LeaseLostError
from dataset_foundry.providers import ProviderTransientError


@dataclass(frozen=True, slots=True)
class WorkerResult:
    job_id: str
    run_id: str
    status: str
    error_type: str | None = None


class Worker:
    """Claim and process durable jobs one at a time."""

    def __init__(
        self,
        repositories: Repositories,
        generation: GenerationService,
        *,
        worker_id: str,
        lease_seconds: int = 120,
        heartbeat_seconds: float = 30,
        poll_seconds: float = 0.5,
    ) -> None:
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat_seconds must be positive")
        if heartbeat_seconds >= lease_seconds:
            raise ValueError("heartbeat_seconds must be shorter than lease_seconds")
        self.repositories = repositories
        self.generation = generation
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.poll_seconds = poll_seconds
        self.presence_ttl_seconds = max(
            1.0,
            heartbeat_seconds * 3,
            poll_seconds * 3,
        )
        self._presence_active = False
        self._presence_state = "idle"
        self._current_job_id: str | None = None

    async def run_once(self) -> WorkerResult | None:
        self.repositories.jobs.recover_expired()
        claim = self.repositories.jobs.claim_next(
            self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if claim is None:
            return None

        self._update_presence(state="busy", current_job_id=claim.job_id)
        try:
            try:
                run, active_claim = await self._process_with_periodic_renewal(claim)
                terminal = "cancelled" if run.status == RunStatus.cancelled.value else "completed"
                self.repositories.jobs.finish(active_claim, status=terminal)
                return WorkerResult(
                    job_id=claim.job_id,
                    run_id=claim.run_id,
                    status=terminal,
                )
            except LeaseLostError as exc:
                # Another worker owns the durable job now. The stale worker must stop
                # immediately and must not mutate either the replacement lease or run.
                return WorkerResult(
                    job_id=claim.job_id,
                    run_id=claim.run_id,
                    status="lease_lost",
                    error_type=type(exc).__name__,
                )
            except Exception as exc:
                retryable = isinstance(exc, ProviderTransientError)
                job = self.repositories.jobs.fail(claim, exc, retryable=retryable)
                self.repositories.runs.record_failure(claim.run_id, exc)
                if job.status == "failed":
                    run = self.repositories.runs.get(claim.run_id)
                    if run.status == RunStatus.running.value:
                        self.repositories.runs.transition(claim.run_id, RunStatus.failed)
                    self.repositories.audit.record(
                        event_type="run.failed",
                        entity_type="run",
                        entity_id=claim.run_id,
                        payload={"error_type": type(exc).__name__},
                    )
                return WorkerResult(
                    job_id=claim.job_id,
                    run_id=claim.run_id,
                    status=job.status,
                    error_type=type(exc).__name__,
                )
        finally:
            self._update_presence(state="idle")

    async def _process_with_periodic_renewal(
        self,
        claim: LeaseClaim,
    ) -> tuple[RunRecord, LeaseClaim]:
        """Run generation while renewing its lease independently of batch progress."""

        active_claim = claim
        stop_renewal = asyncio.Event()

        async def renew_periodically() -> None:
            nonlocal active_claim
            while not stop_renewal.is_set():
                try:
                    await asyncio.wait_for(
                        stop_renewal.wait(),
                        timeout=self.heartbeat_seconds,
                    )
                except TimeoutError:
                    active_claim = self.repositories.jobs.renew(
                        active_claim,
                        lease_seconds=self.lease_seconds,
                    )

        generation_task = asyncio.create_task(self.generation.process(claim.run_id))
        renewal_task = asyncio.create_task(renew_periodically())
        try:
            done, _ = await asyncio.wait(
                {generation_task, renewal_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if renewal_task in done:
                # ``result`` re-raises LeaseLostError (or an unexpected renewal
                # failure) before a stale generation task can persist more work.
                renewal_task.result()
                raise RuntimeError("lease renewal stopped before generation completed")

            stop_renewal.set()
            await renewal_task
            return await generation_task, active_claim
        finally:
            stop_renewal.set()
            for task in (generation_task, renewal_task):
                if not task.done():
                    task.cancel()
            for task in (generation_task, renewal_task):
                with suppress(asyncio.CancelledError, Exception):
                    await task

    async def run_forever(self, stop: asyncio.Event | None = None) -> None:
        stop_event = stop or asyncio.Event()
        self._presence_active = True
        self._update_presence(state="idle")
        heartbeat_task = asyncio.create_task(self._heartbeat_presence())
        try:
            while not stop_event.is_set():
                if heartbeat_task.done():
                    heartbeat_task.result()
                    raise RuntimeError("worker heartbeat stopped unexpectedly")
                result = await self.run_once()
                if result is not None:
                    continue
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.poll_seconds)
                except TimeoutError:
                    continue
        finally:
            self._presence_active = False
            if not heartbeat_task.done():
                heartbeat_task.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    await heartbeat_task
            finally:
                self.repositories.workers.stop(self.worker_id)

    def _update_presence(self, *, state: str, current_job_id: str | None = None) -> None:
        self._presence_state = state
        self._current_job_id = current_job_id
        if self._presence_active:
            self.repositories.workers.heartbeat(
                self.worker_id,
                state=state,
                current_job_id=current_job_id,
                ttl_seconds=self.presence_ttl_seconds,
            )

    async def _heartbeat_presence(self) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            self.repositories.workers.heartbeat(
                self.worker_id,
                state=self._presence_state,
                current_job_id=self._current_job_id,
                ttl_seconds=self.presence_ttl_seconds,
            )


def renew_claim(
    repositories: Repositories,
    claim: LeaseClaim,
    *,
    lease_seconds: int,
) -> LeaseClaim:
    """Public helper for long-running custom generation stages."""

    return repositories.jobs.renew(claim, lease_seconds=lease_seconds)
