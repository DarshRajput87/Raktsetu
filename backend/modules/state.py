"""Everything the API keeps in memory.

MongoDB only stores data. At startup it is loaded into these structures, every
search runs on them, and every change is applied here first and then written
back to MongoDB.
"""

from typing import Any

from fastapi import Request

from core.graph import Graph
from modules.audit import AuditLog, UndoManager
from modules.cities import CityGraphCache
from modules.dates import to_date
from modules.geo import GridIndex
from modules.inventory import Inventory
from modules.requests import RequestQueue

DEFAULT_CITY = "synthetic"


class CityRoads:
    """One city's road network: our Graph plus what is needed to snap and draw.

    Building it is O(V + E): one pass over the junctions and one over the roads.
    """

    def __init__(self, city_id: str, nodes: list[dict], edges: list[dict]) -> None:
        self.city_id = city_id
        self.graph = Graph()
        self.node_coords: dict[str, tuple[float, float]] = {}
        # (from, to) -> minutes, for the estimated travel time along a route.
        self.travel_min: dict[tuple[str, str], float] = {}
        self._edge_km: dict[tuple[str, str], float] = {}
        for node in nodes:
            self.graph.add_node(node["_id"])
            self.node_coords[node["_id"]] = (node["lat"], node["lng"])
        for edge in edges:
            self._add_edge(edge)
        self._edge_km.clear()
        self.index = GridIndex(self.node_coords)

    def _add_edge(self, edge: dict) -> None:
        u, v, km = edge["from"], edge["to"], edge["distance_km"]
        if u not in self.node_coords or v not in self.node_coords:
            return
        oneway = bool(edge.get("oneway", False))
        self.graph.add_edge(u, v, km, directed=oneway)
        minutes = edge.get("travel_time_min", km / 25 * 60)
        for pair in ((u, v),) if oneway else ((u, v), (v, u)):
            # Parallel roads: Dijkstra uses the shortest, so keep that one's time.
            if pair not in self._edge_km or km < self._edge_km[pair]:
                self._edge_km[pair] = km
                self.travel_min[pair] = minutes

    def route_coords(self, path: list[str]) -> list[list[float]]:
        """[lat, lng] of every junction on a path. O(path length)."""
        return [list(self.node_coords[node]) for node in path]

    def route_minutes(self, path: list[str]) -> float:
        """Estimated travel time along a path. O(path length)."""
        return sum(self.travel_min.get(pair, 0.0) for pair in zip(path, path[1:]))


class AppState:
    """In-memory copy of the data, indexed with hash maps (Python dicts).

    Lookups by id, by junction and by blood group are all O(1) on average.
    """

    def __init__(self, city_cache_capacity: int = 5) -> None:
        self.cities: dict[str, dict] = {}
        self.roads = CityGraphCache(city_cache_capacity)
        self.banks_by_id: dict[str, dict] = {}
        self.banks_by_node: dict[str, list[str]] = {}
        self.hospitals_by_id: dict[str, dict] = {}
        self.donors_by_id: dict[str, dict] = {}
        # city_id -> blood group -> donor ids
        self.donors_by_group: dict[str, dict[str, list[str]]] = {}
        self.inventory = Inventory()
        self.audit = AuditLog()
        self.undo = UndoManager()
        self.requests_by_id: dict[str, dict] = {}
        self.request_queue = RequestQueue()
        self.request_sequence = 0  # order in which requests were processed

    @classmethod
    def build(cls, *, cities: list[dict], banks: list[dict], hospitals: list[dict],
              donors: list[dict], units: list[dict], roads: list[CityRoads] = (),
              requests: list[dict] = (), transactions: list[dict] = (),
              city_cache_capacity: int = 5) -> "AppState":
        """Index the documents. O(total number of documents), plus O(u log u) for
        pushing u available units into the inventory heaps."""
        state = cls(max(city_cache_capacity, len(roads)))
        for city in cities:
            state.cities[city["_id"]] = city
        for city_roads in roads:
            state.roads.put(city_roads.city_id, city_roads)
        for bank in banks:
            state.add_bank(bank)
        for hospital in hospitals:
            hospital.setdefault("city_id", DEFAULT_CITY)
            state.hospitals_by_id[hospital["_id"]] = hospital
        for donor in donors:
            state.add_donor(donor)
        for unit in units:
            unit.setdefault("city_id", state.banks_by_id.get(unit["bank_id"], {}).get("city_id", DEFAULT_CITY))
            state.inventory.add_unit(unit)
        for transaction in transactions:
            state.audit.restore(transaction)
        for request in requests:
            state.requests_by_id[request["_id"]] = request
            state.request_sequence = max(state.request_sequence, request.get("sequence") or 0)
            if request["status"] == "queued":
                state.request_queue.push(request)
        return state

    def add_bank(self, bank: dict) -> None:
        bank.setdefault("city_id", DEFAULT_CITY)
        self.banks_by_id[bank["_id"]] = bank
        self.banks_by_node.setdefault(bank["node_id"], []).append(bank["_id"])

    def add_donor(self, donor: dict) -> None:
        donor.setdefault("city_id", DEFAULT_CITY)
        donor["last_donation_date"] = to_date(donor.get("last_donation_date"))
        self.donors_by_id[donor["_id"]] = donor
        groups = self.donors_by_group.setdefault(donor["city_id"], {})
        groups.setdefault(donor["blood_group"], []).append(donor["_id"])

    def get_roads(self, city_id: str) -> CityRoads:
        return self.roads.get(city_id)

    def counts(self) -> dict[str, int]:
        loaded = [self.roads.peek(city_id) for city_id in self.roads.loaded()]
        return {
            "cities": len(self.cities),
            "road_nodes": sum(r.graph.node_count for r in loaded),
            "road_edges": sum(r.graph.edge_count for r in loaded),
            "blood_banks": len(self.banks_by_id),
            "hospitals": len(self.hospitals_by_id),
            "donors": len(self.donors_by_id),
            "blood_units": len(self.inventory),
        }


def get_state(request: Request) -> AppState:
    """FastAPI dependency: the state built at startup."""
    return request.app.state.data
