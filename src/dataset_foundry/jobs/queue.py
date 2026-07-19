"""Small queue facade that keeps enqueue semantics explicit."""

from __future__ import annotations

from dataset_foundry.persistence import Repositories
from dataset_foundry.persistence.models import JobRecord


class JobQueue:
    def __init__(self, repositories: Repositories) -> None:
        self.repositories = repositories

    def enqueue(self, run_id: str, *, max_attempts: int = 3) -> JobRecord:
        return self.repositories.jobs.enqueue(run_id, max_attempts=max_attempts)

    def recover_expired(self) -> int:
        return self.repositories.jobs.recover_expired()
