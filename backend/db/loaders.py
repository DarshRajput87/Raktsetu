"""Read MongoDB into the in-memory AppState. Plain reads only: no sorting, no geo queries."""

import logging
import time

from motor.motor_asyncio import AsyncIOMotorDatabase

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


async def load_state(db: AsyncIOMotorDatabase) -> AppState:
    """Build the AppState from every collection."""
    cities = await db.cities.find().to_list(None)
    state = AppState.build(
        cities=cities,
        banks=await db.blood_banks.find().to_list(None),
        hospitals=await db.hospitals.find().to_list(None),
        donors=await db.donors.find().to_list(None),
        units=await db.blood_units.find().to_list(None),
        roads=[await load_city_roads(db, city["_id"]) for city in cities],
    )
    counts = state.counts()
    log.info("Loaded into memory: %s", ", ".join(f"{v:,} {k}" for k, v in counts.items()))
    return state
