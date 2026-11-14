# RaktSetu task runner. On Windows without `make`, use the same names with
# `npm run <name>` from the repository root (see package.json).

ifeq ($(OS),Windows_NT)
PY := backend/.venv/Scripts/python
else
PY := backend/.venv/bin/python
endif

.PHONY: backend-dev frontend-dev test test-backend test-e2e bench simulate seed

backend-dev:
	cd backend && ../$(PY) -m uvicorn api.main:app --reload

frontend-dev:
	cd frontend && npm run dev

# Everything: backend unit, API and scenario tests, then the browser tests.
# Needs MongoDB running. Uses its own databases (raktsetu_test, raktsetu_e2e).
test: test-backend test-e2e

test-backend:
	cd backend && ../$(PY) -m pytest -q

test-e2e:
	cd frontend && npx playwright test

bench:
	cd backend && ../$(PY) -m benchmarks.bench_core

simulate:
	cd backend && ../$(PY) -m simulation.simulator --days 90 --runs 10

seed:
	cd backend && ../$(PY) -m db.seed --reset
