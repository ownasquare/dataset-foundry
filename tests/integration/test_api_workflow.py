from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from dataset_foundry.api import create_app
from dataset_foundry.config import Settings
from dataset_foundry.container import Container
from dataset_foundry.domain import (
    CandidateDecision,
    ChatMessage,
    GeneratedCandidate,
    GenerationRecipe,
    ProviderName,
    ProviderTrace,
    QualityReport,
    RunStatus,
    TrainingExample,
)
from dataset_foundry.ingestion import fingerprint_dataset
from tests.integration.test_generation_pipeline import make_container


def test_http_seed_to_export_workflow(tmp_path: Path) -> None:
    container = make_container(tmp_path)
    client = TestClient(create_app(container))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    project_response = client.post(
        "/api/v1/projects",
        json={"name": "API support project", "description": "Contract test"},
    )
    assert project_response.status_code == 201
    project = project_response.json()

    rows = [
        {
            "instruction": "How do I update my email?",
            "output": "Open Profile, edit the email, and verify the confirmation message.",
        },
        {
            "instruction": "How can I download an invoice?",
            "output": "Open Billing history and choose Download beside the invoice.",
        },
    ]
    rows.append(dict(rows[0]))
    content = "\n".join(json.dumps(row) for row in rows).encode()
    upload = client.post(
        f"/api/v1/projects/{project['id']}/seeds",
        files={"file": ("support.jsonl", content, "application/x-ndjson")},
        data={"dataset_name": "Support seeds"},
    )
    assert upload.status_code == 201, upload.text
    dataset = upload.json()
    assert dataset["row_count"] == 2
    assert dataset["duplicate_count"] == 1

    recipe_response = client.post(
        f"/api/v1/projects/{project['id']}/recipes",
        json={
            "dataset_id": dataset["id"],
            "name": "Offline API recipe",
            "target_count": 5,
            "batch_size": 5,
            "candidate_multiplier": 3,
            "min_quality_score": 0,
            "max_similarity": 1,
            "provider": "offline",
            "model": "offline-deterministic-v1",
            "allow_external_data_transfer": False,
        },
    )
    assert recipe_response.status_code == 201, recipe_response.text
    recipe = recipe_response.json()

    preflight = client.post(f"/api/v1/recipes/{recipe['id']}/preflight", json={})
    assert preflight.status_code == 200, preflight.text
    assert preflight.json()["ready"] is True
    assert preflight.json()["worker_ready"] is False
    assert preflight.json()["seed_count"] == 2
    assert preflight.json()["candidate_budget"] == 15

    api_only_status = client.get("/api/v1/system/status")
    assert api_only_status.status_code == 200
    assert api_only_status.json()["api_ready"] is True
    assert api_only_status.json()["worker_ready"] is False
    assert api_only_status.json()["worker_state"] == "missing"

    container.repositories.workers.heartbeat(
        "api-test-worker",
        state="idle",
        ttl_seconds=30,
    )
    ready_preflight = client.post(f"/api/v1/recipes/{recipe['id']}/preflight", json={})
    assert ready_preflight.status_code == 200
    assert ready_preflight.json()["ready"] is True
    assert ready_preflight.json()["worker_ready"] is True

    queued = client.post(
        "/api/v1/runs",
        json={"project_id": project["id"], "recipe_id": recipe["id"]},
    )
    assert queued.status_code == 202, queued.text
    run = queued.json()
    assert run["status"] == "queued"

    export_payload = {
        "project_id": project["id"],
        "name": "Support canonical snapshot",
        "formats": ["canonical_jsonl"],
        "train_percent": 80,
        "validation_percent": 10,
        "test_percent": 10,
    }
    missing_project = client.post(
        f"/api/v1/runs/{run['id']}/exports",
        json={**export_payload, "project_id": "missing-project"},
    )
    assert missing_project.status_code == 404
    assert missing_project.json()["code"] == "export_project_not_found"
    assert missing_project.json()["errors"][0]["loc"] == ["body", "project_id"]

    missing_run = client.post(
        "/api/v1/runs/missing-run/exports",
        json=export_payload,
    )
    assert missing_run.status_code == 404
    assert missing_run.json()["code"] == "export_run_not_found"
    assert missing_run.json()["errors"][0]["loc"] == ["path", "run_id"]

    other_project_response = client.post(
        "/api/v1/projects",
        json={"name": "Other API project"},
    )
    assert other_project_response.status_code == 201
    mismatch = client.post(
        f"/api/v1/runs/{run['id']}/exports",
        json={**export_payload, "project_id": other_project_response.json()["id"]},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "export_run_project_mismatch"

    incomplete = client.post(f"/api/v1/runs/{run['id']}/exports", json=export_payload)
    assert incomplete.status_code == 409
    assert incomplete.json()["code"] == "export_run_not_complete"
    assert incomplete.json()["errors"][0]["loc"] == ["path", "run_id"]

    worker_result = asyncio.run(container.worker().run_once())
    assert worker_result is not None and worker_result.status == "completed"

    completed = client.get(f"/api/v1/runs/{run['id']}")
    assert completed.status_code == 200
    assert completed.json()["accepted_count"] == 5

    candidates_response = client.get(
        f"/api/v1/runs/{run['id']}/candidates",
        params={"decision": "accepted"},
    )
    assert candidates_response.status_code == 200, candidates_response.text
    candidates = candidates_response.json()["items"]
    assert len(candidates) == 5
    assert candidates[0]["example"]["messages"][0]["role"] in {"system", "user"}
    assert candidates[0]["source_examples"]
    assert candidates[0]["source_examples"][0]["messages"][0]["role"] == "user"
    assert "quality_reasons" in candidates[0]
    assert [item["code"] for item in candidates[0]["quality_reasons"]] == candidates[0][
        "reason_codes"
    ]

    review = client.post(
        f"/api/v1/candidates/{candidates[0]['id']}/reviews",
        json={"decision": "needs_review", "note": "Check domain terminology."},
    )
    assert review.status_code == 201, review.text
    assert review.json()["decision"] == "needs_review"
    reviewed_run = client.get(f"/api/v1/runs/{run['id']}")
    assert reviewed_run.status_code == 200
    assert reviewed_run.json()["accepted_count"] == 4
    assert reviewed_run.json()["needs_review_count"] == 1

    exported = client.post(
        f"/api/v1/runs/{run['id']}/exports",
        json=export_payload,
    )
    assert exported.status_code == 201, exported.text
    export = exported.json()
    assert export["status"] == "ready"
    assert export["manifest"]["name"] == "Support canonical snapshot"
    assert export["manifest"]["requested_formats"] == ["canonical_jsonl"]
    assert export["manifest"]["requested_split_ratios"] == {
        "train": 0.8,
        "validation": 0.1,
        "test": 0.1,
    }
    assert [artifact["format"] for artifact in export["artifacts"]] == [
        "canonical_jsonl",
        None,
    ]
    canonical = next(
        artifact for artifact in export["artifacts"] if artifact["filename"] == "canonical.jsonl"
    )
    download = client.get(canonical["download_url"])
    assert download.status_code == 200
    assert len(download.content.splitlines()) == 4

    providers = client.get("/api/v1/providers")
    assert providers.status_code == 200
    assert "api_key" not in providers.text.lower()
    assert (
        next(item["label"] for item in providers.json()["providers"] if item["id"] == "openai")
        == "OpenAI"
    )


def test_http_worker_accepts_seed_datasets_larger_than_provider_context(tmp_path: Path) -> None:
    container = make_container(tmp_path)
    client = TestClient(create_app(container))
    project_response = client.post(
        "/api/v1/projects",
        json={"name": "Large seed project"},
    )
    assert project_response.status_code == 201
    project = project_response.json()

    rows = [
        {
            "id": f"large-seed-{index:03d}",
            "instruction": f"How should I handle support scenario {index}?",
            "output": (
                f"Verify support scenario {index}, update one record, and confirm the "
                "saved result before continuing."
            ),
        }
        for index in range(205)
    ]
    content = "\n".join(json.dumps(row) for row in rows).encode()
    upload = client.post(
        f"/api/v1/projects/{project['id']}/seeds",
        files={"file": ("large-seeds.jsonl", content, "application/x-ndjson")},
        data={"dataset_name": "Large support seeds"},
    )
    assert upload.status_code == 201, upload.text
    dataset = upload.json()
    assert dataset["row_count"] == 205

    recipe_response = client.post(
        f"/api/v1/projects/{project['id']}/recipes",
        json={
            "dataset_id": dataset["id"],
            "name": "Large seed offline recipe",
            "target_count": 3,
            "batch_size": 2,
            "candidate_multiplier": 2,
            "min_quality_score": 0,
            "max_similarity": 1,
            "provider": "offline",
            "model": "offline-deterministic-v1",
            "allow_external_data_transfer": False,
        },
    )
    assert recipe_response.status_code == 201, recipe_response.text
    recipe = recipe_response.json()
    queued = client.post(
        "/api/v1/runs",
        json={"project_id": project["id"], "recipe_id": recipe["id"]},
    )
    assert queued.status_code == 202, queued.text

    worker_result = asyncio.run(container.worker().run_once())

    assert worker_result is not None and worker_result.status == "completed"
    completed = client.get(f"/api/v1/runs/{queued.json()['id']}")
    assert completed.status_code == 200
    assert completed.json()["accepted_count"] == 3
    candidates = client.get(f"/api/v1/runs/{queued.json()['id']}/candidates")
    assert candidates.status_code == 200
    source_ids = {
        source_id
        for candidate in candidates.json()["items"]
        for source_id in candidate["source_seed_ids"]
    }
    assert source_ids
    persisted_seed_ids = {
        example.id for example in container.repositories.datasets.list_examples(dataset["id"])
    }
    assert source_ids <= persisted_seed_ids


def test_candidate_api_uses_server_filtered_cursor_pagination(tmp_path: Path) -> None:
    container = make_container(tmp_path)
    project = container.repositories.projects.create(name="Pagination project")
    seed = TrainingExample(
        id="pagination-seed",
        messages=[
            ChatMessage(role="user", content="How should an agent verify an account update?"),
            ChatMessage(
                role="assistant",
                content="Confirm the requested change, save it, and read the value back.",
            ),
        ],
    )
    dataset = container.repositories.datasets.create(
        project_id=project.id,
        name="Pagination seeds",
        fingerprint=fingerprint_dataset([seed]),
        examples=[seed],
    )
    recipe = GenerationRecipe(name="Pagination recipe", target_count=105)
    recipe_record = container.repositories.recipes.create(dataset.id, recipe)
    run = container.repositories.runs.create(
        dataset_id=dataset.id,
        recipe_id=recipe_record.id,
        target_count=recipe.target_count,
        candidate_budget=recipe.candidate_budget,
        dataset_fingerprint=dataset.fingerprint,
        recipe_fingerprint=recipe_record.fingerprint,
    )
    container.repositories.runs.transition(run.id, RunStatus.running)

    for index in range(105):
        candidate = GeneratedCandidate(
            id=f"pagination-candidate-{index:03d}",
            generation_index=index,
            messages=[
                ChatMessage(role="user", content=f"Review account update scenario {index}."),
                ChatMessage(
                    role="assistant",
                    content=f"Verify scenario {index}, save the record, and confirm the result.",
                ),
            ],
            source_seed_ids=[seed.id],
            provider_trace=ProviderTrace(
                provider=ProviderName.offline,
                model="offline-deterministic-v1",
                mode="offline-deterministic",
            ),
        )
        container.repositories.candidates.add(run.id, candidate)
        decision = CandidateDecision.needs_review if index == 104 else CandidateDecision.accepted
        report_kwargs: dict[str, object] = {}
        if index == 104:
            report_kwargs = {
                "reason_codes": ["policy_not_grounded"],
                "explanations": ["The answer needs an explicit policy citation."],
            }
        container.repositories.candidates.save_quality_report(
            QualityReport(
                candidate_id=candidate.id,
                score=0.9,
                automated_decision=decision,
                **report_kwargs,
            )
        )

    client = TestClient(create_app(container))
    accepted_ids: list[str] = []
    cursor: str | None = None
    while True:
        params = {"decision": "accepted", "limit": 40}
        if cursor is not None:
            params["cursor"] = cursor
        response = client.get(f"/api/v1/runs/{run.id}/candidates", params=params)
        assert response.status_code == 200, response.text
        page = response.json()
        accepted_ids.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert len(accepted_ids) == 104
    assert len(set(accepted_ids)) == 104
    needs_review = client.get(
        f"/api/v1/runs/{run.id}/candidates",
        params={"decision": "needs_review", "limit": 40},
    )
    assert needs_review.status_code == 200
    assert [item["id"] for item in needs_review.json()["items"]] == ["pagination-candidate-104"]
    reason = needs_review.json()["items"][0]["quality_reasons"][0]
    assert reason == {
        "code": "policy_not_grounded",
        "evidence": "The answer needs an explicit policy citation.",
    }


def test_export_problem_identifies_a_completed_run_without_accepted_examples(
    tmp_path: Path,
) -> None:
    container = make_container(tmp_path)
    project = container.repositories.projects.create(name="Empty accepted pool")
    seed = TrainingExample(
        id="empty-export-seed",
        messages=[
            ChatMessage(role="user", content="How should an account change be verified?"),
            ChatMessage(role="assistant", content="Save the change and read it back."),
        ],
    )
    dataset = container.repositories.datasets.create(
        project_id=project.id,
        name="Empty export seeds",
        fingerprint=fingerprint_dataset([seed]),
        examples=[seed],
    )
    recipe = GenerationRecipe(name="Empty export recipe", target_count=1)
    recipe_record = container.repositories.recipes.create(dataset.id, recipe)
    run = container.repositories.runs.create(
        dataset_id=dataset.id,
        recipe_id=recipe_record.id,
        target_count=recipe.target_count,
        candidate_budget=recipe.candidate_budget,
        dataset_fingerprint=dataset.fingerprint,
        recipe_fingerprint=recipe_record.fingerprint,
    )
    container.repositories.runs.transition(run.id, RunStatus.running)
    container.repositories.runs.transition(run.id, RunStatus.completed)
    client = TestClient(create_app(container))

    response = client.post(
        f"/api/v1/runs/{run.id}/exports",
        json={"project_id": project.id, "formats": ["canonical_jsonl"]},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "export_run_has_no_accepted_examples"
    assert response.json()["errors"][0]["loc"] == ["path", "run_id"]


def test_problem_response_has_request_id(tmp_path: Path) -> None:
    client = TestClient(create_app(make_container(tmp_path)))

    response = client.get("/api/v1/projects/missing/datasets")

    assert response.status_code == 404
    assert response.headers["x-request-id"] == response.json()["request_id"]
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "record_not_found"


def test_built_frontend_and_spa_fallback_are_served(tmp_path: Path) -> None:
    frontend_dist = tmp_path / "frontend-dist"
    assets = frontend_dist / "assets"
    assets.mkdir(parents=True)
    (frontend_dist / "index.html").write_text(
        "<html><body>Dataset Foundry Workbench</body></html>",
        encoding="utf-8",
    )
    (assets / "app.css").write_text("body { color: black; }", encoding="utf-8")
    client = TestClient(create_app(make_container(tmp_path / "data", frontend_dist=frontend_dist)))

    root = client.get("/")
    nested = client.get("/runs/example")
    asset = client.get("/assets/app.css")

    assert root.status_code == 200
    assert "Dataset Foundry Workbench" in root.text
    assert nested.status_code == 200
    assert "Dataset Foundry Workbench" in nested.text
    assert asset.status_code == 200
    assert "color: black" in asset.text


def test_api_key_protects_data_and_metrics_but_not_the_spa(tmp_path: Path) -> None:
    frontend_dist = tmp_path / "frontend-dist"
    assets = frontend_dist / "assets"
    assets.mkdir(parents=True)
    (frontend_dist / "index.html").write_text(
        "<html><body>Authenticated Dataset Foundry</body></html>",
        encoding="utf-8",
    )
    (assets / "app.css").write_text("body { color: navy; }", encoding="utf-8")
    api_key = "unit-test-api-key"
    container = Container(
        Settings(
            environment="test",
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'keyed.sqlite3'}",
            artifact_dir=tmp_path / "artifacts",
            frontend_dist=frontend_dist,
            api_key=api_key,
            _env_file=None,
        )
    )
    client = TestClient(create_app(container))

    assert client.get("/").status_code == 200
    assert client.get("/runs/example").status_code == 200
    assert client.get("/assets/app.css").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.get("/api/v1/projects").status_code == 401
    assert client.get("/api/v1/system/status").status_code == 401
    assert client.get("/metrics").status_code == 401

    headers = {"X-API-Key": api_key}
    assert client.get("/api/v1/projects", headers=headers).status_code == 200
    assert client.get("/api/v1/system/status", headers=headers).status_code == 200
    assert client.get("/metrics", headers=headers).status_code == 200
