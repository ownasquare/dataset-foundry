from __future__ import annotations

import pytest

from dataset_foundry.domain import (
    ALLOWED_RUN_TRANSITIONS,
    InvalidRunTransitionError,
    RunStatus,
    can_transition,
    validate_run_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunStatus.queued, RunStatus.running),
        (RunStatus.queued, RunStatus.cancelled),
        (RunStatus.running, RunStatus.completed),
        (RunStatus.running, RunStatus.failed),
        (RunStatus.running, RunStatus.cancelled),
    ],
)
def test_documented_run_transitions_are_legal(current: RunStatus, target: RunStatus) -> None:
    assert can_transition(current, target)
    validate_run_transition(current, target)


@pytest.mark.parametrize("terminal", list(RunStatus)[2:])
def test_terminal_runs_cannot_transition(terminal: RunStatus) -> None:
    assert ALLOWED_RUN_TRANSITIONS[terminal] == set()
    with pytest.raises(InvalidRunTransitionError, match="cannot transition"):
        validate_run_transition(terminal, RunStatus.running)


def test_queued_run_cannot_skip_to_completed() -> None:
    with pytest.raises(InvalidRunTransitionError):
        validate_run_transition(RunStatus.queued, RunStatus.completed)
