"""Import real OpenStreetMap roads per city into MongoDB.

Run from backend/, ahead of time (never during a user request):

    python -m data.import_cities --city ahmedabad
    python -m data.import_cities --all                 # every city in data/cities.json
    python -m data.import_cities --city surat --roads-only

This reuses generate_real_data.py for everything it already does: downloading
the city + margin with OSMnx (cached in downloads/<city_id>.graphml), converting
junctions and roads, and placing fake banks, hospitals, donors and stock on real
junctions. With the same --seed it produces the same places as that script.

What this adds: several cities side by side (ids are prefixed with the city id),
the cities collection, and --roads-only for when real bank data is used.
The JSON is also written to data/output_cities/<city_id>/, in the format
demo_search.py reads (`python demo_search.py --data output_cities/ahmedabad`).
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import date
from pathlib import Path

from pymongo import MongoClient

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # generate_real_data imports generate_data as a top-level module

import generate_real_data as real  # noqa: E402
from generate_data import build_units  # noqa: E402

from config import get_settings  # noqa: E402
from db import seed  # noqa: E402

ROAD_COLLECTIONS = ["road_nodes", "road_edges"]


def load_city_list() -> list[dict]:
    with open(HERE / "cities.json", encoding="utf-8") as f:
        return json.load(f)


def get_graph(city: dict):
    """The city's road graph: from downloads/<id>.graphml if present, else downloaded."""
    cache = HERE / "downloads" / f"{city['id']}.graphml"
    if cache.exists():
        print(f"Loading roads from {cache}")
        return real.load_graph(str(cache)), None
    return real.download_graph(city["place"], city["margin_km"], str(cache))


def build_city(city: dict, args: argparse.Namespace) -> tuple[dict[str, list[dict]], dict]:
    """Roads plus (unless --roads-only) fake places, in the same order of random
    draws as generate_real_data.main, so the same seed gives the same data."""
    rng = random.Random(args.seed)
    as_of = date.fromisoformat(args.as_of)
    G, center = get_graph(city)
    nodes, edges = real.convert_graph(G, city["id"])
    if center is None:
        center = (sum(n["lat"] for n in nodes.values()) / len(nodes),
                  sum(n["lng"] for n in nodes.values()) / len(nodes))
    collections = {"road_nodes": list(nodes.values()), "road_edges": edges}

    if not args.roads_only:
        adj = real.undirected_adjacency(edges)
        big = {"motorway", "trunk", "primary", "secondary", "tertiary"}
        on_big_roads = ({e["from"] for e in edges if e["road_type"] in big}
                        | {e["to"] for e in edges if e["road_type"] in big})
        if len(on_big_roads) < (args.banks + args.hospitals) * 3:
            on_big_roads = None
        place_sampler = real.weighted_node_sampler(rng, nodes, center, 8.0, on_big_roads)
        bank_nodes = place_sampler(args.banks)
        hospital_nodes = place_sampler(args.hospitals, exclude=bank_nodes)
        donor_sampler = real.weighted_node_sampler(rng, nodes, center, 12.0)
        donor_nodes = [donor_sampler(1)[0] for _ in range(args.donors)]

        banks = real.build_places_real(rng, nodes, bank_nodes, "B", "bank", city["id"], 100)
        for bank in banks:
            bank["admin_user_id"] = None
        hospitals = real.build_places_real(rng, nodes, hospital_nodes, "H", "hospital", city["id"], 500)
        donors = real.build_donors_real(rng, nodes, donor_nodes, banks, adj, as_of, city["id"])
        units = build_units(rng, banks, as_of, args.units_per_bank, args.empty_bank_share)
        collections.update(blood_banks=banks, hospitals=hospitals, donors=donors, blood_units=units)

    meta = {
        "as_of": as_of.isoformat(), "seed": args.seed, "city_id": city["id"], "place": city["place"],
        "margin_km": city["margin_km"], "center": [center[0], center[1]],
        "road_source": "OpenStreetMap (c) OpenStreetMap contributors, ODbL",
        "counts": {name: len(docs) for name, docs in collections.items()},
    }
    return collections, meta


def write_json(city_id: str, collections: dict[str, list[dict]], meta: dict) -> Path:
    out = HERE / "output_cities" / city_id
    os.makedirs(out, exist_ok=True)
    for name, docs in collections.items():
        with open(out / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(docs, f)
    with open(out / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return out


def store(db, city: dict, collections: dict[str, list[dict]], meta: dict) -> None:
    """Replace this city's documents (roads only: just its roads) and its cities entry."""
    seed.namespace_ids(collections, city["id"])
    seed.prepare(collections, city["id"])
    seed.remove_city(db, seed.SYNTHETIC_CITY)  # the development grid overlaps Ahmedabad
    for name in seed.EMPTY_COLLECTIONS:
        if name not in db.list_collection_names():
            db.create_collection(name)
    extra = {"name": city["name"], "state": city["state"], "place": city["place"],
             "notes": city.get("notes", "")}
    doc = seed.city_document(city["id"], meta, collections, extra)
    for name, docs in collections.items():
        db[name].delete_many({"city_id": city["id"]})
        for i in range(0, len(docs), seed.BATCH):
            db[name].insert_many(docs[i:i + seed.BATCH], ordered=False)
    db.cities.replace_one({"_id": city["id"]}, doc, upsert=True)
    seed.create_indexes(db)


def import_city(db, city: dict, args: argparse.Namespace) -> None:
    t0 = time.time()
    print(f"\n=== {city['name']} ({city['id']}), city + {city['margin_km']} km ===")
    collections, meta = build_city(city, args)
    out = write_json(city["id"], collections, meta)
    if db is not None:
        store(db, city, collections, meta)
    for name, count in meta["counts"].items():
        print(f"  {name:12s} {count:>9,}")
    print(f"  one-way road segments: {sum(1 for e in collections['road_edges'] if e['oneway']):,}")
    where = f"MongoDB and {out}" if db is not None else str(out)
    print(f"  imported into {where} in {time.time() - t0:.0f} s")


def main() -> None:
    settings = get_settings()
    cities = load_city_list()
    p = argparse.ArgumentParser(description="Import real roads per city (OpenStreetMap)")
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--city", choices=[c["id"] for c in cities])
    target.add_argument("--all", action="store_true", help="every city in data/cities.json")
    p.add_argument("--roads-only", action="store_true", help="import roads without fake places")
    p.add_argument("--no-mongo", action="store_true", help="only write the JSON files")
    p.add_argument("--banks", type=int, default=40)
    p.add_argument("--hospitals", type=int, default=60)
    p.add_argument("--donors", type=int, default=5000)
    p.add_argument("--units-per-bank", type=int, default=120)
    p.add_argument("--empty-bank-share", type=float, default=0.15)
    p.add_argument("--as-of", default=(settings.as_of_date or date.today()).isoformat())
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--overpass-url", default=None, help="another Overpass server, if the default is busy")
    p.add_argument("--mongo-uri", default=settings.mongo_uri)
    p.add_argument("--db", default=settings.db_name)
    args = p.parse_args()

    if args.overpass_url:
        import osmnx as ox
        ox.settings.overpass_url = args.overpass_url
    db = None if args.no_mongo else MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)[args.db]
    t0 = time.time()
    selected = cities if args.all else [c for c in cities if c["id"] == args.city]
    for city in selected:
        import_city(db, city, args)
    if db is not None and not args.roads_only:
        from db.accounts import seed_accounts
        print(f"\nDemo accounts written: {seed_accounts(db)}")
    print(f"Done: {len(selected)} city(ies) in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
