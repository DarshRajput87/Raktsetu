# RaktSetu

A blood bank network that finds the nearest blood bank with compatible stock using
shortest-path search on the road network, and falls back to matching donors when no
bank has stock. M.Tech project.

The core data structures (heaps, queue, stack, linked list, graph, Dijkstra, LRU cache)
are written by hand in `backend/core/`. MongoDB only stores data; every search and
ranking runs in memory through those structures.

## Layout

```
backend/
  core/         our data structures (no heapq / networkx / deque)
  modules/      domain logic (search, inventory, requests, donors, audit)
  db/           MongoDB connection, seed script, repositories
  api/          FastAPI app and routers
  data/         data generators and generated JSON
  simulation/   evaluation simulator
  tests/
frontend/       Next.js app (TypeScript, Tailwind, React-Leaflet)
```

## Requirements

- Python 3.11+
- Node.js 20+
- MongoDB 7+ (a local install, or Docker)

## Setup

### 1. MongoDB

With Docker:

```
docker compose up -d
```

Or use a locally installed MongoDB listening on `mongodb://localhost:27017`.

### 2. Backend

```
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # Windows   (Linux/macOS: cp .env.example .env)
```

Generate the development data and load it into MongoDB:

```
cd data
python generate_data.py --as-of 2026-11-13
cd ..
python -m db.seed --reset
```

Run the API:

```
uvicorn api.main:app --reload
```

- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs

### 3. Frontend

```
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Tasks

From the repository root, with `make` or with `npm run` (same names):

| Task | What it does |
|---|---|
| `backend-dev` | Run the API with reload |
| `frontend-dev` | Run the Next.js dev server |
| `test` | Run the backend tests |
| `seed` | Reset MongoDB and load `backend/data/output` |

## Data

Road data in `backend/data/output_real` is © OpenStreetMap contributors (ODbL).
All names are made up and all phone numbers use the invalid prefix `+91-00000`.
