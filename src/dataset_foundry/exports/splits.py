"""Deterministic lineage-grouped train, validation, and test assignment."""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from dataset_foundry.domain import GeneratedCandidate

SPLIT_ORDER = ("train", "validation", "test")
DEFAULT_SPLIT_RATIOS = {"train": 0.90, "validation": 0.05, "test": 0.05}


@dataclass(frozen=True, slots=True)
class SplitAssignment:
    by_candidate_id: dict[str, str]
    counts: dict[str, int]
    ratios: dict[str, float]


def lineage_group(candidate: GeneratedCandidate) -> str:
    """Return a stable representative for a single candidate's direct lineage."""

    return sorted(candidate.source_seed_ids)[0] if candidate.source_seed_ids else candidate.id


def _connected_lineage_groups(
    candidates: Sequence[GeneratedCandidate],
) -> list[tuple[tuple[str, str], list[GeneratedCandidate]]]:
    """Group candidates by transitive overlap across every source seed ID."""

    parents: dict[str, str] = {}

    def find(seed_id: str) -> str:
        parent = parents.setdefault(seed_id, seed_id)
        while parent != parents[parent]:
            parents[parent] = parents[parents[parent]]
            parent = parents[parent]
        root = parent
        current = seed_id
        while parents[current] != root:
            next_id = parents[current]
            parents[current] = root
            current = next_id
        return root

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        root, child = sorted((left_root, right_root))
        parents[child] = root

    for candidate in candidates:
        seed_ids = sorted(candidate.source_seed_ids)
        if not seed_ids:
            continue
        find(seed_ids[0])
        for seed_id in seed_ids[1:]:
            union(seed_ids[0], seed_id)

    groups: dict[tuple[str, str], list[GeneratedCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.source_seed_ids:
            key = ("seed", find(sorted(candidate.source_seed_ids)[0]))
        else:
            key = ("candidate", candidate.id)
        groups[key].append(candidate)
    return sorted(groups.items())


def grouped_split(
    candidates: Sequence[GeneratedCandidate],
    *,
    seed: int,
    ratios: dict[str, float] | None = None,
) -> SplitAssignment:
    configured = dict(ratios or DEFAULT_SPLIT_RATIOS)
    if set(configured) != set(SPLIT_ORDER):
        raise ValueError("split ratios must define train, validation, and test")
    if any(value < 0 for value in configured.values()) or abs(sum(configured.values()) - 1) > 1e-9:
        raise ValueError("split ratios must be non-negative and sum to 1")

    group_items = _connected_lineage_groups(candidates)
    # Dataset splits must be reproducible; this value is never used as a secret.
    random.Random(seed).shuffle(group_items)  # noqa: S311  # nosec B311

    total = len(candidates)
    targets = {name: configured[name] * total for name in SPLIT_ORDER}
    counts = {name: 0 for name in SPLIT_ORDER}
    assignments: dict[str, str] = {}
    for _group_id, members in group_items:

        def remaining_fraction(split: str) -> float:
            target = targets[split]
            if target == 0:
                return float("-inf")
            return (target - counts[split]) / target

        selected = max(
            SPLIT_ORDER,
            key=lambda split: (remaining_fraction(split), -SPLIT_ORDER.index(split)),
        )
        for candidate in members:
            assignments[candidate.id] = selected
        counts[selected] += len(members)

    actual_ratios = {name: (counts[name] / total if total else 0.0) for name in SPLIT_ORDER}
    return SplitAssignment(
        by_candidate_id=assignments,
        counts=counts,
        ratios=actual_ratios,
    )
