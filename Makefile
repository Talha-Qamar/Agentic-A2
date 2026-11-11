.PHONY: setup data index stack api web test test-unit test-integration test-e2e eval eval-smoke lint up down

setup:            ## install Python + web deps
	pip install -r requirements-eval.txt && cd apps/web && npm ci
data:             ## regenerate synthetic corpora/dev set (market stats need the Kaggle CSV: see docs/DATA_CARD.md)
	python data/generator/build_personas.py && python data/generator/build_jobs.py
index:            ## pre-build portfolio indexes for the configured retrieval variant
	python -m rag.warm
stack:            ## GigSim + MCP servers locally
	python scripts/run_stack.py
api:
	uvicorn apps.api.main:app --port 8000 --reload
web:
	cd apps/web && npm run dev
lint:
	ruff check .
test-unit:
	GIGBID_PROFILE=stub GIGBID_EMBEDDER=hash GIGBID_RERANKER=overlap pytest -q -m "not integration"
test-integration:
	GIGBID_PROFILE=stub GIGBID_EMBEDDER=hash GIGBID_RERANKER=overlap pytest -q -m integration
test-e2e:
	cd apps/web && npm run build && npx playwright test
test: lint test-unit test-integration test-e2e
eval-smoke:       ## 30-job smoke eval (CI gate)
	python -m evals.runners.decision_eval --limit 10 --out smoke_eval.json --gate
eval:             ## full experiment suite (see evals/README.md)
	python -m evals.runners.rag_eval --variants all && python -m evals.runners.decision_eval --limit 50
up:
	docker compose up --build
down:
	docker compose down
