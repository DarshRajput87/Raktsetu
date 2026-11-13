"""Demo scenarios: create (and undo) a blood shortage in one city.

    python -m data.scenario shortage --city ahmedabad --group B+ --component red_cells
    python -m data.scenario restore  --city ahmedabad

A shortage marks every available unit a patient of that group could receive
(all compatible donor groups, e.g. B+, B-, O+ and O- for B+ red cells) at
every bank of the city as issued. The search then finds no bank with stock and
shows matching donors instead. The units are tagged, so `restore` puts back
exactly those units and nothing else.

The API keeps its data in memory: restart it afterwards (a --reload server
reloads when any backend .py file is saved).
"""

import argparse

from pymongo import MongoClient

from config import get_settings
from modules.compatibility import BLOOD_GROUPS, COMPONENTS, compatible_groups

TAG = "demo_shortage"


def create_shortage(db, city_id: str, group: str, component: str) -> tuple[list[str], int]:
    """Returns (donor groups emptied, units taken out of stock)."""
    groups = compatible_groups(group, component)
    banks = db.blood_banks.distinct("_id", {"city_id": city_id})
    result = db.blood_units.update_many(
        {"bank_id": {"$in": banks}, "component": component, "blood_group": {"$in": groups},
         "status": "available"},
        {"$set": {"status": "issued", TAG: f"{group} {component}"}},
    )
    return groups, result.modified_count


def restore(db, city_id: str) -> int:
    """Put back every unit a shortage took out in this city. Returns how many."""
    result = db.blood_units.update_many(
        {"city_id": city_id, TAG: {"$exists": True}},
        {"$set": {"status": "available"}, "$unset": {TAG: ""}},
    )
    return result.modified_count


def main() -> None:
    settings = get_settings()
    p = argparse.ArgumentParser(description="Create or undo a demo blood shortage")
    p.add_argument("action", choices=["shortage", "restore"])
    p.add_argument("--city", required=True, help="city id, e.g. ahmedabad")
    p.add_argument("--group", choices=BLOOD_GROUPS, default="B+")
    p.add_argument("--component", choices=COMPONENTS, default="red_cells")
    p.add_argument("--mongo-uri", default=settings.mongo_uri)
    p.add_argument("--db", default=settings.db_name)
    args = p.parse_args()

    db = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)[args.db]
    if not db.cities.find_one({"_id": args.city}):
        raise SystemExit(f"Unknown city '{args.city}'. Loaded: {', '.join(db.cities.distinct('_id'))}")
    if args.action == "shortage":
        groups, count = create_shortage(db, args.city, args.group, args.component)
        print(f"Shortage in {args.city}: {count:,} {args.component} unit(s) of {', '.join(groups)} "
              f"marked as issued. A {args.group} {args.component} search now shows donors.")
    else:
        print(f"Restored {restore(db, args.city):,} unit(s) in {args.city}.")
    print("Restart the API so it reloads the stock.")


if __name__ == "__main__":
    main()
