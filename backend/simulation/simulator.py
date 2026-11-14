"""Phase 8: discrete-event simulation comparing how blood is found.

    python -m simulation.simulator                       # 90 days, 10 runs per method
    python -m simulation.simulator --days 30 --runs 3    # quicker
    python -m simulation.simulator --quick               # smoke test (5 days, 2 runs)

Three methods run on the same synthetic city and, within a run, on exactly the
same stream of donations and requests (common random numbers), so the
differences come from the method alone:

1. traditional        Requests are served first come, first served. The requester
                      phones banks from a directory in random order (3 minutes per
                      call, gives up after 10 calls); a bank hands out a random
                      compatible unit. No donor fallback.
2. raktsetu           Public searches run on arrival; hospital requests wait in our
                      RequestQueue (MaxHeap with aging) and are dispatched every
                      5 minutes, most urgent first. Nearest banks first by
                      Dijkstra (25 km), FEFO issuing from the Inventory heaps, and a
                      donor fallback within 25 km when banks cannot cover it.
3. raktsetu_transfer  RaktSetu, plus once a day every unit expiring within 2 days
                      is moved to the nearest bank (within 25 km) that is short of
                      that group and component.

Each run uses seed (base seed + run index). Results go to simulation/results/:
runs.csv (every run), summary.csv and summary.md (mean and std per method),
daily_wastage.csv, one bar chart per metric and a wastage-over-time line chart.

The simulation reuses the project's own Inventory, RequestQueue, Dijkstra,
compatibility table, eligibility rules and donor search (modules.search.find_donors).
"""

import argparse
import copy
import csv
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from core.graph import dijkstra
from core.heap import MinHeap
from modules.compatibility import SHELF_LIFE_DAYS, compatible_groups
from modules.requests import URGENCY, RequestQueue, base_score
from modules.search import find_donors
from modules.state import AppState, CityRoads

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"
RESULTS = Path(__file__).resolve().parent / "results"
CACHE = Path(__file__).resolve().parent / ".cache"
CITY_ID = "synthetic"
START = date(2026, 11, 13)
CITY_SEED = 42

METHODS = ["traditional", "raktsetu", "raktsetu_transfer"]
LABELS = {"traditional": "Traditional", "raktsetu": "RaktSetu", "raktsetu_transfer": "RaktSetu + transfers"}


@dataclass(frozen=True)
class Config:
    """Every assumption of the model in one place (also printed in summary.md)."""
    days: int = 90
    radius_km: float = 25.0
    donations_per_day: float = 105.0
    hospital_requests_per_day: float = 38.0
    public_requests_per_day: float = 24.0
    public_origins: int = 400           # neighbourhoods public requests come from
    call_min: float = 3.0               # one phone call, to a bank or a donor
    max_bank_calls: int = 10            # traditional: give up after this many calls
    app_search_min: float = 1.0         # RaktSetu: entering a search in the app
    dispatch_min: int = 5               # RaktSetu: hospital queue is served this often
    donor_response_prob: float = 0.35   # a contacted donor agrees and comes in
    max_donor_calls: int = 10
    transfer_within_days: int = 2       # transfers: units expiring this soon may move
    short_threshold: int = 2            # transfers: a bank is short below this many units
    critical_score: int = 80            # base urgency counted as critical


# Patient condition -> (share of hospital requests, components it needs with weights).
CONDITIONS: dict[str, tuple[float, dict[str, float]]] = {
    "accident": (0.15, {"whole_blood": 0.5, "red_cells": 0.4, "plasma": 0.1}),
    "delivery_complication": (0.10, {"red_cells": 0.5, "whole_blood": 0.3, "plasma": 0.2}),
    "dengue_low_platelets": (0.10, {"platelets": 1.0}),
    "thalassemia": (0.15, {"red_cells": 1.0}),
    "cancer_treatment": (0.15, {"platelets": 0.5, "red_cells": 0.5}),
    "planned_surgery": (0.25, {"red_cells": 0.6, "plasma": 0.25, "whole_blood": 0.15}),
    "other": (0.10, {"whole_blood": 0.3, "red_cells": 0.4, "plasma": 0.2, "platelets": 0.1}),
}
# Same mix as the data generator (approximate Indian distribution).
GROUP_MIX = {"O+": 0.32, "B+": 0.32, "A+": 0.22, "AB+": 0.075, "O-": 0.02, "B-": 0.02, "A-": 0.015, "AB-": 0.01}
DONATION_COMPONENTS = {"whole_blood": 0.30, "red_cells": 0.35, "platelets": 0.10, "plasma": 0.25}

# Event kinds, in the order they are handled when they share a minute.
DAY_START, DONATION, ARRIVAL, DISPATCH = 0, 1, 2, 3


# ---- the city ---------------------------------------------------------------

def synthetic_city() -> Path:
    """The standard synthetic city (seed 42, as of 2026-11-13), generated once into a cache
    so the simulation does not depend on whatever is in data/output."""
    out = CACHE / "grid_60km"
    if not (out / "meta.json").exists():
        subprocess.run([sys.executable, str(DATA / "generate_data.py"), "--seed", str(CITY_SEED),
                        "--as-of", START.isoformat(), "--out", str(out)], check=True, capture_output=True)
    return out


class World:
    """The read-only part shared by every run: documents, road graph and road distances.

    Distances are computed once per origin with our Dijkstra and cached: the road
    graph never changes during the simulation, so repeating the search for every
    request would give the same answer at a much higher cost.
    """

    def __init__(self, folder: Path, config: Config) -> None:
        self.config = config
        self.docs = {}
        for name in ["meta", "road_nodes", "road_edges", "blood_banks", "hospitals", "donors", "blood_units"]:
            with open(folder / f"{name}.json", encoding="utf-8") as f:
                self.docs[name] = json.load(f)
        nodes = self.docs["road_nodes"]
        lats, lngs = [n["lat"] for n in nodes], [n["lng"] for n in nodes]
        self.city = {"_id": CITY_ID, "name": "Synthetic", "center": self.docs["meta"]["center"],
                     "bbox": [min(lats), min(lngs), max(lats), max(lngs)]}
        self.roads = CityRoads(CITY_ID, nodes, self.docs["road_edges"])
        self.banks = [b for b in self.docs["blood_banks"] if b.get("verified", True)]
        self.hospitals = self.docs["hospitals"]
        origin_rng = random.Random(CITY_SEED)
        self.public_origins = [d["node_id"] for d in origin_rng.sample(self.docs["donors"], config.public_origins)]
        self._dist: dict[str, dict[str, float]] = {}
        self._near: dict[str, dict[str, float]] = {}
        self._banks: dict[str, list[tuple[str, float]]] = {}

    def distances(self, node: str) -> dict[str, float]:
        """Road km from a junction to every reachable junction (full Dijkstra, cached)."""
        if node not in self._dist:
            self._dist[node] = dijkstra(self.roads.graph, node)[0]
        return self._dist[node]

    def within_radius(self, node: str) -> dict[str, float]:
        """Junctions within the search radius, as the 25 km cutoff Dijkstra would settle them."""
        if node not in self._near:
            r = self.config.radius_km
            self._near[node] = {n: d for n, d in self.distances(node).items() if d <= r}
        return self._near[node]

    def banks_by_distance(self, node: str) -> list[tuple[str, float]]:
        """Every reachable bank as (bank_id, km), nearest first, ordered with our MinHeap."""
        if node not in self._banks:
            dist = self.distances(node)
            heap = MinHeap()
            for bank in self.banks:
                if bank["node_id"] in dist:
                    heap.push(dist[bank["node_id"]], bank["_id"])
            self._banks[node] = [(bank_id, d) for d, bank_id in (heap.pop() for _ in range(len(heap)))]
        return self._banks[node]

    def fresh_state(self) -> AppState:
        """A private, changeable copy of the city's banks, donors and stock."""
        docs = copy.deepcopy({k: self.docs[k] for k in ("blood_banks", "hospitals", "donors", "blood_units")})
        for collection in docs.values():
            for doc in collection:
                doc["city_id"] = CITY_ID
        return AppState.build(cities=[self.city], banks=docs["blood_banks"], hospitals=docs["hospitals"],
                              donors=docs["donors"], units=docs["blood_units"], roads=[self.roads])


# ---- the events -----------------------------------------------------------------

def poisson(rng: random.Random, mean: float) -> int:
    """Knuth's method; fine for the small daily means used here."""
    limit, k, p = math.exp(-mean), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def pick(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def generate_events(world: World, seed: int) -> tuple[list[dict], list[dict]]:
    """Donations and requests for every day, from one seed. Identical for every method."""
    cfg, rng = world.config, random.Random(seed)
    donations, requests = [], []
    condition_share = {c: share for c, (share, _) in CONDITIONS.items()}
    for day in range(cfg.days):
        base = day * 1440
        for _ in range(poisson(rng, cfg.donations_per_day)):
            donations.append({"minute": base + rng.randint(8 * 60, 20 * 60), "bank_id": rng.choice(world.banks)["_id"],
                              "blood_group": pick(rng, GROUP_MIX), "component": pick(rng, DONATION_COMPONENTS)})
        for source, mean in (("hospital", cfg.hospital_requests_per_day), ("public", cfg.public_requests_per_day)):
            for _ in range(poisson(rng, mean)):
                condition = pick(rng, condition_share)
                if source == "hospital":
                    hospital = rng.choice(world.hospitals)
                    origin, units = hospital["node_id"], rng.choice([1, 1, 2, 2, 2, 3, 4])
                else:
                    origin, units = rng.choice(world.public_origins), rng.choice([1, 1, 2])
                requests.append({
                    "_id": f"R{len(requests) + 1:06d}", "minute": base + rng.randint(0, 1439), "source": source,
                    "origin": origin, "blood_group": pick(rng, GROUP_MIX),
                    "component": pick(rng, CONDITIONS[condition][1]), "units_needed": units,
                    "patient_condition": condition, "base_score": base_score(condition),
                })
    return donations, requests


# ---- one method, one run ------------------------------------------------------------

@dataclass
class Outcome:
    """What happened to one request."""
    request: dict
    fulfilled: bool = False
    locate_min: float = 0.0
    bank_km: float = 0.0
    used_donors: bool = False


@dataclass
class Simulation:
    world: World
    method: str
    seed: int
    state: AppState = field(init=False)
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.state = self.world.fresh_state()
        self.rng = random.Random(f"{self.seed}-{self.method}")
        self.queue = RequestQueue()
        self.outcomes: list[Outcome] = []
        self.total_units = sum(1 for u in self.world.docs["blood_units"] if u["status"] == "available")
        self.expired = 0
        self.transfers = 0
        self.daily: list[dict] = []
        self._unit_seq = 0

    # -- clock ------------------------------------------------------------------

    @staticmethod
    def day_of(minute: float) -> date:
        return START + timedelta(days=int(minute // 1440))

    @staticmethod
    def clock(minute: float) -> datetime:
        return datetime.combine(START, datetime.min.time()) + timedelta(minutes=minute)

    # -- main loop ----------------------------------------------------------------

    def run(self, donations: list[dict], requests: list[dict]) -> dict:
        """Process every event in time order with our MinHeap as the event queue."""
        cfg = self.world.config
        events = MinHeap()
        seq = 0
        for day in range(cfg.days):
            events.push((day * 1440, DAY_START, seq := seq + 1), {"day": day})
        for donation in donations:
            events.push((donation["minute"], DONATION, seq := seq + 1), donation)
        dispatch_ticks = set()
        for request in requests:
            events.push((request["minute"], ARRIVAL, seq := seq + 1), request)
            tick = math.ceil(request["minute"] / cfg.dispatch_min) * cfg.dispatch_min
            if request["source"] == "hospital" and self.method != "traditional" and tick not in dispatch_ticks:
                dispatch_ticks.add(tick)
                events.push((tick, DISPATCH, seq := seq + 1), {})

        t0 = time.perf_counter()
        while not events.is_empty():
            (minute, kind, _), payload = events.pop()
            if kind == DAY_START:
                self.start_day(payload["day"])
            elif kind == DONATION:
                self.donate(payload)
            elif kind == ARRIVAL:
                self.arrive(payload, minute)
            else:
                self.dispatch(minute)
        self.close_day(cfg.days - 1)
        return self.metrics(time.perf_counter() - t0)

    def start_day(self, day: int) -> None:
        if day > 0:
            self.close_day(day - 1)
        today = START + timedelta(days=day)
        self.expired += len(self.state.inventory.purge_expired(today))
        if self.method == "raktsetu_transfer":
            self.transfer_expiring(today)

    def close_day(self, day: int) -> None:
        if len(self.daily) > day:
            return
        self.daily.append({"day": day + 1, "expired": self.expired, "total_units": self.total_units,
                           "wastage_pct": round(100 * self.expired / self.total_units, 3)})

    def donate(self, donation: dict) -> None:
        today = self.day_of(donation["minute"])
        self._unit_seq += 1
        self.state.inventory.add_unit({
            "_id": f"S{self._unit_seq:07d}", "bank_id": donation["bank_id"], "city_id": CITY_ID,
            "blood_group": donation["blood_group"], "component": donation["component"],
            "collected_on": today, "expires_on": today + timedelta(days=SHELF_LIFE_DAYS[donation["component"]]),
            "status": "available",
        })
        self.total_units += 1

    def arrive(self, request: dict, minute: float) -> None:
        if self.method == "traditional":
            self.serve_traditional(request, minute)
        elif request["source"] == "public":
            self.serve_raktsetu(request, minute, minute)
        else:
            self.queue.push({**request, "created_at": self.clock(minute)})

    def dispatch(self, minute: float) -> None:
        """Serve every waiting hospital request, highest effective priority (urgency + aging) first."""
        now = self.clock(minute)
        while not self.queue.is_empty():
            request = self.queue.pop(now)
            self.serve_raktsetu(request, request["minute"], minute)

    # -- the methods ----------------------------------------------------------------

    def serve_traditional(self, request: dict, minute: float) -> None:
        """Phone banks in random order; each bank hands out random compatible units."""
        cfg, inventory = self.world.config, self.state.inventory
        today = self.day_of(minute)
        groups = compatible_groups(request["blood_group"], request["component"])
        dist = self.world.distances(request["origin"])
        directory = [b["_id"] for b in self.world.banks]
        self.rng.shuffle(directory)
        outcome, taken, banks_used = Outcome(request), [], set()
        need = request["units_needed"]
        for calls, bank_id in enumerate(directory[:cfg.max_bank_calls], start=1):
            pool = [u for g in groups for u in inventory.available_units(bank_id, g, request["component"], today)]
            while pool and len(taken) < need:
                unit = pool.pop(self.rng.randrange(len(pool)))
                inventory.set_status(unit["_id"], "reserved")
                taken.append(unit)
                banks_used.add(bank_id)
            if len(taken) == need:
                outcome.fulfilled, outcome.locate_min = True, calls * cfg.call_min
                break
        bank_node = {b["_id"]: b["node_id"] for b in self.world.banks}
        outcome.bank_km = sum(dist.get(bank_node[b], 0.0) for b in banks_used)
        self.settle(outcome, taken, [])

    def serve_raktsetu(self, request: dict, arrived: float, minute: float) -> None:
        """Nearest banks within the radius first, FEFO; donors if the banks fall short."""
        cfg, inventory = self.world.config, self.state.inventory
        today = self.day_of(minute)
        groups = compatible_groups(request["blood_group"], request["component"])
        outcome, taken, km = Outcome(request), [], 0.0
        need = request["units_needed"]
        for bank_id, d in self.world.banks_by_distance(request["origin"]):
            if d > cfg.radius_km or len(taken) == need:
                break
            units = inventory.reserve(bank_id, groups, request["component"], need - len(taken), today)
            if units:
                taken += units
                km += d
        locate = (minute - arrived) + cfg.app_search_min
        donors = []
        if len(taken) < need:
            outcome.used_donors = True
            hits = find_donors(self.state, CITY_ID, groups, self.world.within_radius(request["origin"]), today)
            for calls, hit in enumerate(hits[:cfg.max_donor_calls], start=1):
                if self.rng.random() < cfg.donor_response_prob:
                    donors.append(hit.donor_id)
                    if len(taken) + len(donors) == need:
                        locate += calls * cfg.call_min
                        break
        outcome.fulfilled = len(taken) + len(donors) == need
        outcome.locate_min, outcome.bank_km = locate, km
        if outcome.fulfilled:
            for donor_id in donors:  # they donate now, so are not eligible again for months
                self.state.donors_by_id[donor_id]["last_donation_date"] = today
        self.settle(outcome, taken, donors)

    def settle(self, outcome: Outcome, taken: list[dict], donors: list[str]) -> None:
        """Issue the reserved units if the request is covered, otherwise put them back."""
        for unit in taken:
            self.state.inventory.set_status(unit["_id"], "issued" if outcome.fulfilled else "available")
        if not outcome.fulfilled:
            outcome.bank_km = 0.0
        self.outcomes.append(outcome)

    def transfer_expiring(self, today: date) -> None:
        """Move units about to expire to the nearest bank that is short of them.

        A unit moves at most once. The target is found by walking the other banks
        in road-distance order (Dijkstra from the bank's junction, cached).
        """
        cfg, inventory = self.world.config, self.state.inventory
        for bank in self.world.banks:
            for unit in inventory.expiring_within(bank["_id"], cfg.transfer_within_days, today):
                if unit.get("moved"):
                    continue
                for target, d in self.world.banks_by_distance(bank["node_id"]):
                    if d > cfg.radius_km:
                        break
                    if target != bank["_id"] and inventory.count_available(
                            target, [unit["blood_group"]], unit["component"], today) < cfg.short_threshold:
                        inventory.set_status(unit["_id"], "transferred")
                        inventory.add_unit({**unit, "_id": unit["_id"] + "-T", "bank_id": target,
                                            "status": "available", "moved": True})
                        self.transfers += 1
                        break

    # -- metrics ----------------------------------------------------------------------

    def metrics(self, seconds: float) -> dict:
        found = [o for o in self.outcomes if o.fulfilled]
        critical = [o for o in self.outcomes if o.request["base_score"] >= self.world.config.critical_score]
        with_banks = [o for o in found if o.bank_km > 0]
        times = [o.locate_min for o in found]
        return {
            "method": self.method, "seed": self.seed, "requests": len(self.outcomes),
            "critical_requests": len(critical), "total_units": self.total_units, "expired_units": self.expired,
            "wastage_pct": pct(self.expired, self.total_units),
            "locate_min_mean": round(statistics.fmean(times), 3) if times else 0.0,
            "locate_min_p90": round(percentile(times, 90), 3) if times else 0.0,
            "fulfilment_pct": pct(len(found), len(self.outcomes)),
            "critical_fulfilment_pct": pct(sum(o.fulfilled for o in critical), len(critical)),
            "distance_km_mean": round(statistics.fmean(o.bank_km for o in with_banks), 3) if with_banks else 0.0,
            "donor_fallback_pct": pct(sum(o.used_donors for o in self.outcomes), len(self.outcomes)),
            "transfers": self.transfers, "seconds": round(seconds, 2),
        }


def pct(part: float, whole: float) -> float:
    return round(100 * part / whole, 3) if whole else 0.0


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile (the value q% of requests did not exceed)."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q / 100 * len(ordered)) - 1)]


# ---- running everything ------------------------------------------------------------

_WORLD: World | None = None


def _init_worker(folder: str, config: Config) -> None:
    global _WORLD
    _WORLD = World(Path(folder), config)


def _run_job(job: tuple[int, int]) -> tuple[dict, list[dict]]:
    """One run index: build the events once and play them through every method."""
    run_index, seed = job
    donations, requests = generate_events(_WORLD, seed)
    rows, daily = [], []
    for method in METHODS:
        sim = Simulation(_WORLD, method, seed)
        row = sim.run(donations, requests)
        row["run"] = run_index
        rows.append(row)
        daily += [{"method": method, "run": run_index, **d} for d in sim.daily]
    return rows, daily


def run_all(config: Config, runs: int, seed: int, workers: int, folder: Path) -> tuple[list[dict], list[dict]]:
    jobs = [(i, seed + i) for i in range(runs)]
    rows, daily = [], []
    if workers <= 1:
        _init_worker(str(folder), config)
        results = map(_run_job, jobs)
    else:
        pool = ProcessPoolExecutor(workers, initializer=_init_worker, initargs=(str(folder), config))
        results = pool.map(_run_job, jobs)
    for run_rows, run_daily in results:
        rows += run_rows
        daily += run_daily
        print(f"  run {run_rows[0]['run'] + 1}/{runs} done "
              "(" + ", ".join(f"{r['method']} {r['seconds']}s" for r in run_rows) + ")", flush=True)
    if workers > 1:
        pool.shutdown()
    return rows, daily


# ---- summary and charts --------------------------------------------------------------

# metric key -> (label, unit, lower is better)
METRICS = {
    "wastage_pct": ("Wastage", "% of units expired", True),
    "locate_min_mean": ("Time to locate blood (mean)", "minutes", True),
    "locate_min_p90": ("Time to locate blood (90th percentile)", "minutes", True),
    "fulfilment_pct": ("Requests fulfilled", "% of requests", False),
    "critical_fulfilment_pct": ("Critical requests fulfilled", "% of critical requests", False),
    "distance_km_mean": ("Distance to the supplying banks", "km by road, per fulfilled request", True),
    # Not ranked: needing donors is a property of the stock, and traditional has no fallback at all.
    "donor_fallback_pct": ("Donor fallback", "% of requests that needed donors", None),
}


def summarise(rows: list[dict]) -> list[dict]:
    summary = []
    for method in METHODS:
        mine = [r for r in rows if r["method"] == method]
        entry = {"method": method, "runs": len(mine)}
        for key in [*METRICS, "transfers", "requests", "seconds"]:
            values = [r[key] for r in mine]
            entry[f"{key}_mean"] = round(statistics.fmean(values), 3)
            entry[f"{key}_std"] = round(statistics.stdev(values), 3) if len(values) > 1 else 0.0
        summary.append(entry)
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def daily_means(daily: list[dict], days: int) -> dict[str, list[float]]:
    lines = {}
    for method in METHODS:
        lines[method] = [statistics.fmean(d["wastage_pct"] for d in daily if d["method"] == method and d["day"] == day)
                         for day in range(1, days + 1)]
    return lines


def write_markdown(summary: list[dict], config: Config, runs: int, seed: int, seconds: float) -> None:
    by = {s["method"]: s for s in summary}
    head = "| Metric | " + " | ".join(LABELS[m] for m in METHODS) + " |"
    lines = [head, "|---|" + "---|" * len(METHODS)]
    for key, (label, unit, lower) in METRICS.items():
        means = [by[m][f"{key}_mean"] for m in METHODS]
        best = None if lower is None else min(means) if lower else max(means)
        cells = []
        for m, mean in zip(METHODS, means):
            text = f"{mean:.2f} ± {by[m][f'{key}_std']:.2f}"
            if key == "donor_fallback_pct" and m == "traditional":
                text = "n/a (no fallback)"
            cells.append(f"**{text}**" if mean == best and len(set(means)) > 1 else text)
        lines.append(f"| {label} ({unit}) | " + " | ".join(cells) + " |")
    lines.append("| Units transferred (per run) | " + " | ".join(
        f"{by[m]['transfers_mean']:.0f} ± {by[m]['transfers_std']:.0f}" for m in METHODS) + " |")
    lines.append("| Requests (per run) | " + " | ".join(
        f"{by[m]['requests_mean']:.0f}" for m in METHODS) + " |")

    c = config
    text = f"""# RaktSetu simulation results

{c.days} days, {runs} runs per method (seeds {seed} to {seed + runs - 1}), mean ± standard deviation
across runs. Bold marks the best method for each metric. Synthetic 60 km city centred on Ahmedabad
(seed {CITY_SEED}, {START.isoformat()}): 30 blood banks, 40 hospitals, 3,000 donors. Total time
{seconds:.0f} s on {platform.processor() or platform.machine()}, Python {platform.python_version()}.

{chr(10).join(lines)}

Charts: `wastage_over_time.png` and one `metric_<name>.png` per metric. Every run is in `runs.csv`,
the means in `summary.csv`, and the day-by-day wastage in `daily_wastage.csv`.

## How to read it

- **Wastage**: units that expired during the simulation, as a share of all units available at the
  start plus every unit donated. Units still in stock at the end are not counted as wasted.
- **Time to locate**: from the request to knowing where every unit will come from, for fulfilled
  requests. Traditional: {c.call_min:g} minutes per phone call. RaktSetu: {c.app_search_min:g} minute to search,
  plus the wait for the next {c.dispatch_min}-minute dispatch for hospital requests, plus
  {c.call_min:g} minutes per donor called when the fallback is needed.
- **Fulfilled**: every unit asked for was found. A request that is only partly covered counts as
  not fulfilled and its units go back into stock.
- **Critical**: patient conditions with an urgency of {c.critical_score} or more (accident, delivery
  complication, dengue with low platelets).
- **Distance**: road km from the requester to each bank that supplied units, added up, for fulfilled
  requests that took units from a bank.
- **Donor fallback**: requests where the banks within {c.radius_km:g} km could not cover the request and
  donors were contacted. The traditional method has no donor fallback.

## Model

- Each day: about {c.donations_per_day:g} donations (Poisson), each one unit at a random bank between
  08:00 and 20:00, blood group from the Indian population mix, component by the usual split
  (red cells 35%, whole blood 30%, plasma 25%, platelets 10%) with its standard shelf life.
- Each day: about {c.hospital_requests_per_day:g} hospital requests (1 to 4 units) and {c.public_requests_per_day:g}
  public requests (1 or 2 units) at random minutes. Public requests come from {c.public_origins} fixed
  neighbourhoods. The patient condition sets the urgency and the component (dengue needs platelets,
  thalassemia red cells, and so on).
- Units past their expiry are removed at the start of each day.
- Traditional: first come, first served; the requester calls banks from the directory in random
  order and stops after {c.max_bank_calls} calls; a bank hands out random compatible units.
- RaktSetu: public requests are searched on arrival; hospital requests wait in the priority queue
  (urgency + {URGENCY['accident']}-point scale with aging) and are dispatched every {c.dispatch_min} minutes.
  Banks within {c.radius_km:g} km by road are used nearest first, units soonest to expire first. If they
  fall short, up to {c.max_donor_calls} eligible, available, consenting donors within {c.radius_km:g} km are
  called nearest first; each agrees with probability {c.donor_response_prob:g}.
- RaktSetu + transfers: at the start of each day, each unit expiring within {c.transfer_within_days} days moves
  (once) to the nearest bank within {c.radius_km:g} km holding fewer than {c.short_threshold} units of that group
  and component.
- Within a run every method sees exactly the same donations and requests.
"""
    (RESULTS / "summary.md").write_text(text, encoding="utf-8")


def charts(summary: list[dict], daily: list[dict], days: int, runs: int) -> None:
    from benchmarks.bench_core import GRID, INK, MUTED, SURFACE, chart_style, end_label, rounded_bar

    # Categorical slots 1-3 of the validated palette (blue, orange, aqua); aqua is below 3:1 on
    # white, so every bar and line also carries a direct text label.
    colors = dict(zip(METHODS, ["#2a78d6", "#eb6834", "#1baf7a"]))
    plt = chart_style()
    by = {s["method"]: s for s in summary}
    for key, (label, unit, lower) in METRICS.items():
        fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=160)
        means = [by[m][f"{key}_mean"] for m in METHODS]
        stds = [by[m][f"{key}_std"] for m in METHODS]
        top = max(m + s for m, s in zip(means, stds)) or 1
        ax.set_xlim(-0.6, len(METHODS) - 0.4)
        ax.set_ylim(0, top * 1.25)
        ax.set_xticks(range(len(METHODS)), [LABELS[m] for m in METHODS])
        for x, (method, mean, std) in enumerate(zip(METHODS, means, stds)):
            na = key == "donor_fallback_pct" and method == "traditional"
            if not na:
                rounded_bar(ax, x, mean, 0.5, colors[method])
            if std:
                ax.errorbar(x, mean, yerr=std, color=INK, capsize=4, linewidth=1.2, zorder=4)
            end_label(ax, x, mean + std, "n/a" if na else f"{mean:.1f} ± {std:.1f}")
        ax.set_title(label)
        ax.set_ylabel(unit)
        better = "" if lower is None else f"; {'lower' if lower else 'higher'} is better"
        fig.text(0.01, 0.01, f"Mean ± std over {runs} runs of {days} days{better}.",
                 fontsize=8.5, color=MUTED)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(RESULTS / f"metric_{key.removesuffix('_pct').removesuffix('_mean')}.png")
        plt.close(fig)

    lines = daily_means(daily, days)
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=160)
    x = list(range(1, days + 1))
    for method in METHODS:
        ys = lines[method]
        ax.plot(x, ys, color=colors[method], label=LABELS[method], zorder=3)
        ax.annotate(f"{ys[-1]:.1f}%", (x[-1], ys[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)
    ax.set_title("Wastage over time")
    ax.set_xlabel("Day")
    ax.set_ylabel("Units expired so far, % of all units")
    ax.set_xlim(1, days * 1.1)
    ax.set_ylim(0, max(max(v) for v in lines.values()) * 1.2 or 1)
    ax.legend(loc="lower right")
    fig.text(0.01, 0.01, f"Cumulative, mean over {runs} runs. Same donations and requests for every method.",
             fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(RESULTS / "wastage_over_time.png")
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="RaktSetu simulation: traditional vs RaktSetu")
    p.add_argument("--days", type=int, default=90)
    p.add_argument("--runs", type=int, default=10)
    p.add_argument("--seed", type=int, default=1000, help="seed of the first run; run i uses seed + i")
    p.add_argument("--workers", type=int, default=0, help="processes (default: one per run, up to the CPU count)")
    p.add_argument("--data", type=Path, default=None, help="generated city folder (default: generate the standard one)")
    p.add_argument("--quick", action="store_true", help="5 days, 2 runs: a smoke test")
    p.add_argument("--no-charts", action="store_true")
    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.quick:
        args.days, args.runs = 5, 2

    config = Config(days=args.days)
    folder = args.data or synthetic_city()
    workers = args.workers or min(args.runs, os.cpu_count() or 1)
    RESULTS.mkdir(parents=True, exist_ok=True)
    print(f"Simulating {args.days} days x {args.runs} runs x {len(METHODS)} methods ({workers} processes)...")
    t0 = time.perf_counter()
    rows, daily = run_all(config, args.runs, args.seed, workers, folder)
    seconds = time.perf_counter() - t0

    summary = summarise(rows)
    write_csv(RESULTS / "runs.csv", rows)
    write_csv(RESULTS / "summary.csv", summary)
    write_csv(RESULTS / "daily_wastage.csv", daily)
    write_markdown(summary, config, args.runs, args.seed, seconds)
    if not args.no_charts:
        charts(summary, daily, args.days, args.runs)
    print((RESULTS / "summary.md").read_text(encoding="utf-8").split("## How to read it")[0])
    print(f"Done in {seconds:.0f} s. Results in {RESULTS}")


if __name__ == "__main__":
    main()
