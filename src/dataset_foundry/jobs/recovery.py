"""Lease recovery entry point used at worker startup and by operations tooling."""

from __future__ import annotations

from dataset_foundry.persistence import Repositories


def recover_expired_jobs(repositories: Repositories) -> int:
    """Return expired non-terminal jobs to the queue without duplicating work."""

    recovered = repositories.jobs.recover_expired()
    if recovered:
        repositories.audit.record(
            event_type="jobs.recovered",
            entity_type="worker",
            entity_id="lease-recovery",
            payload={"recovered_count": recovered},
        )
    return recovered
