from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from dataset_foundry.config import Settings
from dataset_foundry.container import Container
from dataset_foundry.domain import (
    CandidateBatch,
    ChatMessage,
    GeneratedCandidate,
    GenerationBatchRequest,
    GenerationRecipe,
    MessageRole,
    ProviderName,
    ProviderTrace,
    TrainingExample,
)
from dataset_foundry.generation.service import GenerationService, select_batch_seeds
from dataset_foundry.ingestion import fingerprint_dataset
from dataset_foundry.providers import ProviderRegistry


def make_container(tmp_path: Path, *, frontend_dist: Path | None = None) -> Container:
    settings = Settings(
        environment="test",
        data_dir=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'test.sqlite3'}",
        artifact_dir=tmp_path / "artifacts",
        frontend_dist=frontend_dist or tmp_path / "frontend-dist",
        _env_file=None,
    )
    return Container(settings)


def seeds() -> list[TrainingExample]:
    return [
        TrainingExample(
            id="seed-password",
            messages=[
                ChatMessage(role=MessageRole.user, content="How do I reset my password?"),
                ChatMessage(
                    role=MessageRole.assistant,
                    content="Open Security settings and request a time-limited reset link.",
                ),
            ],
        ),
        TrainingExample(
            id="seed-billing",
            messages=[
                ChatMessage(role=MessageRole.user, content="Where can I update billing details?"),
                ChatMessage(
                    role=MessageRole.assistant,
                    content="Open Billing, edit the saved details, and verify the next invoice.",
                ),
            ],
        ),
    ]


def many_seeds(count: int) -> list[TrainingExample]:
    return [
        TrainingExample(
            id=f"seed-{index:03d}",
            messages=[
                ChatMessage(
                    role=MessageRole.user,
                    content=f"How should I resolve account scenario {index}?",
                ),
                ChatMessage(
                    role=MessageRole.assistant,
                    content=(
                        f"Verify account scenario {index}, update one record, and confirm "
                        "the saved result before continuing."
                    ),
                ),
            ],
        )
        for index in range(count)
    ]


def test_large_seed_selection_is_stratified_rotating_and_replay_safe() -> None:
    examples = many_seeds(250)

    first = select_batch_seeds(examples, random_seed=17, batch_index=0)
    second = select_batch_seeds(examples, random_seed=17, batch_index=1)
    replay = select_batch_seeds(examples, random_seed=17, batch_index=0)

    assert len(first) == len(second) == 100
    assert [example.id for example in replay] == [example.id for example in first]
    assert len({example.id for example in first}) == 100
    assert len({example.id for example in first + second}) == 200
    for stratum_index, example in enumerate(first):
        example_index = int(example.id.removeprefix("seed-"))
        assert stratum_index * len(examples) // 100 <= example_index
        assert example_index < (stratum_index + 1) * len(examples) // 100


def create_run(container: Container, *, target_count: int = 7) -> str:
    project = container.repositories.projects.create(name="Support")
    examples = seeds()
    dataset = container.repositories.datasets.create(
        project_id=project.id,
        name="Seeds",
        fingerprint=fingerprint_dataset(examples),
        examples=examples,
    )
    recipe = GenerationRecipe(
        name="Offline expansion",
        dataset_id=dataset.id,
        target_count=target_count,
        batch_size=4,
        candidate_multiplier=3,
        quality_threshold=0,
        similarity_threshold=1,
        random_seed=17,
    )
    recipe_record = container.repositories.recipes.create(dataset.id, recipe)
    return container.generation.enqueue(
        dataset_id=dataset.id,
        recipe_id=recipe_record.id,
    ).id


@pytest.mark.asyncio
async def test_offline_pipeline_is_bounded_and_replay_safe(tmp_path: Path) -> None:
    container = make_container(tmp_path)
    run_id = create_run(container)

    result = await container.worker().run_once()

    assert result is not None
    assert result.status == "completed"
    completed = container.repositories.runs.get(run_id)
    assert completed.accepted_count == completed.target_count == 7
    assert completed.generated_count <= completed.candidate_budget
    first_fingerprints = {
        record.candidate_fingerprint for record in container.repositories.candidates.list(run_id)
    }

    replayed = await container.generation.process(run_id)

    assert replayed.status == "completed"
    assert {
        record.candidate_fingerprint for record in container.repositories.candidates.list(run_id)
    } == first_fingerprints


@pytest.mark.asyncio
async def test_same_offline_recipe_reproduces_candidate_content(tmp_path: Path) -> None:
    container = make_container(tmp_path)
    first_run_id = create_run(container, target_count=5)
    first = await container.worker().run_once()
    assert first is not None and first.status == "completed"

    first_run = container.repositories.runs.get(first_run_id)
    second_run_id = container.generation.enqueue(
        dataset_id=first_run.dataset_id,
        recipe_id=first_run.recipe_id,
    ).id
    second = await container.worker().run_once()
    assert second is not None and second.status == "completed"

    assert {
        record.candidate_fingerprint
        for record in container.repositories.candidates.list(first_run_id)
    } == {
        record.candidate_fingerprint
        for record in container.repositories.candidates.list(second_run_id)
    }


class HalfAcceptanceProvider:
    name = ProviderName.offline
    model = "half-acceptance-test"

    async def generate_batch(self, request: GenerationBatchRequest) -> CandidateBatch:
        seed = request.seed_examples[0]
        candidates = []
        for offset in range(request.requested_count):
            index = request.batch_index * request.recipe.batch_size + offset
            if index % 2 == 0:
                messages = seed.messages
            else:
                messages = [
                    ChatMessage(
                        role=MessageRole.user,
                        content=f"Unique scenario {index}: explain the safe account workflow.",
                    ),
                    ChatMessage(
                        role=MessageRole.assistant,
                        content=(
                            f"For scenario {index}, verify identity, change one setting, "
                            "confirm the saved result, and document a fallback if it fails."
                        ),
                    ),
                ]
            candidates.append(
                GeneratedCandidate(
                    id=f"{request.run_id}-{index}",
                    messages=messages,
                    metadata={"index": index},
                    source_seed_ids=[seed.id],
                    generation_index=index,
                    provider_trace=ProviderTrace(
                        provider=ProviderName.offline,
                        model=self.model,
                        mode="test-double",
                    ),
                )
            )
        return CandidateBatch(candidates=candidates)


class HalfAcceptanceRegistry:
    def get(self, _provider: object, _model: object) -> HalfAcceptanceProvider:
        return HalfAcceptanceProvider()


@pytest.mark.asyncio
async def test_candidate_multiplier_reaches_target_at_half_acceptance(tmp_path: Path) -> None:
    container = make_container(tmp_path)
    project = container.repositories.projects.create(name="Multiplier")
    example = seeds()[0]
    dataset = container.repositories.datasets.create(
        project_id=project.id,
        name="Multiplier seeds",
        fingerprint=fingerprint_dataset([example]),
        examples=[example],
    )
    recipe = GenerationRecipe(
        name="Half acceptance",
        dataset_id=dataset.id,
        target_count=3,
        batch_size=4,
        candidate_multiplier=2,
        quality_threshold=0,
        similarity_threshold=1,
    )
    recipe_record = container.repositories.recipes.create(dataset.id, recipe)
    container.generation = GenerationService(
        container.repositories,
        cast(ProviderRegistry, HalfAcceptanceRegistry()),
    )
    run = container.generation.enqueue(dataset_id=dataset.id, recipe_id=recipe_record.id)

    result = await container.worker().run_once()

    assert result is not None and result.status == "completed"
    completed = container.repositories.runs.get(run.id)
    assert completed.accepted_count == 3
    assert completed.rejected_count == 3
    assert completed.generated_count == completed.candidate_budget == 6
