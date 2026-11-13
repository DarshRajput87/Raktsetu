"""Read MongoDB into the in-memory AppState. Plain reads only: no sorting, no geo queries."""

import logging
import time

from motor.motor_asyncio import AsyncIOMotorDatabase

from modules.dates import to_date
from modules.state import AppState, CityRoads

log = logging.getLogger("raktsetu")


async def load_city_roads(db: AsyncIOMotorDatabase, city_id: str) -> CityRoads:
    """Load one city's junctions and roads into our Graph. O(V + E)."""
    t0 = time.perf_counter()
    nodes = await db.road_nodes.find({"city_id": city_id}).to_list(None)
    edges = await db.road_edges.find({"city_id": city_id}).to_list(None)
    roads = CityRoads(city_id, nodes, edges)
    log.info("Loaded roads of '%s' from MongoDB: %s junctions, %s roads in %.2f s", city_id,
             f"{roads.graph.node_count:,}", f"{roads.graph.edge_count:,}", time.perf_counter() - t0)
    return roads


async def ensure_city_loaded(state: AppState, db: AsyncIOMotorDatabase, city_id: str) -> None:
    """Make sure a city's roads are in the LRU cache before a search uses them.

    A hit costs nothing here; a miss reads that city's roads from MongoDB once.
    """
    if city_id not in state.roads:
        state.roads.put(city_id, await load_city_roads(db, city_id))


async def load_state(db: AsyncIOMotorDatabase, city_cache_capacity: int = 5) -> AppState:
    """Build the AppState from every collection and preload the first cities' roads."""
    requests = await db.requests.find().to_list(None)
    for request in requests:
        for allocation in request.get("allocations", []):
            for unit in allocation.get("units", []):
                unit["expires_on"] = to_date(unit["expires_on"])
    donors = await db.donors.find().to_list(None)
    for donor in donors:
        for donation in donor.get("donations", []):
            donation["date"] = to_date(donation["date"])
    transactions = await db.transactions.find().to_list(None)
    transactions.sort(key=lambda t: t["at"])  # rebuild each bank's log in time order

    state = AppState.build(
        cities=await db.cities.find().to_list(None),
        banks=await db.blood_banks.find().to_list(None),
        hospitals=await db.hospitals.find().to_list(None),
        donors=donors,
        units=await db.blood_units.find().to_list(None),
        requests=requests,
        transactions=transactions,
        city_cache_capacity=city_cache_capacity,
    )
    for city_id in list(state.cities)[:city_cache_capacity]:
        await ensure_city_loaded(state, db, city_id)
    log.info("Loaded into memory: %s", ", ".join(f"{v:,} {k}" for k, v in state.counts().items()))
    return state
