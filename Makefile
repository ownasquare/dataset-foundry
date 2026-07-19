.PHONY: install install-frontend demo serve worker test test-unit test-integration lint format typecheck security build frontend-check check benchmark-ci benchmark-durable e2e clean

install:
	uv sync --frozen

install-frontend:
	npm --prefix frontend ci

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
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts

format:
	uv run ruff check --fix src tests scripts
	uv run ruff format src tests scripts

typecheck:
	uv run mypy src

security:
	uv run bandit -q -r src
	uv run pip-audit

build:
	uv build

frontend-check:
	npm --prefix frontend run typecheck
	npm --prefix frontend run build
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
