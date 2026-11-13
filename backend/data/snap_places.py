"""Snap places that only have a lat/lng onto the real road network.

For places added after the import (a new bank, real bank data, donors loaded in
bulk): sets city_id and node_id to the nearest road junction of their city.

    python -m data.snap_places                         # places without a node_id
    python -m data.snap_places --collection blood_banks --all

Uses the same function as the API's register endpoints
(modules.cities.snap_to_city: city by expanded bbox, junction by grid index).
"""

import argparse

from pymongo import MongoClient
from pymongo.database import Database

from config import get_settings
from modules.cities import CityNotSupported, snap_to_city
from modules.geo import GridIndex

PLACE_COLLECTIONS = ["blood_banks", "hospitals", "donors"]


class IndexLoader:
    """Builds each city's GridIndex from MongoDB the first time it is needed."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._indexes: dict[str, GridIndex] = {}

    def __call__(self, city_id: str) -> GridIndex:
        if city_id not in self._indexes:
            coords = {n["_id"]: (n["lat"], n["lng"])
                      for n in self._db.road_nodes.find({"city_id": city_id}, {"lat": 1, "lng": 1})}
            self._indexes[city_id] = GridIndex(coords)
        return self._indexes[city_id]


def snap_collection(db: Database, name: str, cities: dict[str, dict], index_for: IndexLoader,
                    everything: bool = False) -> tuple[int, int]:
    """Returns (snapped, outside every supported city)."""
    query = {} if everything else {"$or": [{"node_id": None}, {"node_id": {"$exists": False}}]}
    snapped = skipped = 0
    for doc in db[name].find(query, {"lat": 1, "lng": 1}):
        try:
            city_id, node_id = snap_to_city(cities, index_for, doc["lat"], doc["lng"])
        except (CityNotSupported, KeyError, TypeError):
            skipped += 1
            continue
        db[name].update_one({"_id": doc["_id"]}, {"$set": {"city_id": city_id, "node_id": node_id}})
        snapped += 1
    return snapped, skipped


def main() -> None:
    settings = get_settings()
    p = argparse.ArgumentParser(description="Snap places to the nearest real road junction")
    p.add_argument("--collection", choices=PLACE_COLLECTIONS, default=None, help="default: all three")
    p.add_argument("--all", action="store_true", help="re-snap every place, not only those without node_id")
    p.add_argument("--mongo-uri", default=settings.mongo_uri)
    p.add_argument("--db", default=settings.db_name)
    args = p.parse_args()

    db = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)[args.db]
    cities = {c["_id"]: c for c in db.cities.find()}
    index_for = IndexLoader(db)
    for name in [args.collection] if args.collection else PLACE_COLLECTIONS:
        snapped, skipped = snap_collection(db, name, cities, index_for, args.all)
        print(f"{name:12s} snapped {snapped:,}; outside every supported city: {skipped:,}")


if __name__ == "__main__":
    main()
