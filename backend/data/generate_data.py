"""
RaktSetu - synthetic data generator (no ML).

Creates a fake city road network plus blood banks, hospitals, donors and
blood units placed on it, so the shortest-path search can be built and tested.

Output (JSON, one file per MongoDB collection) goes to ./output/:
    road_nodes.json   junctions: {_id, lat, lng}
    road_edges.json   roads (undirected): {_id, from, to, distance_km, road_type, travel_time_min}
    blood_banks.json  {_id, name, area, node_id, lat, lng, phone, ...}
    hospitals.json    {_id, name, area, node_id, lat, lng, phone, ...}
    donors.json       {_id, name, blood_group, node_id, linked_bank_id, eligible, ...}
    blood_units.json  {_id, bank_id, blood_group, component, collected_on, expires_on, status}

Usage:
    python generate_data.py                      # default sizes, writes ./output
    python generate_data.py --donors 5000 --banks 40 --seed 7
    python generate_data.py --mongo-uri mongodb://localhost:27017 --db raktsetu

Only the Python standard library is needed. pymongo is needed only with --mongo-uri.
All names are made up and all phone numbers use the invalid prefix +91-00000,
so no real person can be contacted by mistake.
"""

import argparse
import heapq
import json
import math
import os
import random
from datetime import date, timedelta

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

# Approximate blood group mix for India (used only to make the data realistic).
BLOOD_GROUPS = {
    "O+": 0.32, "B+": 0.32, "A+": 0.22, "AB+": 0.075,
    "O-": 0.02, "B-": 0.02, "A-": 0.015, "AB-": 0.01,
}

# Component -> shelf life in days (typical values).
COMPONENTS = {
    "whole_blood": 35,
    "red_cells": 42,
    "platelets": 5,
    "plasma": 365,
}

# Relative stock level of each component in a bank.
COMPONENT_WEIGHT = {"whole_blood": 0.30, "red_cells": 0.35, "platelets": 0.10, "plasma": 0.25}

FIRST_NAMES_M = ["Aarav", "Rohan", "Vikram", "Arjun", "Rahul", "Karan", "Siddharth", "Aditya",
                 "Manish", "Suresh", "Rajesh", "Amit", "Nikhil", "Pranav", "Harsh", "Yash",
                 "Kunal", "Deepak", "Sanjay", "Varun", "Imran", "Farhan", "Gurpreet", "Joseph"]
FIRST_NAMES_F = ["Priya", "Ananya", "Sneha", "Kavya", "Pooja", "Neha", "Riya", "Isha",
                 "Meera", "Divya", "Shruti", "Aisha", "Fatima", "Simran", "Anjali", "Lakshmi"]
LAST_NAMES = ["Sharma", "Patel", "Kumar", "Singh", "Reddy", "Nair", "Iyer", "Joshi", "Desai",
              "Kulkarni", "Gupta", "Mehta", "Shah", "Rao", "Khan", "Das", "Pillai", "Verma",
              "Chauhan", "Bose", "Menon", "Pawar", "Jadhav", "Fernandes"]
AREA_WORDS = ["Shanti", "Ganga", "Sagar", "Kamal", "Surya", "Nehru", "Gandhi", "Vasant", "Laxmi",
              "Indira", "Ashok", "Moti", "Hari", "Ram", "Shiv", "Sai", "Gokul", "Anand"]
AREA_SUFFIX = ["Nagar", "Puram", "Vihar", "Colony", "Park", "Wadi", "Peth", "Gaon", "Enclave"]

HEALTH_FLAGS = ["recent_illness", "recent_surgery", "on_medication", "chronic_condition"]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def pick_weighted(rng, weights):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def fake_phone(n):
    # +91-00000-xxxxx is not a valid Indian number: safe for fake data.
    return f"+91-00000-{n:05d}"


class UnionFind:
    def __init__(self, items):
        self.parent = {i: i for i in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[ra] = rb
        return True


# ----------------------------------------------------------------------------
# 1. Road network
# ----------------------------------------------------------------------------

def build_road_network(rng, center_lat, center_lng, size_km, spacing_km, drop_prob):
    """A jittered grid of junctions with some roads removed and a few highways.
    The graph is always connected."""
    n = int(size_km / spacing_km) + 1
    km_lat = 1 / 111.0
    km_lng = 1 / (111.32 * math.cos(math.radians(center_lat)))
    half = size_km / 2

    nodes = {}
    grid = {}
    for i in range(n):
        for j in range(n):
            y_km = -half + i * spacing_km + rng.uniform(-0.25, 0.25) * spacing_km
            x_km = -half + j * spacing_km + rng.uniform(-0.25, 0.25) * spacing_km
            node_id = f"N{i:03d}{j:03d}"
            nodes[node_id] = {
                "_id": node_id,
                "lat": round(center_lat + y_km * km_lat, 6),
                "lng": round(center_lng + x_km * km_lng, 6),
            }
            grid[(i, j)] = node_id

    # Highways: three rows and three columns across the city.
    highway_lines = {n // 4, n // 2, (3 * n) // 4}

    candidates = []
    for i in range(n):
        for j in range(n):
            a = grid[(i, j)]
            if j + 1 < n:
                candidates.append((a, grid[(i, j + 1)], "highway" if i in highway_lines else "local"))
            if i + 1 < n:
                candidates.append((a, grid[(i + 1, j)], "highway" if j in highway_lines else "local"))

    rng.shuffle(candidates)
    uf = UnionFind(nodes)
    kept, dropped = [], []
    for a, b, kind in candidates:
        if kind == "local" and rng.random() < drop_prob:
            dropped.append((a, b, kind))
        else:
            kept.append((a, b, kind))
            uf.union(a, b)
    # Re-add dropped roads only where needed to keep the city connected.
    for a, b, kind in dropped:
        if uf.union(a, b):
            kept.append((a, b, kind))

    edges = []
    for k, (a, b, kind) in enumerate(kept):
        na, nb = nodes[a], nodes[b]
        straight = haversine_km(na["lat"], na["lng"], nb["lat"], nb["lng"])
        road_km = round(straight * rng.uniform(1.0, 1.25), 3)  # roads are not perfectly straight
        speed = 45 if kind == "highway" else 22                 # km/h
        edges.append({
            "_id": f"E{k:06d}",
            "from": a,
            "to": b,
            "distance_km": road_km,
            "road_type": kind,
            "travel_time_min": round(road_km / speed * 60, 2),
        })
    return nodes, edges


def adjacency(edges):
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append((e["to"], e["distance_km"]))
        adj.setdefault(e["to"], []).append((e["from"], e["distance_km"]))
    return adj


def multi_source_nearest(adj, sources):
    """For every node, the nearest source (by road km). Used only to link donors
    to their nearest bank while generating data."""
    dist, owner, heap = {}, {}, []
    for node_id, src_id in sources:
        dist[node_id] = 0.0
        owner[node_id] = src_id
        heapq.heappush(heap, (0.0, node_id))
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                owner[v] = owner[u]
                heapq.heappush(heap, (nd, v))
    return owner, dist


# ----------------------------------------------------------------------------
# 2. Places (banks, hospitals) and donors
# ----------------------------------------------------------------------------

def make_area_name(rng):
    return f"{rng.choice(AREA_WORDS)} {rng.choice(AREA_SUFFIX)}"


def pick_node_near_center(rng, node_ids_grid, n, spread_cells):
    """Pick a grid node, most of them near the centre (normal distribution)."""
    c = n // 2
    while True:
        i = round(rng.gauss(c, spread_cells))
        j = round(rng.gauss(c, spread_cells))
        if 0 <= i < n and 0 <= j < n:
            return node_ids_grid[(i, j)]


def build_places(rng, nodes, count, prefix, kind, spread_cells, phone_start):
    n = int(math.isqrt(len(nodes)))
    grid = {(int(k[1:4]), int(k[4:7])): k for k in nodes}
    used, places = set(), []
    for k in range(count):
        node_id = pick_node_near_center(rng, grid, n, spread_cells)
        while node_id in used:
            node_id = pick_node_near_center(rng, grid, n, spread_cells)
        used.add(node_id)
        area = make_area_name(rng)
        name = f"{area} {kind}" if kind == "Blood Centre" else f"{area} {rng.choice(['General', 'City', 'Care', 'Life', 'Sunrise'])} Hospital"
        places.append({
            "_id": f"{prefix}{k + 1:03d}",
            "name": name,
            "area": area,
            "node_id": node_id,
            "lat": nodes[node_id]["lat"],
            "lng": nodes[node_id]["lng"],
            "phone": fake_phone(phone_start + k),
            "verified": True,
        })
    return places


def build_donors(rng, nodes, count, banks, adj, as_of, spread_cells):
    n = int(math.isqrt(len(nodes)))
    grid = {(int(k[1:4]), int(k[4:7])): k for k in nodes}
    owner, _ = multi_source_nearest(adj, [(b["node_id"], b["_id"]) for b in banks])
    donors = []
    for k in range(count):
        gender = "M" if rng.random() < 0.7 else "F"
        first = rng.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)
        age = rng.randint(18, 65)
        node_id = pick_node_near_center(rng, grid, n, spread_cells)

        if rng.random() < 0.35:
            last_donation = None  # never donated
        else:
            last_donation = as_of - timedelta(days=rng.randint(5, 500))

        flags = [f for f in HEALTH_FLAGS if rng.random() < 0.015]
        gap_needed = 90 if gender == "M" else 120
        gap_ok = last_donation is None or (as_of - last_donation).days >= gap_needed
        eligible = 18 <= age <= 65 and gap_ok and not flags

        donors.append({
            "_id": f"D{k + 1:05d}",
            "name": f"{first} {rng.choice(LAST_NAMES)}",
            "age": age,
            "gender": gender,
            "blood_group": pick_weighted(rng, BLOOD_GROUPS),
            "phone": fake_phone(10000 + k),
            "node_id": node_id,
            "lat": nodes[node_id]["lat"],
            "lng": nodes[node_id]["lng"],
            "linked_bank_id": owner.get(node_id),
            "last_donation_date": last_donation.isoformat() if last_donation else None,
            "health_checklist": {f: (f in flags) for f in HEALTH_FLAGS},
            "eligible": eligible,
            "available": rng.random() < 0.85,
            "contact_consent": rng.random() < 0.90,
        })
    return donors


# ----------------------------------------------------------------------------
# 3. Blood units (stock)
# ----------------------------------------------------------------------------

def build_units(rng, banks, as_of, mean_units_per_bank, empty_bank_share):
    units, k = [], 0
    for bank in banks:
        # Some banks are nearly empty, so the "no stock -> show donors" path can be tested.
        if rng.random() < empty_bank_share:
            size = rng.randint(0, 5)
        else:
            size = max(10, int(rng.gauss(mean_units_per_bank, mean_units_per_bank * 0.35)))
        for _ in range(size):
            group = pick_weighted(rng, BLOOD_GROUPS)
            comp = pick_weighted(rng, COMPONENT_WEIGHT)
            shelf = COMPONENTS[comp]
            # Collected some time in the past; ~10% of units are already past expiry.
            age_days = rng.randint(0, int(shelf * 1.1))
            collected = as_of - timedelta(days=age_days)
            expires = collected + timedelta(days=shelf)
            if expires < as_of:
                status = "expired"
            else:
                status = rng.choices(["available", "reserved", "issued"], weights=[0.85, 0.05, 0.10])[0]
            k += 1
            units.append({
                "_id": f"U{k:07d}",
                "bank_id": bank["_id"],
                "blood_group": group,
                "component": comp,
                "collected_on": collected.isoformat(),
                "expires_on": expires.isoformat(),
                "status": status,
            })
    return units


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Generate synthetic RaktSetu data")
    p.add_argument("--center-lat", type=float, default=23.0225, help="city centre latitude (default: Ahmedabad)")
    p.add_argument("--center-lng", type=float, default=72.5714, help="city centre longitude (default: Ahmedabad)")
    p.add_argument("--size-km", type=float, default=60, help="width of the square city area in km")
    p.add_argument("--spacing-km", type=float, default=1.0, help="distance between junctions")
    p.add_argument("--drop-prob", type=float, default=0.10, help="share of local roads removed")
    p.add_argument("--banks", type=int, default=30)
    p.add_argument("--hospitals", type=int, default=40)
    p.add_argument("--donors", type=int, default=3000)
    p.add_argument("--units-per-bank", type=int, default=120)
    p.add_argument("--empty-bank-share", type=float, default=0.15)
    p.add_argument("--as-of", type=str, default=date.today().isoformat(), help="'today' for the data, YYYY-MM-DD")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
    p.add_argument("--mongo-uri", type=str, default=None, help="also insert into MongoDB")
    p.add_argument("--db", type=str, default="raktsetu")
    args = p.parse_args()

    rng = random.Random(args.seed)
    as_of = date.fromisoformat(args.as_of)
    n_cells = int(args.size_km / args.spacing_km) + 1

    nodes, edges = build_road_network(rng, args.center_lat, args.center_lng,
                                      args.size_km, args.spacing_km, args.drop_prob)
    adj = adjacency(edges)

    banks = build_places(rng, nodes, args.banks, "B", "Blood Centre", n_cells / 6, 100)
    hospitals = build_places(rng, nodes, args.hospitals, "H", "Hospital", n_cells / 6, 500)
    for b in banks:
        b["admin_user_id"] = None
    donors = build_donors(rng, nodes, args.donors, banks, adj, as_of, n_cells / 4)
    units = build_units(rng, banks, as_of, args.units_per_bank, args.empty_bank_share)

    collections = {
        "road_nodes": list(nodes.values()),
        "road_edges": edges,
        "blood_banks": banks,
        "hospitals": hospitals,
        "donors": donors,
        "blood_units": units,
    }

    os.makedirs(args.out, exist_ok=True)
    for name, docs in collections.items():
        with open(os.path.join(args.out, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=1)

    meta = {
        "as_of": as_of.isoformat(),
        "seed": args.seed,
        "center": [args.center_lat, args.center_lng],
        "size_km": args.size_km,
        "counts": {k: len(v) for k, v in collections.items()},
    }
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)

    print("Generated data in", args.out)
    for k, v in meta["counts"].items():
        print(f"  {k:12s} {v:>8,}")
    avail = sum(1 for u in units if u["status"] == "available")
    elig = sum(1 for d in donors if d["eligible"] and d["available"] and d["contact_consent"])
    print(f"  available units: {avail:,} | searchable donors (eligible + available + consent): {elig:,}")

    if args.mongo_uri:
        from pymongo import MongoClient
        db = MongoClient(args.mongo_uri)[args.db]
        for name, docs in collections.items():
            db[name].drop()
            if docs:
                db[name].insert_many(docs)
        db["blood_units"].create_index([("bank_id", 1), ("blood_group", 1), ("status", 1)])
        db["donors"].create_index([("blood_group", 1)])
        print(f"Inserted into MongoDB database '{args.db}'")


if __name__ == "__main__":
    main()
