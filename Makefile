.PHONY: install ingest query serve test lint e2e

install:
	uv sync --extra dev

ingest:
	uv run tm ingest --source local

query:
	uv run tm query "$(Q)"

serve:
	uv run uvicorn twin_mind.api.app:app --reload --port 8000

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

e2e:
	uv run tm eval --suite smoke
