"""Case 1: find the nearest blood banks with compatible stock, or fall back to donors.

Everything here runs in memory on our own structures: a dict lookup for the
compatible groups, the grid index to snap the location, Dijkstra with a
distance cutoff on the city's road graph, and heaps for ordering.
"""

import math
from dataclasses import dataclass, field
from datetime import date

from core.graph import build_path, dijkstra_until
from core.heap import MinHeap
from modules.cities import city_for_location
from modules.compatibility import compatible_groups
from modules.eligibility import is_eligible
from modules.state import AppState, CityRoads

MAX_DONORS = 50
TRACE_LIMIT = 6000


@dataclass
class BankHit:
    bank_id: str
    name: str
    area: str
    lat: float
    lng: float
    phone: str
    node_id: str
    distance_km: float
    est_travel_min: float
    units: int
    units_by_group: dict[str, int]


@dataclass
class DonorHit:
    """A matching donor. Deliberately has no phone number: that is only given
    out by the contact endpoint, after login."""
    donor_id: str
    name: str
    blood_group: str
    lat: float
    lng: float
    distance_km: float


@dataclass
class SearchResult:
    city_id: str
    group: str
    component: str
    radius_km: float
    compatible_groups: list[str]
    start_node: str
    start: list[float]
    banks: list[BankHit] = field(default_factory=list)
    route: list[list[float]] = field(default_factory=list)
    route_bank_id: str | None = None
    donors: list[DonorHit] = field(default_factory=list)
    junctions_visited: int = 0
    # Only filled when trace=True (for the "how it works" animation).
    trace: list[dict] | None = None
    banks_reached: list[dict] | None = None


@dataclass
class RouteResult:
    bank_id: str
    distance_km: float
    est_travel_min: float
    route: list[list[float]]


def public_name(name: str) -> str:
    """'Rohan Sharma' -> 'Rohan S.' so search results do not expose full names."""
    parts = name.split()
    return name if len(parts) < 2 else f"{parts[0]} {parts[-1][0]}."


def search_blood(state: AppState, lat: float, lng: float, group: str, component: str,
                 radius_km: float = 25.0, today: date | None = None, *,
                 city_id: str | None = None, trace: bool = False,
                 exclude_banks: tuple[str, ...] | list[str] = (),
                 always_list_donors: bool = False) -> SearchResult:
    """Banks within radius_km (by road) holding usable compatible stock, nearest
    first, with the route to the nearest one. If there is none, matching donors.

    Cost: one cutoff Dijkstra, O((V' + E') log V') for the V' junctions and E'
    roads within the radius, plus O(1) hash-map work per bank reached, plus
    O(d log d) to order d matching donors in the fallback.
    """
    today = today or date.today()
    city_id = city_for_location(state.cities, lat, lng, city_id)
    roads = state.get_roads(city_id)
    groups = compatible_groups(group, component)
    start = roads.index.nearest(lat, lng)[0]

    result = SearchResult(city_id=city_id, group=group, component=component, radius_km=radius_km,
                          compatible_groups=groups, start_node=start,
                          start=list(roads.node_coords[start]))
    dist: dict[str, float] = {}
    prev: dict[str, str] = {}
    visits: list[tuple[str, float, str | None]] = []
    reached: list[dict] = []

    def on_visit(node: str, d: float, parent: str | None) -> None:
        dist[node] = d
        if trace:
            visits.append((node, d, parent))

    def is_bank_node(node: str) -> bool:
        return node in state.banks_by_node

    # Bank junctions arrive in increasing road distance, so `banks` is already sorted.
    for node, d in dijkstra_until(roads.graph, start, is_bank_node, radius_km, prev, on_visit):
        for bank_id in state.banks_by_node[node]:
            bank = state.banks_by_id[bank_id]
            if bank["city_id"] != city_id or not bank.get("verified", True) or bank_id in exclude_banks:
                continue
            by_group = state.inventory.available_by_group(bank_id, groups, component, today)
            reached.append({"bank_id": bank_id, "node": node, "lat": bank["lat"], "lng": bank["lng"],
                            "dist_km": round(d, 3), "has_stock": bool(by_group)})
            if by_group:
                path = build_path(prev, start, node)
                result.banks.append(BankHit(
                    bank_id=bank_id, name=bank["name"], area=bank.get("area", ""), lat=bank["lat"],
                    lng=bank["lng"], phone=bank["phone"], node_id=node, distance_km=round(d, 3),
                    est_travel_min=round(roads.route_minutes(path), 1),
                    units=sum(by_group.values()), units_by_group=by_group))

    result.junctions_visited = len(dist)
    if result.banks:
        nearest = result.banks[0]
        result.route = roads.route_coords(build_path(prev, start, nearest.node_id))
        result.route_bank_id = nearest.bank_id
    if not result.banks or always_list_donors:
        result.donors = find_donors(state, city_id, groups, dist, today)
    if trace:
        result.trace = build_trace(roads, visits, {b["node"] for b in reached})
        result.banks_reached = reached
    return result


def find_donors(state: AppState, city_id: str, groups: list[str], dist: dict[str, float],
                today: date, limit: int = MAX_DONORS) -> list[DonorHit]:
    """Compatible donors who are eligible, available, consenting and reachable
    (their junction is in `dist`), nearest first.

    The candidates come straight from the donors_by_group hash map, so only
    donors of a compatible group are looked at. They are ordered with our
    MinHeap: O(d log d) for d matches.
    """
    by_group = state.donors_by_group.get(city_id, {})
    heap = MinHeap()
    for group in groups:
        for donor_id in by_group.get(group, ()):
            donor = state.donors_by_id[donor_id]
            if (donor["node_id"] in dist and donor.get("available") and donor.get("contact_consent")
                    and is_eligible(donor, today)):
                heap.push(dist[donor["node_id"]], donor)
    hits = []
    while not heap.is_empty() and len(hits) < limit:
        d, donor = heap.pop()
        hits.append(DonorHit(donor_id=donor["_id"], name=public_name(donor["name"]),
                             blood_group=donor["blood_group"], lat=donor["lat"], lng=donor["lng"],
                             distance_km=round(d, 3)))
    return hits


def build_trace(roads: CityRoads, visits: list[tuple[str, float, str | None]],
                keep: set[str], limit: int = TRACE_LIMIT) -> list[dict]:
    """Junctions in the order Dijkstra settled them. A real city has far more
    junctions within 25 km than an animation can show, so the list is thinned
    evenly to about `limit` entries (bank junctions are always kept)."""
    step = max(1, math.ceil(len(visits) / limit))
    trace = []
    for i, (node, d, parent) in enumerate(visits):
        if i % step == 0 or node in keep:
            lat, lng = roads.node_coords[node]
            trace.append({"node": node, "lat": lat, "lng": lng, "dist_km": round(d, 3), "parent": parent})
    return trace


def nearest_banks(state: AppState, lat: float, lng: float, k: int = 5,
                  city_id: str | None = None, max_km: float | None = None) -> list[tuple[dict, float]]:
    """The k nearest verified banks by road distance, as (bank, km) pairs.

    dijkstra_until is a generator, so the search stops as soon as the k-th bank
    is reached instead of exploring the whole city.
    """
    city_id = city_for_location(state.cities, lat, lng, city_id)
    roads = state.get_roads(city_id)
    start = roads.index.nearest(lat, lng)[0]
    found: list[tuple[dict, float]] = []
    for node, d in dijkstra_until(roads.graph, start, lambda n: n in state.banks_by_node, max_km):
        for bank_id in state.banks_by_node[node]:
            bank = state.banks_by_id[bank_id]
            if bank["city_id"] == city_id and bank.get("verified", True):
                found.append((bank, round(d, 3)))
        if len(found) >= k:
            break
    return found[:k]


def route_to_bank(state: AppState, lat: float, lng: float, bank_id: str) -> RouteResult | None:
    """Shortest road route from a location to one bank, or None if no road leads there.

    Dijkstra stops the moment the bank's junction is settled.
    """
    bank = state.banks_by_id[bank_id]
    roads = state.get_roads(bank["city_id"])
    start = roads.index.nearest(lat, lng)[0]
    prev: dict[str, str] = {}
    target = bank["node_id"]
    for node, d in dijkstra_until(roads.graph, start, lambda n: n == target, None, prev):
        path = build_path(prev, start, node)
        return RouteResult(bank_id=bank_id, distance_km=round(d, 3),
                           est_travel_min=round(roads.route_minutes(path), 1),
                           route=roads.route_coords(path))
    return None
