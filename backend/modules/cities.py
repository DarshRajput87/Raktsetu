"""Which city serves a request, and the cache of loaded city road graphs."""

import logging
from typing import Callable

from core.lru_cache import LRUCache
from modules.geo import haversine_km

log = logging.getLogger("raktsetu")

NOT_AVAILABLE = "RaktSetu is not available in this area yet"


class CityNotSupported(Exception):
    """The location is outside every supported city."""

    def __init__(self) -> None:
        super().__init__(NOT_AVAILABLE)


def bbox_contains(bbox: list[float], lat: float, lng: float) -> bool:
    """bbox is [south, west, north, east], already expanded by the city's margin."""
    south, west, north, east = bbox
    return south <= lat <= north and west <= lng <= east


def city_for_location(cities: dict[str, dict], lat: float, lng: float,
                      picked: str | None = None) -> str:
    """The supported city whose expanded bbox contains the point.

    If the user picked a city and the point really is inside it, that city is
    used. Otherwise, when several cities contain the point, the one whose
    centre is nearest wins. O(number of cities).
    """
    if picked in cities and bbox_contains(cities[picked]["bbox"], lat, lng):
        return picked
    best, best_km = None, float("inf")
    for city_id, city in cities.items():
        if bbox_contains(city["bbox"], lat, lng):
            km = haversine_km(lat, lng, city["center"][0], city["center"][1])
            if km < best_km:
                best, best_km = city_id, km
    if best is None:
        raise CityNotSupported()
    return best


class CityGraphCache:
    """LRU cache of city road networks (modules.state.CityRoads).

    Holding every city's roads at once would not fit in memory as more cities
    are added, so only the most recently used `capacity` cities stay loaded.
    get and put are O(1) (see core.lru_cache); a miss costs one load from
    MongoDB, O(V + E) for that city.
    """

    def __init__(self, capacity: int, loader: Callable[[str], object] | None = None) -> None:
        self._cache = LRUCache(capacity)
        self._loader = loader
        self.hits = 0
        self.misses = 0

    def __contains__(self, city_id: str) -> bool:
        return city_id in self._cache

    def get(self, city_id: str):
        """The city's roads. A miss calls the loader, or raises KeyError without one."""
        roads = self._cache.get(city_id)
        if roads is not None:
            self.hits += 1
            log.info("City graph cache hit: %s (hits=%d, misses=%d)", city_id, self.hits, self.misses)
            return roads
        if self._loader is None:
            raise KeyError(f"roads of city '{city_id}' are not loaded")
        self.put(city_id, self._loader(city_id))
        return self._cache.get(city_id)

    def put(self, city_id: str, roads: object) -> None:
        """Store a freshly loaded city, evicting the least recently used one if full."""
        self.misses += 1
        log.info("City graph cache miss: %s loaded (hits=%d, misses=%d)", city_id, self.hits, self.misses)
        evicted = self._cache.put(city_id, roads)
        if evicted is not None:
            log.info("City graph cache evicted: %s", evicted[0])

    def loaded(self) -> list[str]:
        """Loaded cities, most recently used first."""
        return self._cache.keys()

    def peek(self, city_id: str):
        """The city's roads if loaded (no hit counted, no reordering), else None."""
        return self._cache.peek(city_id)
