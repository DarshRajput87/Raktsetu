"""
RaktSetu - fake data on REAL roads (OpenStreetMap).

Downloads a city's real drivable road network (city area + a margin, default 25 km),
then places fake blood banks, hospitals and donors on real road junctions, so every
place has a real lat/lng on a real street. Blood stock is generated per bank.

Output (same format as generate_data.py, plus city_id and one-way roads) in ./output_real/:
    road_nodes.json, road_edges.json, blood_banks.json, hospitals.json,
    donors.json, blood_units.json, meta.json

Run on your own computer (needs internet the first time):
    pip install osmnx
    python generate_real_data.py                                   # Ahmedabad (+25 km)
    python generate_real_data.py --place "Surat, Gujarat, India" --city-id surat
    python generate_real_data.py --mongo-uri mongodb://localhost:27017

The downloaded roads are cached in ./downloads/<city_id>.graphml, so later runs
(e.g. with a new --seed) work offline:
    python generate_real_data.py --graphml downloads/ahmedabad.graphml

The places and stock are FAKE: names are made up and phone numbers use the invalid
prefix +91-00000. Only the road network and coordinates are real.
"""

import argparse
import json
import math
import os
import random
import time
from datetime import date

from generate_data import (
    BLOOD_GROUPS, HEALTH_FLAGS, FIRST_NAMES_F, FIRST_NAMES_M, LAST_NAMES,
    build_units, fake_phone, haversine_km, make_area_name, multi_source_nearest, pick_weighted,
)

HERE = os.path.dirname(os.path.abspath(__file__))

# Typical speeds (km/h) by OSM road type, for travel time.
SPEED_KMH = {
    "motorway": 60, "trunk": 55, "primary": 40, "secondary": 35, "tertiary": 30,
    "unclassified": 25, "residential": 20, "living_street": 10, "service": 15,
}


# ----------------------------------------------------------------------------
# 1. Get the real road network
# ----------------------------------------------------------------------------

def expand_bbox(south, west, north, east, margin_km):
    mid_lat = (south + north) / 2
    dlat = margin_km / 111.0
    dlng = margin_km / (111.32 * math.cos(math.radians(mid_lat)))
    return south - dlat, west - dlng, north + dlat, east + dlng


def download_graph(place, margin_km, cache_path):
    import osmnx as ox  # only needed for downloading

    print(f"Finding the boundary of '{place}' ...")
    gdf = ox.geocode_to_gdf(place)
    west, south, east, north = gdf.total_bounds
    s, w, n, e = expand_bbox(south, west, north, east, margin_km)
    print(f"Downloading drivable roads for the city + {margin_km} km "
          f"(bbox S{s:.3f} W{w:.3f} N{n:.3f} E{e:.3f}). This can take a few minutes ...")
    t0 = time.time()
    try:  # OSMnx 2.x
        G = ox.graph_from_bbox(bbox=(w, s, e, n), network_type="drive")
    except TypeError:  # OSMnx 1.x
        G = ox.graph_from_bbox(n, s, e, w, network_type="drive")
    try:
        G = ox.truncate.largest_component(G, strongly=False)
    except AttributeError:
        G = ox.utils_graph.get_largest_component(G, strongly=False)
    print(f"Downloaded in {time.time() - t0:.0f} s")

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    ox.save_graphml(G, cache_path)
    print(f"Saved road cache to {cache_path}")
    center = (gdf.geometry.iloc[0].centroid.y, gdf.geometry.iloc[0].centroid.x)
    return G, center


def load_graph(path):
    try:
        import osmnx as ox
        return ox.load_graphml(path)
    except ImportError:
        import networkx as nx
        return nx.read_graphml(path)


def to_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def first_highway(v):
    if isinstance(v, list):
        v = v[0]
    v = str(v).strip("[]'\" ").split(",")[0].strip("'\" ")
    return v.replace("_link", "")


def convert_graph(G, city_id):
    """OSMnx MultiDiGraph -> our road_nodes / road_edges documents.
    Two-way roads become one undirected edge; one-way roads stay directed."""
    nodes = {}
    for nid, d in G.nodes(data=True):
        _id = f"osm_{nid}"
        nodes[_id] = {"_id": _id, "city_id": city_id,
                      "lat": round(float(d["y"]), 6), "lng": round(float(d["x"]), 6)}

    best = {}  # (from, to, oneway) -> shortest parallel edge
    for u, v, d in G.edges(data=True):
        a, b = f"osm_{u}", f"osm_{v}"
        if a == b:
            continue
        oneway = to_bool(d.get("oneway", False))
        if "length" in d:
            km = float(d["length"]) / 1000.0
        else:
            km = haversine_km(nodes[a]["lat"], nodes[a]["lng"], nodes[b]["lat"], nodes[b]["lng"])
        road_type = first_highway(d.get("highway", "unclassified"))
        key = (a, b, True) if oneway else (min(a, b), max(a, b), False)
        if key not in best or km < best[key][0]:
            best[key] = (km, road_type)

    edges = []
    for k, ((a, b, oneway), (km, road_type)) in enumerate(best.items()):
        speed = SPEED_KMH.get(road_type, 25)
        edges.append({
            "_id": f"E{k:07d}", "city_id": city_id, "from": a, "to": b,
            "distance_km": round(km, 4), "road_type": road_type, "oneway": oneway,
            "travel_time_min": round(km / speed * 60, 2),
        })
    return nodes, edges


def undirected_adjacency(edges):
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append((e["to"], e["distance_km"]))
        adj.setdefault(e["to"], []).append((e["from"], e["distance_km"]))
    return adj


# ----------------------------------------------------------------------------
# 2. Place fake banks, hospitals and donors on real junctions
# ----------------------------------------------------------------------------

def weighted_node_sampler(rng, nodes, center, scale_km, main_roads_only=None):
    """Sample junctions, more often near the city centre: weight = exp(-distance / scale)."""
    ids, weights = [], []
    for n in nodes.values():
        if main_roads_only is not None and n["_id"] not in main_roads_only:
            continue
        d = haversine_km(center[0], center[1], n["lat"], n["lng"])
        ids.append(n["_id"])
        weights.append(math.exp(-d / scale_km))

    def sample(k, exclude=()):
        chosen, excluded = [], set(exclude)
        while len(chosen) < k:
            node = rng.choices(ids, weights=weights, k=1)[0]
            if node not in excluded:
                chosen.append(node)
                excluded.add(node)
        return chosen
    return sample


def build_places_real(rng, nodes, node_ids, prefix, kind, city_id, phone_start):
    places, used_areas = [], set()
    for k, node_id in enumerate(node_ids):
        area = make_area_name(rng)
        while area in used_areas:  # unique names within a kind
            area = make_area_name(rng)
        used_areas.add(area)
        if kind == "bank":
            name = f"{area} Blood Centre"
        else:
            name = f"{area} {rng.choice(['General', 'City', 'Care', 'Life', 'Sunrise'])} Hospital"
        places.append({
            "_id": f"{prefix}{k + 1:03d}", "city_id": city_id, "name": name, "area": area,
            "node_id": node_id, "lat": nodes[node_id]["lat"], "lng": nodes[node_id]["lng"],
            "phone": fake_phone(phone_start + k), "verified": True,
        })
    return places


def build_donors_real(rng, nodes, node_ids, banks, adj, as_of, city_id):
    owner, _ = multi_source_nearest(adj, [(b["node_id"], b["_id"]) for b in banks])
    donors = []
    for k, node_id in enumerate(node_ids):
        gender = "M" if rng.random() < 0.7 else "F"
        first = rng.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)
        age = rng.randint(18, 65)
        last = None if rng.random() < 0.35 else as_of.fromordinal(as_of.toordinal() - rng.randint(5, 500))
        flags = [f for f in HEALTH_FLAGS if rng.random() < 0.015]
        gap_ok = last is None or (as_of - last).days >= (90 if gender == "M" else 120)
        donors.append({
            "_id": f"D{k + 1:05d}", "city_id": city_id,
            "name": f"{first} {rng.choice(LAST_NAMES)}", "age": age, "gender": gender,
            "blood_group": pick_weighted(rng, BLOOD_GROUPS), "phone": fake_phone(10000 + k),
            "node_id": node_id, "lat": nodes[node_id]["lat"], "lng": nodes[node_id]["lng"],
            "linked_bank_id": owner.get(node_id),
            "last_donation_date": last.isoformat() if last else None,
            "health_checklist": {f: (f in flags) for f in HEALTH_FLAGS},
            "eligible": 18 <= age <= 65 and gap_ok and not flags,
            "available": rng.random() < 0.85,
            "contact_consent": rng.random() < 0.90,
        })
    return donors


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Fake RaktSetu data on real OpenStreetMap roads")
    p.add_argument("--place", default="Ahmedabad, Gujarat, India")
    p.add_argument("--city-id", default="ahmedabad")
    p.add_argument("--margin-km", type=float, default=25)
    p.add_argument("--graphml", default=None, help="use a saved road file instead of downloading")
    p.add_argument("--center-lat", type=float, default=None, help="override the city centre")
    p.add_argument("--center-lng", type=float, default=None)
    p.add_argument("--banks", type=int, default=40)
    p.add_argument("--hospitals", type=int, default=60)
    p.add_argument("--donors", type=int, default=5000)
    p.add_argument("--units-per-bank", type=int, default=120)
    p.add_argument("--empty-bank-share", type=float, default=0.15)
    p.add_argument("--as-of", default=date.today().isoformat())
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default=os.path.join(HERE, "output_real"))
    p.add_argument("--mongo-uri", default=None)
    p.add_argument("--db", default="raktsetu")
    args = p.parse_args()

    rng = random.Random(args.seed)
    as_of = date.fromisoformat(args.as_of)
    cache = os.path.join(HERE, "downloads", f"{args.city_id}.graphml")

    if args.graphml or os.path.exists(cache):
        path = args.graphml or cache
        print(f"Loading roads from {path}")
        G, center = load_graph(path), None
    else:
        G, center = download_graph(args.place, args.margin_km, cache)

    nodes, edges = convert_graph(G, args.city_id)
    if args.center_lat is not None:
        center = (args.center_lat, args.center_lng)
    if center is None:  # centre of all junctions
        center = (sum(n["lat"] for n in nodes.values()) / len(nodes),
                  sum(n["lng"] for n in nodes.values()) / len(nodes))
    adj = undirected_adjacency(edges)

    # Banks and hospitals sit on bigger roads when possible (more realistic).
    big = {"motorway", "trunk", "primary", "secondary", "tertiary"}
    on_big_roads = {e["from"] for e in edges if e["road_type"] in big} | \
                   {e["to"] for e in edges if e["road_type"] in big}
    if len(on_big_roads) < (args.banks + args.hospitals) * 3:
        on_big_roads = None

    place_sampler = weighted_node_sampler(rng, nodes, center, 8.0, on_big_roads)
    bank_nodes = place_sampler(args.banks)
    hosp_nodes = place_sampler(args.hospitals, exclude=bank_nodes)
    donor_sampler = weighted_node_sampler(rng, nodes, center, 12.0)
    donor_nodes = [donor_sampler(1)[0] for _ in range(args.donors)]  # several donors may share a junction

    banks = build_places_real(rng, nodes, bank_nodes, "B", "bank", args.city_id, 100)
    for b in banks:
        b["admin_user_id"] = None
    hospitals = build_places_real(rng, nodes, hosp_nodes, "H", "hospital", args.city_id, 500)
    donors = build_donors_real(rng, nodes, donor_nodes, banks, adj, as_of, args.city_id)
    units = build_units(rng, banks, as_of, args.units_per_bank, args.empty_bank_share)

    collections = {
        "road_nodes": list(nodes.values()), "road_edges": edges, "blood_banks": banks,
        "hospitals": hospitals, "donors": donors, "blood_units": units,
    }
    os.makedirs(args.out, exist_ok=True)
    for name, docs in collections.items():
        with open(os.path.join(args.out, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(docs, f)
    meta = {
        "as_of": as_of.isoformat(), "seed": args.seed, "city_id": args.city_id,
        "place": args.place, "margin_km": args.margin_km, "center": [center[0], center[1]],
        "road_source": "OpenStreetMap (c) OpenStreetMap contributors, ODbL",
        "counts": {k: len(v) for k, v in collections.items()},
    }
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)

    print("Generated data in", args.out)
    for k, v in meta["counts"].items():
        print(f"  {k:12s} {v:>9,}")
    print(f"  one-way road segments: {sum(1 for e in edges if e['oneway']):,}")

    if args.mongo_uri:
        from pymongo import MongoClient
        db = MongoClient(args.mongo_uri)[args.db]
        for name, docs in collections.items():
            db[name].delete_many({"city_id": args.city_id})
            for i in range(0, len(docs), 10000):
                db[name].insert_many(docs[i:i + 10000])
            db[name].create_index("city_id")
        print(f"Inserted city '{args.city_id}' into MongoDB database '{args.db}'")


if __name__ == "__main__":
    main()
