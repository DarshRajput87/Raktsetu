# RaktSetu – Phase-wise Development Prompts

Use these prompts one phase at a time with an AI coding assistant (Claude Code, Cursor, Copilot Chat, etc.).

**How to use this file**
1. Paste the **Project Context** block at the start of every new chat or session.
2. Paste one phase prompt at a time, in order. Don't move on until that phase's acceptance criteria pass.
3. After each phase, commit to Git: `git commit -m "Phase N: <name>"`.
4. If the assistant drifts from the rules (e.g., uses `heapq` or `networkx` in core code), point it back to the **Project Rules**.

---

## Data workflow (already built)

The fake data is already built by three scripts in `backend/data/`. Phases 2 and 2.5 load what they produce. Region: **Gujarat**, starting with **Ahmedabad**.

### The three scripts

| Script | What it does | Needs internet | Output folder |
|---|---|---|---|
| `generate_data.py` | Builds a **fake city**: a 60 × 60 km grid of road junctions centred on Ahmedabad, plus fake blood banks, hospitals, donors and stock placed on it | No | `output/` |
| `generate_real_data.py` | Downloads the **real road map** of a city from OpenStreetMap (city + 25 km margin), then places fake blood banks, hospitals, donors and stock on **real road junctions with real lat/lng** | Yes, first run only (then cached) | `output_real/` |
| `demo_search.py` | Runs one search on either dataset: nearest bank within 25 km by Dijkstra, the route, or the donor fallback. Used to check that the data works. | No | Prints results |

### Step-by-step process

**Step 1 – Develop with the fake city (offline)**
```
cd backend/data
python generate_data.py --as-of 2026-11-13          # seed 42 by default
python demo_search.py --group B+ --component red_cells
```
Use this while building Phases 0–3: it is small, works offline and always gives the same data for the same `--seed`.

**Step 2 – Download a real city's roads (on your own computer)**
```
pip install osmnx
python generate_real_data.py                                    # Ahmedabad (+25 km, includes Gandhinagar)
python generate_real_data.py --place "Surat, Gujarat, India" --city-id surat
```
What happens inside:
1. Finds the city boundary on OpenStreetMap and expands it by 25 km on every side.
2. Downloads the drivable roads in that area (OSMnx, `network_type="drive"`) and keeps the largest connected part.
3. Saves the download to `downloads/<city_id>.graphml`, so later runs work offline.
4. Converts it to our format: every junction keeps its real lat/lng; road length comes from OpenStreetMap; one-way streets stay one-way; travel time uses a typical speed per road type.
5. Places 40 blood banks and 60 hospitals on real junctions, mostly near the centre and on main roads.
6. Places 5,000 donors on real junctions, spread more widely, each linked to its nearest bank by road distance.
7. Creates stock for every bank with collection and expiry dates; about 15% of banks are nearly empty so the donor fallback can be tested.
8. Writes one JSON file per collection to `output_real/`, every document tagged with `city_id`.

**Step 3 – Regenerate from the cached roads (offline)**
```
python generate_real_data.py --graphml downloads/ahmedabad.graphml --seed 7
```

**Step 4 – Check the data**
```
python demo_search.py --data output_real --group B+ --component red_cells
python demo_search.py --data output_real --group O- --component platelets --lat <outskirts lat> --lng <outskirts lng>
```
Expect: banks found near the centre with a route; a rare group on the outskirts falls back to donors.

**Step 5 – Load into MongoDB**
```
python generate_data.py --mongo-uri mongodb://localhost:27017                 # fake city
python generate_real_data.py --mongo-uri mongodb://localhost:27017            # one real city
```
The real-roads loader replaces only that city's documents (`city_id`), so cities can be added one at a time. (Phase 2 also builds `db/seed.py`, which loads either folder.)

### Main options

| Option | Script | Default | Meaning |
|---|---|---|---|
| `--seed` | both | 42 | Same seed = same data every time |
| `--as-of` | both | today | The "today" used for expiry and donation gaps |
| `--banks` / `--hospitals` / `--donors` | both | 30/40/3,000 (fake), 40/60/5,000 (real) | How many places to create |
| `--units-per-bank` | both | 120 | Average stock per bank |
| `--empty-bank-share` | both | 0.15 | Share of banks that are nearly empty |
| `--center-lat`, `--center-lng`, `--size-km` | fake | Ahmedabad, 60 km | Where and how big the fake city is |
| `--place`, `--city-id`, `--margin-km` | real | Ahmedabad, `ahmedabad`, 25 | Which city to download and the margin around it |
| `--graphml` | real | – | Use a saved road file instead of downloading |
| `--mongo-uri`, `--db` | both | – , `raktsetu` | Also insert into MongoDB |

### Safety and licence
- Only the roads and coordinates are real. Names are made up; phone numbers use the invalid prefix `+91-00000`, so no real person can be contacted.
- Road data is © OpenStreetMap contributors (ODbL). The map in the app must show this attribution.
- `downloads/` and `output_real/` are large: add them to `.gitignore`.

---

## Project Context (paste this first, every time)

```
You are helping me build "RaktSetu", an M.Tech project: a blood bank network that finds
the nearest blood bank with compatible stock using shortest-path search, and falls back
to showing matching donors when no bank has stock.

TECH STACK
- Backend: Python 3.11+, FastAPI, Motor (async MongoDB driver), Pydantic v2, pytest
- Database: MongoDB (local or Atlas)
- Frontend: Next.js 14+ (App Router, TypeScript), Tailwind CSS, React-Leaflet (OpenStreetMap)
- Core data structures: written by us in pure Python (no libraries)

USER ROLES
- Public user: search blood by group + component + location; view banks, route, donors
- Hospital: same search + raise requests with units, component, patient condition (urgency)
- Donor: register, link to a blood bank, set availability
- Blood bank admin: manage stock, record donations, issue units, accept requests, undo
- System admin: verify hospitals and banks, handle misuse reports

CORE FLOW (Case 1 and 2)
1. Get blood group, component and the user's location (GPS / map pin).
2. Hash map lookup -> all compatible donor blood groups.
3. Snap location to the nearest road junction; run Dijkstra on the road graph,
   stopping at 25 km of road distance.
4. Banks reached that hold AVAILABLE, NON-EXPIRED units of a compatible group and the
   requested component -> list nearest first, draw route to the nearest one.
5. No bank found -> list donors within 25 km who are compatible, eligible, available
   and gave contact consent, nearest first, with phone number (login required to view).
6. Hospital requests go through a max-heap priority queue (urgency from patient
   condition + aging) before running the same search; units can come from several banks.
7. Banks issue the unit closest to expiry first (min-heap, FEFO).

DATA (already generated, one JSON file per collection)
- backend/data/generate_data.py      -> data/output/       fake grid city centred on Ahmedabad
- backend/data/generate_real_data.py -> data/output_real/  real OpenStreetMap roads of one city
  (city + 25 km margin) with fake banks, hospitals, donors and stock on real junctions;
  every document also has city_id, and road_edges has oneway (true = only from -> to)
- backend/data/demo_search.py        reference search (uses heapq; ours must not)
- road_nodes:  {_id, lat, lng, city_id?}
- road_edges:  {_id, from, to, distance_km, road_type, travel_time_min, oneway?, city_id?}
- blood_banks: {_id, name, area, node_id, lat, lng, phone, verified, admin_user_id, city_id?}
- hospitals:   {_id, name, area, node_id, lat, lng, phone, verified, city_id?}
- donors:      {_id, name, age, gender, blood_group, phone, node_id, lat, lng,
                linked_bank_id, last_donation_date, health_checklist{...}, eligible,
                available, contact_consent, city_id?}
- blood_units: {_id, bank_id, blood_group, component, collected_on, expires_on, status}
  component in {whole_blood, red_cells, platelets, plasma}
  status in {available, reserved, issued, expired, transferred}
- meta.json:   {as_of, seed, center, counts, size_km (fake) | city_id, place, margin_km (real)}

REAL ROAD NETWORK (Phase 2.5)
- The synthetic grid roads are for development only. The final system uses real
  OpenStreetMap roads, imported per city (the city area plus a 25 km margin).
- road_nodes / road_edges carry a city_id; a search loads only the road graph of the
  city the request comes from into our own Graph, kept in an LRU cache of cities.
- OSM data is (c) OpenStreetMap contributors, ODbL: the map must show this attribution.

PROJECT RULES
1. backend/core/ must NOT use heapq, networkx, collections.deque, sortedcontainers or any
   graph/heap library. We implement MinHeap, MaxHeap, Graph, Dijkstra, Queue, LinkedList,
   Stack ourselves. Python dict is our hash map (allowed).
2. MongoDB only stores data. Do NOT use $near, $geoNear or Mongo sorting for search logic.
   All search, ranking and prioritisation runs through our core DSA in memory.
3. On startup the backend loads MongoDB data into in-memory structures; every change is
   applied in memory first and then written back to MongoDB.
4. Every core class and module has pytest tests. Keep functions small and typed.
5. Never put real phone numbers in seed data; fake numbers use the prefix +91-00000.
6. Explain the time complexity of each core operation in its docstring.
```

---

## Phase 0 – Project setup

```
PHASE 0: Set up the RaktSetu repository.

Create this structure:
raktsetu/
├── backend/
│   ├── core/            # our DSA (empty for now, with __init__.py)
│   ├── modules/         # domain logic
│   ├── db/              # MongoDB connection, loaders, repositories
│   ├── api/             # FastAPI app and routers
│   ├── data/            # generate_data.py, generate_real_data.py, demo_search.py (I will copy
│   │                    # these in) + requirements-data.txt: osmnx (data import only, not the API)
│   ├── simulation/
│   ├── tests/
│   ├── requirements.txt # fastapi, uvicorn[standard], motor, pymongo, pydantic, pydantic-settings,
│   │                    # python-jose[cryptography], pytest, pytest-asyncio, httpx
│   └── .env.example     # MONGO_URI, DB_NAME, JWT_SECRET, SEARCH_RADIUS_KM=25, AS_OF_DATE
├── frontend/            # Next.js 14 app (TypeScript, Tailwind, App Router, ESLint)
├── docker-compose.yml   # MongoDB 7 service with a named volume
├── .gitignore           # Python, Node, .env, data/output, data/output_real, data/downloads
└── README.md            # how to run backend, frontend and MongoDB locally

Also create:
- backend/api/main.py with a FastAPI app and GET /health returning {"status": "ok"}
- backend/config.py using pydantic-settings to read .env
- A Makefile or npm scripts with: backend-dev, frontend-dev, test, seed

Acceptance criteria:
- `docker compose up -d` starts MongoDB
- `uvicorn api.main:app --reload` (from backend/) serves /health
- `npm run dev` (from frontend/) shows the Next.js start page
- `pytest` runs (0 tests is fine)
```

---

## Phase 1 – Core data structures (the heart of the project)

```
PHASE 1: Implement our own data structures in backend/core/. No heapq, no networkx,
no deque. Pure Python. Each class has docstrings with time complexity and full pytest tests.

1. heap.py
   - class MinHeap: array-based binary heap storing (key, item) pairs.
     push(key, item), pop() -> (key, item), peek(), __len__, is_empty(),
     heapify(list_of_pairs) in O(n). Ties broken by insertion order (stable) using a counter.
   - class MaxHeap: same API, largest key first (implement directly, not by negating
     only in callers; negating internally is fine).
   - Raise IndexError on pop/peek from an empty heap.

2. queue.py
   - class Queue: FIFO using a singly linked list with head and tail pointers.
     enqueue, dequeue, peek, __len__, is_empty. All O(1).

3. stack.py
   - class Stack: push, pop, peek, __len__, is_empty. O(1).

4. linked_list.py
   - class LinkedList: append-only log with head/tail. append(item) O(1),
     __iter__ in insertion order, __len__, to_list(), last(n) returning the latest n items.

5. graph.py
   - class Graph: undirected weighted graph, adjacency list as dict[node_id, list[(neighbor, weight)]].
     add_node, add_edge(u, v, w), neighbors(u), node_count, edge_count.
   - dijkstra(graph, source, max_distance=None) -> (dist: dict, prev: dict)
     using OUR MinHeap with lazy deletion (skip stale entries).
     If max_distance is set, never relax beyond it and stop when the popped distance exceeds it.
   - dijkstra_until(graph, source, is_target, max_distance) -> generator yielding
     (node, distance) in increasing distance order for nodes where is_target(node) is True
     (lets the caller stop at the first k targets).
   - build_path(prev, source, target) -> list of node ids, built with OUR Stack.
     Return [] if target is unreachable.

6. tests/core/: tests for every class, including:
   - heap: random push/pop against sorted() for 1,000 items; stability on equal keys
   - dijkstra: hand-made 6-node graph with known answers; cutoff respected; unreachable node;
     path reconstruction; matches a brute-force Bellman-Ford on 50 random small graphs
   - queue/stack/linked list: order, empty errors, lengths

Acceptance criteria:
- `pytest tests/core -q` passes
- `grep -rE "heapq|networkx|deque" backend/core` returns nothing
```

---

## Phase 2 – Database and data loading

```
PHASE 2: Connect MongoDB, seed it with the generated data, and load it into memory.

1. db/mongo.py: async Motor client created on FastAPI startup (lifespan), closed on shutdown.
   get_db() dependency.

2. db/seed.py (CLI: `python -m db.seed --source output` or `--source output_real`):
   - Read every JSON file from data/<source>/ and insert into the matching collection
     (drop first when --reset is passed; for output_real, replace only that city_id).
   - Convert ISO date strings (collected_on, expires_on, last_donation_date) to datetime.
   - Create indexes: blood_units(bank_id, blood_group, component, status),
     donors(blood_group), donors(node_id), road_edges(from), road_edges(to).
   - Also create the collections that start empty: users, requests, transactions,
     contact_access_logs, misuse_reports.

3. db/repositories.py: small async functions for each collection
   (get_bank, list_banks, insert_unit, update_unit_status, get_donor, update_donor,
   insert_request, update_request, insert_transaction, insert_access_log, ...).
   No search logic here: only reads and writes.

4. modules/state.py: class AppState built at startup:
   - graph: core.Graph from road_nodes + road_edges
   - node_coords: dict[node_id, (lat, lng)]
   - banks_by_id, banks_by_node: dicts
   - hospitals_by_id
   - donors_by_id: dict; donors_by_group: dict[group, list[donor_id]]
   - inventory: built in Phase 3 (leave a placeholder)
   Store it on app.state and expose a get_state() dependency.

5. modules/geo.py: haversine_km and nearest_node(lat, lng) that snaps a location to the
   closest road junction. Use a simple uniform grid bucket index (dict of cell -> node ids)
   built at startup so lookups don't scan all nodes. Document the complexity.

Acceptance criteria:
- `python -m db.seed --reset` loads all collections; counts match data/output/meta.json
- On API startup the log prints node, edge, bank, donor and unit counts
- Unit tests for geo.nearest_node and for AppState building from a tiny fixture dataset
```

---

## Phase 2.5 – Real road network per city (OpenStreetMap)

Do this after Phase 2 works with the synthetic grid. The launch region is **Gujarat**: start with Ahmedabad, then add the other Gujarat cities.

```
PHASE 2.5: Replace the synthetic grid roads with real OpenStreetMap roads, imported per
city. A search loads only the road graph of the city the request comes from.

WHY PER CITY: all of India's roads are tens of millions of junctions, too large to hold
in memory. A search only needs roads within 25 km of the user, and almost every request
comes from inside one city, so we keep one road graph per city.

1. cities collection + config
   - cities: {_id: "ahmedabad", name: "Ahmedabad", state: "Gujarat", center: [lat, lng],
     bbox: [south, west, north, east], margin_km: 25, imported_at, node_count, edge_count}
   - The bbox is the city boundary's bounding box EXPANDED by margin_km (25 km) on every
     side, so a user near the city border still finds banks just outside it.
   - Launch region: Gujarat. data/cities.json lists the supported cities, in this order:
     Ahmedabad (first), Surat, Vadodara, Rajkot, Bhavnagar, Jamnagar, Junagadh.
     Gandhinagar is about 25 km from Ahmedabad, so it falls inside Ahmedabad's 25 km margin:
     treat it as part of the Ahmedabad entry (state this in the city's notes) instead of a
     separate import. Other states are added later with the same command.

2. Importing cities – REUSE data/generate_real_data.py (already built and tested; see
   "Data workflow"). It already downloads the city + 25 km margin with OSMnx, keeps the
   largest connected part, caches downloads/<city_id>.graphml, converts junctions and roads
   (real lat/lng, OSM length, one-way kept, travel time by road type), places fake banks,
   hospitals, donors and stock on real junctions, and inserts by city_id into MongoDB.
   Build only what is missing:
   - data/cities.json and a cities collection (fields above), written after each import
     with imported_at, node_count, edge_count and the expanded bbox.
   - data/import_cities.py:
       python -m data.import_cities --city ahmedabad
       python -m data.import_cities --all      # every city in cities.json (all of Gujarat)
     For each city, call generate_real_data's functions (download_graph / load_graph,
     convert_graph, the place builders) with that city's place, city_id and margin.
     Run ahead of time, never during a user request. Print counts and time per city.
   - A --roads-only flag: import roads without fake places (for when real bank data is used).
   - Indexes: road_nodes(city_id), road_edges(city_id, from), blood_banks(city_id),
     donors(city_id, blood_group).

3. Update core/graph.py: support directed edges (add_edge(u, v, w, directed=False)) so
   one-way roads are respected. Add tests.

4. modules/cities.py – pick and load the city for each request:
   - city_for_location(lat, lng) -> city_id: the supported city whose expanded bbox
     contains the point (if several, the one whose center is nearest by haversine).
     The search form also sends the city the user picked; use the location to confirm it.
   - No supported city -> return a clear error: "RaktSetu is not available in this area yet".
   - CityGraphCache: an LRU cache of loaded city graphs, implemented by us with a hash map
     + doubly linked list (O(1) get/put). Capacity from .env (e.g. 5 cities). On a miss,
     load that city's nodes and edges from MongoDB into a core.Graph and a grid index for
     nearest_node. Preload the most-used cities at startup.

5. Snap places to the real roads:
   - Fake places from generate_real_data.py already sit on real junctions (node_id set).
   - data/snap_places.py: for places added later with only lat/lng (a new bank, a donor
     registering through the app, real bank data), set city_id and node_id to the nearest
     real road junction of their city (haversine + the grid index). The API's register
     endpoints call the same function.
   - Optional: import real blood bank names and coordinates from the public blood bank
     directory on data.gov.in where coordinates are available (--roads-only import, then
     snap_places), and keep the stock synthetic.

6. Search changes (modules/search.py):
   - city_id = city_for_location(lat, lng); graph = CityGraphCache.get(city_id);
     then the same nearest_node + Dijkstra with the 25 km cutoff. Only banks and donors
     of that city are considered. Nothing else in the search logic changes.

Acceptance criteria:
- `python -m data.import_cities --city ahmedabad` imports Ahmedabad (+25 km margin, which
  includes Gandhinagar) and prints counts; `--all` imports every Gujarat city in cities.json.
- `python demo_search.py --data output_real ...` and our own search agree: banks found near
  the centre with a route; a rare group on the outskirts falls back to donors.
- A search from Gandhinagar is served by the Ahmedabad graph.
- A route returned by /route, drawn on the map, follows real streets.
- A search near the city border finds a bank just outside the city boundary (margin works).
- The first search in a city loads its graph from MongoDB; repeat searches do no database
  reads for roads (log cache hits). A location outside every supported city returns the
  "not available yet" error.
- The LRU cache has unit tests (eviction order, O(1) operations).
- The map shows "(c) OpenStreetMap contributors".
```

---

## Phase 3 – Domain modules (business logic)

```
PHASE 3: Build the domain modules in backend/modules/ using ONLY our core DSA.
Each module has unit tests that run without MongoDB (use in-memory fixtures).

1. compatibility.py
   - COMPATIBLE: dict recipient_group -> ordered list of donor groups
     (exact match first, then others; O- last). Same table for whole_blood and red_cells.
   - For plasma use the reverse (plasma) compatibility table; for platelets use the
     red-cell table (document this simplification).
   - compatible_groups(group, component) -> list[str]

2. inventory.py – expiry-aware stock (FEFO)
   - class Inventory: dict[(bank_id, group, component)] -> MinHeap keyed by expires_on.
   - add_unit(unit), issue(bank_id, groups, component, count) -> list of issued units,
     always the soonest-to-expire first, trying groups in the given order.
   - count_available(bank_id, groups, component, today) -> int
   - purge_expired(today) -> list of expired units (pop while top is expired).
   - expiring_within(bank_id, days, today) for the bank dashboard.
   - Only 'available' units live in the heaps; reserved/issued/expired are removed.

3. search.py – Case 1
   - search_blood(state, lat, lng, group, component, radius_km=25, today) -> SearchResult:
       start_node = nearest_node(lat, lng)
       groups = compatible_groups(group, component)
       walk dijkstra_until(graph, start_node, is_bank_node, radius_km)
       keep banks with count_available > 0
       if any: return banks (distance_km, est_travel_min, units per group) nearest first,
               plus the route (list of [lat, lng]) to the nearest bank via build_path
       else:   return donors from donors_by_group[g] for g in groups, filtered by
               eligible + available + contact_consent + reachable within radius,
               sorted by road distance (use our MinHeap), WITHOUT phone numbers
               (phone is fetched separately via the contact endpoint)
   - route_to_bank(state, lat, lng, bank_id) -> route + distance

4. eligibility.py
   - is_eligible(donor, today): age 18–65, no health flags, gap since last donation
     >= 90 days (M) / 120 days (F). Used at registration and on every donation.

5. requests.py – Case 2
   - URGENCY: dict patient_condition -> base score
     (accident 100, delivery_complication 100, dengue_low_platelets 80, thalassemia 75,
      cancer_treatment 65, planned_surgery 40, other 20).
   - class RequestQueue: our MaxHeap keyed on effective priority
     = base_score + AGING_PER_MINUTE * minutes_waited. Re-key waiting requests on a timer
     (rebuild the heap with heapify) and document why.
   - fulfil(request): run the search; take units from the nearest banks first (greedy)
     until units_needed is met; reserve them in Inventory; return the allocation per bank
     or a partial result + donor fallback list.

6. donors.py – Case 3
   - register(donor_input) -> donor with eligibility computed and linked_bank_id set
     (chosen bank, or nearest bank by Dijkstra if none chosen).
   - set_availability, record_donation(donor_id, bank_id, component) -> creates a unit,
     updates last_donation_date, recomputes eligibility.

7. audit.py
   - Per-bank transaction log using our LinkedList (added, issued, expired, transferred).
   - Per-admin undo using our Stack of inverse actions (command pattern):
     add_unit <-> remove_unit, issue <-> return to inventory.

Acceptance criteria:
- Tests reproduce the three demo cases from data/demo_search.py on the generated data:
  B+ red_cells at city centre (23.0225, 72.5714) -> banks found;
  AB- platelets at (23.2021, 72.7706) -> one far bank (19.93 km);
  O- platelets at (22.8021, 72.3275) -> donor fallback.
  (Synthetic grid centred on Ahmedabad, seed 42, as-of 2026-11-13.)
- Inventory always issues the earliest-expiring unit (property test with random units).
- RequestQueue serves 'accident' before 'planned_surgery', and an old 'other' request
  eventually overtakes new medium ones (aging test).
```

---

## Phase 4 – Authentication, roles and donor privacy

```
PHASE 4: Add authentication, roles and the donor-contact safeguards.

1. OTP login (api/routers/auth.py)
   - POST /auth/otp/send {phone}: generate a 6-digit OTP, store hashed with 5-minute expiry.
     In development mode, return the OTP in the response / log it (no SMS provider yet).
     Put SMS sending behind an interface so a provider can be plugged in later.
   - POST /auth/otp/verify {phone, otp}: create the user if new (role=public),
     return a JWT (role, user_id, expiry).
   - Separate login for hospital and bank_admin accounts (email + password with bcrypt is fine),
     only allowed if verified=true.

2. api/deps.py: get_current_user, require_role(*roles) dependencies.

3. Donor contact safeguards
   - GET /donors/{id}/contact requires login.
   - Only donors with contact_consent=true and available=true return a phone.
   - Rate limit: max 20 contact views per user per day (store counts in MongoDB or memory
     with a daily reset). Return 429 with a clear message when exceeded.
   - Write a contact_access_logs entry for every view: viewer, donor, timestamp.
   - POST /donors/{id}/report creates a misuse_reports entry.

4. Tests for: OTP expiry, wrong OTP, role guard, rate limit, access log written.

Acceptance criteria:
- Public search works without login; donor phone numbers never appear in /search responses.
- Contact endpoint returns 401 without a token, 429 after the limit, and logs each view.
```

---

## Phase 5 – REST API

```
PHASE 5: Expose the modules through FastAPI routers with Pydantic request/response models.
Group routers by role. All endpoints documented in the auto-generated /docs.

Public
- GET  /search?group=&component=&lat=&lng=&radius=25
- GET  /search?...&trace=true          also returns the Dijkstra trace for the animation:
                                       [{node, lat, lng, dist_km, parent}] in visit order,
                                       plus the banks reached and the final route
- GET  /route?lat=&lng=&bank_id=
- GET  /banks, GET /banks/{id}
- GET  /donors/{id}/contact            (login required, Phase 4)

Hospital (role=hospital)
- POST /hospital/requests              {group, component, units_needed, patient_condition}
- GET  /hospital/requests              list with status
- GET  /hospital/requests/{id}

Donor (role=donor)
- POST  /donors/register
- PATCH /donors/me                     availability, details, linked bank
- GET   /donors/me/suggested-banks     nearest 5 banks by road distance
- POST  /donors/{id}/report

Blood bank admin (role=bank_admin, own bank only)
- GET   /bank/stock                    by group and component, expiring soon flagged
- POST  /bank/units                    add a unit (records a donation if donor_id given)
- POST  /bank/units/issue              {group, component, count} -> FEFO issue
- GET   /bank/requests                 requests assigned to this bank
- PATCH /bank/requests/{id}            accept / reject
- GET   /bank/transactions?limit=50    from the LinkedList log
- POST  /bank/undo

System admin (role=admin)
- PATCH /admin/hospitals/{id}/verify, PATCH /admin/banks/{id}/verify
- GET   /admin/reports

Also:
- A background task (FastAPI lifespan + asyncio loop) that runs purge_expired once a day
  and re-keys the request queue every minute.
- Consistent error format: {"error": {"code": "...", "message": "..."}}.
- CORS configured for the frontend origin from .env.

Acceptance criteria:
- httpx-based API tests for every endpoint's happy path and one failure case.
- /search responds in under 200 ms on the generated dataset (log the timing).
```

---

## Phase 6 – Frontend (Next.js)

```
PHASE 6: Build the Next.js frontend in frontend/ (App Router, TypeScript, Tailwind,
React-Leaflet). Clean white design, red (#B3202F) as the only accent colour.
Mobile-first: most users will search from a phone in an emergency.

Shared
- lib/api.ts: typed fetch wrapper with base URL from NEXT_PUBLIC_API_URL and JWT handling.
- components/Map.tsx: React-Leaflet map (load with next/dynamic, ssr:false) that shows
  the user, banks (markers), donors (different markers) and a route polyline.
- components/BankCard.tsx, DonorCard.tsx (Call and WhatsApp buttons), BloodGroupSelect,
  ComponentSelect, UrgencyBadge, EmptyState, LoadingSpinner.
- Auth context storing the JWT and role; OTP login modal.

Pages
1. / (Search, Case 1)
   - Blood group + component selects, "Use my location" (browser geolocation) or click on map.
   - Results: list of banks (distance, travel time, units, phone) nearest first + route
     to the nearest bank on the map.
   - No banks: banner "No blood bank within 25 km has stock" + donor cards. Tapping
     "Show number" opens OTP login if needed, then calls /donors/{id}/contact.
   - "Search wider" button that retries with radius 50.
   - All blood bank pins are shown on the map as soon as the page loads.
   - "Show how it works" button (Dijkstra animation, uses /search?trace=true):
       * user pin + a 25 km circle appear
       * visited junctions light up in visit order, spreading out like a wave
         (draw with Leaflet's canvas renderer, in batches of ~20 per frame, so the
         whole animation takes about 3-5 seconds)
       * each bank pin flashes when reached: green with its distance if it has stock,
         grey if not
       * when the search ends, the shortest route to the nearest bank with stock is
         drawn segment by segment and that bank is highlighted
       * speed slider and "Skip animation"; the normal search stays instant
2. /hospital (Case 2): login, request form (group, component, units, patient condition
   dropdown), list of requests with status and allocated banks.
3. /donor/register (Case 3): multi-step form (details -> health checklist -> consent ->
   choose bank from suggested nearest banks). Show eligibility result clearly.
4. /donor/me: availability toggle, donation history, linked bank.
5. /bank (Case 4): stock table by group x component with expiring-soon highlights,
   add unit form, issue form, incoming requests (accept/reject), recent transactions,
   Undo button.
6. /admin: verify hospitals/banks, view misuse reports.

Acceptance criteria:
- All three demo cases work end to end in the browser.
- Lighthouse mobile accessibility score >= 90 on the search page.
- No donor phone number is rendered without a successful /contact call.
```

---

## Phase 7 – Integration and testing

```
PHASE 7: Make the system reliable and prove the DSA performs.

1. End-to-end scenarios (pytest + httpx against a test MongoDB seeded with a fixed seed):
   - Public search finds banks; route returned.
   - Search on the outskirts falls back to donors; contact view is logged and rate-limited.
   - Hospital raises an 'accident' request and a 'planned_surgery' request; the accident
     is allocated first; units are reserved from the nearest banks, earliest expiry first.
   - Donor registers, is linked to the nearest bank, donates; their unit appears in stock
     and their eligibility turns false until the gap passes.
   - Bank admin issues a unit then undoes it; stock and log are correct.

2. benchmarks/bench_core.py:
   - Our MinHeap vs Python heapq: push/pop 100k items (report times).
   - Dijkstra with 25 km cutoff vs full Dijkstra: average time and nodes visited over
     200 random start points.
   - Search latency at graph sizes 30x30, 60x60, 100x100 km (regenerate data with
     --size-km). Save results as CSV + PNG charts (matplotlib) in benchmarks/results/.

3. Frontend: Playwright test for the search flow (banks found, donor fallback).

Acceptance criteria:
- All tests green in one command (`make test`).
- benchmarks/results/ contains the CSVs and charts for the report.
```

---

## Phase 8 – Simulation and evaluation (results chapter)

```
PHASE 8: Build a simulator that compares three methods on the same synthetic city and
produces the results for the M.Tech report.

simulation/simulator.py
- Discrete-event simulation over N days (default 90) using the generated city.
- Daily events: donations arrive at banks (new units), requests arrive (public + hospital,
  mixed patient conditions), units expire.
- Methods:
  1. Traditional: requests first-come-first-served; requester checks banks in random order
     (simulate phone calls, each call costs 3 minutes); bank issues a random available unit.
  2. RaktSetu: priority queue + aging; Dijkstra nearest bank with stock; FEFO issuing;
     donor fallback within 25 km.
  3. (Optional) RaktSetu + transfer suggestions: daily move of units expiring within
     2 days to the nearest bank that is short of that group.
- Metrics per method: wastage % (expired / total units), average and 90th-percentile time
  to locate blood, request fulfilment %, critical-request fulfilment %, average distance
  travelled, donor fallback rate.
- Fixed seeds; run each method 10 times and report mean ± std.
- Output: results CSV + charts (bar chart per metric, wastage over time line chart)
  in simulation/results/, and a markdown summary table.

Acceptance criteria:
- `python -m simulation.simulator --days 90 --runs 10` finishes in under 5 minutes.
- Summary table clearly shows each metric for every method.
```

---

## Phase 9 – Deployment and documentation

```
PHASE 9: Deploy and document.

1. Deployment
   - MongoDB Atlas free cluster; seed it with db.seed.
   - Backend on Render or Railway (Dockerfile for FastAPI with uvicorn, health check /health).
   - Frontend on Vercel with NEXT_PUBLIC_API_URL set.
   - Environment variables documented in README; no secrets in the repo.

2. Documentation
   - README: overview, architecture diagram (Mermaid), setup, seed, run, test, deploy.
   - docs/api.md: every endpoint with an example request and response.
   - docs/dsa.md: each data structure, where it is used, complexity table, and benchmark
     results from Phase 7.
   - docs/demo-script.md: a 5-minute demo walkthrough of the three cases for the viva.

Acceptance criteria:
- A public URL where the three demo cases work.
- A fresh clone can be run locally by following only the README.
```

---

## Phase 10 (Optional) – Machine learning add-on

Only after Phases 0–9 are done and working.

```
PHASE 10 (optional): Add ML on top of the working system without breaking it.

1. Extend data/generate_data.py with --with-ml-data:
   - contact_history.csv: per donor contact attempt -> distance_km, hour, days_since_last,
     num_donations, age, past_response_rate, responded (0/1) generated from a logistic rule.
   - weekly_demand.csv: 104 weeks x blood group x component with dengue-season and festival
     effects and Poisson noise.
2. ml/donor_response.py: logistic regression vs random forest (scikit-learn),
   metrics precision@10 and ROC-AUC; save the best model with joblib.
3. ml/shortage_forecast.py: linear regression with lag features vs random forest regressor,
   MAE and RMSE; weekly forecast per bank and group.
4. Integration: donor fallback sorted by a top-k heap on score = P(response) and distance;
   GET /bank/alerts returns predicted shortages. If a model file is missing, fall back to
   distance-only ordering and no alerts.
5. Add "RaktSetu + ML" as a method in the Phase 8 simulator.

Acceptance criteria:
- The system works identically when the model files are absent.
- The ML method appears in the simulation results with its metrics.
```

---

## Quick checklist

| Phase | Output | Done |
|---|---|---|
| 0 | Repo, MongoDB, empty FastAPI + Next.js running | ☐ |
| 1 | Own heap, queue, stack, linked list, graph, Dijkstra + tests | ☐ |
| 2 | MongoDB seeded, data loaded into memory | ☐ |
| 2.5 | Real OpenStreetMap roads per city (+25 km margin), city LRU cache | ☐ |
| 3 | Compatibility, inventory (FEFO), search, requests, donors, audit | ☐ |
| 4 | OTP login, roles, donor contact safeguards | ☐ |
| 5 | All REST endpoints | ☐ |
| 6 | Next.js pages for all roles | ☐ |
| 7 | E2E tests + DSA benchmarks | ☐ |
| 8 | Simulation results for the report | ☐ |
| 9 | Deployed + documented | ☐ |
| 10 | (Optional) ML add-on | ☐ |
