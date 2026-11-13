"""Load generated JSON data into MongoDB.

    python -m db.seed --reset                  # synthetic grid from data/output
    python -m db.seed --source output_real     # one real city from data/output_real

The synthetic grid is stored as the city "synthetic". It is for development only
and overlaps Ahmedabad, so it is removed when a real city is loaded, and real
cities are removed when the synthetic grid is loaded.

Real cities are replaced one at a time by city_id. Their ids are prefixed with
"<city_id>:" so that several cities can live in the same collections (every
generated city has a bank "B001").
"""

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from config import BACKEND_DIR, get_settings

DATA_DIR = BACKEND_DIR / "data"
SYNTHETIC_CITY = "synthetic"
DATA_COLLECTIONS = ["road_nodes", "road_edges", "blood_banks", "hospitals", "donors", "blood_units"]
EMPTY_COLLECTIONS = ["users", "requests", "transactions", "contact_access_logs", "misuse_reports", "cities"]
DATE_FIELDS = ("collected_on", "expires_on", "last_donation_date")
REFERENCE_FIELDS = ("from", "to", "node_id", "linked_bank_id", "bank_id")
BATCH = 10_000


def read_source(folder: Path) -> tuple[dict[str, list[dict]], dict]:
    """Read one JSON file per collection plus meta.json."""
    if not (folder / "meta.json").exists():
        raise SystemExit(f"No data in {folder}. Run the generator in backend/data first.")
    collections = {}
    for name in DATA_COLLECTIONS:
        with open(folder / f"{name}.json", encoding="utf-8") as f:
            collections[name] = json.load(f)
    with open(folder / "meta.json", encoding="utf-8") as f:
        return collections, json.load(f)


def namespace_ids(collections: dict[str, list[dict]], city_id: str) -> None:
    """Prefix every id and id reference with '<city_id>:' (in place)."""
    prefix = f"{city_id}:"
    for docs in collections.values():
        for doc in docs:
            doc["_id"] = prefix + doc["_id"]
            for field in REFERENCE_FIELDS:
                if doc.get(field):
                    doc[field] = prefix + doc[field]


def to_datetime(value: Any) -> Any:
    """ISO date string -> datetime at midnight (MongoDB has no plain date type)."""
    if isinstance(value, str):
        return datetime.combine(date.fromisoformat(value), datetime.min.time())
    return value


def prepare(collections: dict[str, list[dict]], city_id: str) -> None:
    """Tag every document with its city and convert date strings (in place)."""
    for docs in collections.values():
        for doc in docs:
            doc["city_id"] = city_id
            for field in DATE_FIELDS:
                if field in doc:
                    doc[field] = to_datetime(doc[field])


def city_document(city_id: str, meta: dict, collections: dict[str, list[dict]],
                  extra: dict | None = None) -> dict:
    """The cities entry. The bbox is the extent of the imported junctions, which
    for a real city is the city boundary expanded by the margin."""
    nodes = collections["road_nodes"]
    lats = [n["lat"] for n in nodes]
    lngs = [n["lng"] for n in nodes]
    doc = {
        "_id": city_id,
        "name": city_id.title(),
        "state": "Gujarat",
        "center": list(meta["center"]),
        "bbox": [min(lats), min(lngs), max(lats), max(lngs)],  # south, west, north, east
        "margin_km": meta.get("margin_km", 0),
        "imported_at": datetime.now(timezone.utc),
        "node_count": len(nodes),
        "edge_count": len(collections["road_edges"]),
        "as_of": meta.get("as_of"),
        "synthetic": city_id == SYNTHETIC_CITY,
    }
    doc.update(extra or {})
    return doc


def create_indexes(db: Database) -> None:
    db.blood_units.create_index([("bank_id", 1), ("blood_group", 1), ("component", 1), ("status", 1)])
    db.blood_units.create_index("city_id")
    db.donors.create_index("blood_group")
    db.donors.create_index("node_id")
    db.donors.create_index([("city_id", 1), ("blood_group", 1)])
    db.road_edges.create_index("from")
    db.road_edges.create_index("to")
    db.road_edges.create_index([("city_id", 1), ("from", 1)])
    db.road_nodes.create_index("city_id")
    db.blood_banks.create_index("city_id")
    db.hospitals.create_index("city_id")
    db.users.create_index("phone", unique=True, sparse=True)
    db.users.create_index("email", unique=True, sparse=True)


def replace_city(db: Database, city_id: str, collections: dict[str, list[dict]], city_doc: dict) -> None:
    """Delete one city's documents and insert the new ones."""
    for name, docs in collections.items():
        db[name].delete_many({"city_id": city_id})
        for i in range(0, len(docs), BATCH):
            db[name].insert_many(docs[i:i + BATCH], ordered=False)
    db.cities.replace_one({"_id": city_id}, city_doc, upsert=True)


def remove_city(db: Database, city_id: str) -> None:
    for name in DATA_COLLECTIONS:
        db[name].delete_many({"city_id": city_id})
    db.cities.delete_one({"_id": city_id})


def seed(db: Database, source: str, reset: bool = False, with_accounts: bool = True) -> dict[str, int]:
    """Load data/<source> into db. Returns the number of documents per collection."""
    collections, meta = read_source(DATA_DIR / source)
    city_id = meta.get("city_id", SYNTHETIC_CITY)
    extra = {}
    if city_id == SYNTHETIC_CITY:
        extra = {"name": "Ahmedabad (synthetic grid)", "notes": "Development data on a fake road grid."}
    else:
        namespace_ids(collections, city_id)
        extra = {"name": meta.get("place", city_id).split(",")[0], "place": meta.get("place")}
    prepare(collections, city_id)

    if reset:
        for name in DATA_COLLECTIONS + EMPTY_COLLECTIONS:
            db[name].drop()
    elif city_id == SYNTHETIC_CITY:
        for other in db.cities.distinct("_id"):
            remove_city(db, other)
    else:
        remove_city(db, SYNTHETIC_CITY)

    existing = set(db.list_collection_names())
    for name in EMPTY_COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
    replace_city(db, city_id, collections, city_document(city_id, meta, collections, extra))
    create_indexes(db)
    if with_accounts:
        from db.accounts import seed_accounts
        seed_accounts(db)
    return {name: db[name].count_documents({"city_id": city_id}) for name in DATA_COLLECTIONS}


def main() -> None:
    settings = get_settings()
    p = argparse.ArgumentParser(description="Load generated RaktSetu data into MongoDB")
    p.add_argument("--source", default="output", help="folder inside backend/data (output or output_real)")
    p.add_argument("--reset", action="store_true", help="drop all collections first")
    p.add_argument("--mongo-uri", default=settings.mongo_uri)
    p.add_argument("--db", default=settings.db_name)
    args = p.parse_args()

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
    counts = seed(client[args.db], args.source, args.reset)
    _, meta = read_source(DATA_DIR / args.source)
    print(f"Seeded database '{args.db}' from data/{args.source}:")
    for name, count in counts.items():
        expected = meta["counts"][name]
        mark = "ok" if count == expected else f"MISMATCH (meta.json says {expected:,})"
        print(f"  {name:12s} {count:>9,}  {mark}")
    if any(counts[n] != meta["counts"][n] for n in counts):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
