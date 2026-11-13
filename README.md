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

## Real roads: every Gujarat city

The synthetic grid is for development. The real system covers the seven Gujarat cities in
`backend/data/cities.json` (Ahmedabad including Gandhinagar, Surat, Vadodara, Rajkot,
Bhavnagar, Jamnagar, Junagadh), each with a 25 km margin, on real OpenStreetMap roads.

The public Overpass servers are often overloaded, so the import reads a regional extract
from Geofabrik instead (about 210 MB, covers Gujarat):

```
cd backend
pip install -r data/requirements-data.txt
curl -L -o data/downloads/western-zone.osm.pbf https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf
python -m data.import_cities --all --pbf data/downloads/western-zone.osm.pbf
```

This takes about 6 minutes and replaces the synthetic grid in MongoDB. The road graphs are
cached in `data/downloads/<city>.graphml`, so later runs (for example with a new `--seed`)
are offline. One city: `--city surat`. Back to the synthetic grid: `python -m db.seed --reset`.

Demo accounts for real cities carry the city in the address, for example
`ahmedabad.b001@bank.raktsetu.test` and `surat.h001@hospital.raktsetu.test`
(password `raktsetu123`).

## Data

Road data is © OpenStreetMap contributors (ODbL).
All names are made up and all phone numbers use the invalid prefix `+91-00000`.
