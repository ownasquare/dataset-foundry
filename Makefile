.PHONY: install install-frontend setup quickstart stop reset-demo demo serve worker test test-unit test-integration lint format typecheck security frontend-build build frontend-check check benchmark-ci benchmark-durable e2e clean

install:
	uv sync --frozen

install-frontend:
	npm --prefix frontend ci

setup: install install-frontend frontend-build

quickstart:
	docker compose up --build --wait
	@echo "Dataset Foundry is ready at http://127.0.0.1:8765"

stop:
	docker compose down

reset-demo:
	docker compose down --volumes

demo:
	uv run dataset-foundry demo

serve:
	uv run dataset-foundry serve

worker:
	uv run dataset-foundry worker

test:
	uv run pytest -m "not live" --cov=dataset_foundry --cov-report=term-missing

test-unit:
	uv run pytest tests/unit -q

test-integration:
	uv run pytest tests/integration tests/contract -q

lint:
	uv run ruff check src tests scripts examples
	uv run ruff format --check src tests scripts examples

format:
	uv run ruff check --fix src tests scripts examples
	uv run ruff format src tests scripts examples

typecheck:
	uv run mypy src

security:
	uv run bandit -q -r src
	uv run pip-audit

frontend-build:
	npm --prefix frontend run build

build: frontend-build
	uv build

frontend-check: frontend-build
	npm --prefix frontend run typecheck
	npm --prefix frontend run test:component

check: lint typecheck test build frontend-check

benchmark-ci:
	uv run python scripts/benchmark_scale.py --count 250

benchmark-durable:
	uv run python scripts/benchmark_durable.py --count 250

e2e:
	npm --prefix frontend run test:e2e

clean:
	rm -rf build dist htmlcov frontend/dist frontend/coverage frontend/playwright-report frontend/test-results
