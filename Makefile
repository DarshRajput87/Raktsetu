# RaktSetu task runner. On Windows without `make`, use the same names with
# `npm run <name>` from the repository root (see package.json).

ifeq ($(OS),Windows_NT)
PY := backend/.venv/Scripts/python
else
PY := backend/.venv/bin/python
endif

.PHONY: backend-dev frontend-dev test seed

backend-dev:
	cd backend && ../$(PY) -m uvicorn api.main:app --reload

frontend-dev:
	cd frontend && npm run dev

test:
	cd backend && ../$(PY) -m pytest -q

seed:
	cd backend && ../$(PY) -m db.seed --reset
