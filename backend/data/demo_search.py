"""
RaktSetu - demo search on the generated data (Case 1 flow).

Shows the generated data works with shortest path:
  1. snap the user's location to the nearest road junction
  2. find compatible blood groups (hash map)
  3. Dijkstra from the user, stopping at 25 km of road distance
  4. banks with available, non-expired compatible stock -> nearest first + route
  5. no bank found -> eligible, available, consenting donors within 25 km

This uses Python's heapq so it runs on its own. In the real project,
replace it with your own MinHeap / Graph / Dijkstra classes from backend/core.

Usage:
    python demo_search.py --group B+ --component red_cells
    python demo_search.py --group AB- --component platelets --lat 23.2021 --lng 72.7706
"""

import argparse
import heapq
import json
import math
import os
from datetime import date

# Recipient group -> groups it can safely receive (red cells / whole blood).
COMPATIBLE = {
    "O-": ["O-"],
    "O+": ["O+", "O-"],
    "A-": ["A-", "O-"],
    "A+": ["A+", "A-", "O+", "O-"],
    "B-": ["B-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
}


def load(folder, name):
    with open(os.path.join(folder, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_node(nodes, lat, lng):
    return min(nodes, key=lambda n: haversine_km(lat, lng, n["lat"], n["lng"]))["_id"]


def dijkstra_within(adj, src, max_km):
    """Shortest road distance from src to every node within max_km."""
    dist, prev, heap = {src: 0.0}, {}, [(0.0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        if d > max_km:          # cutoff: everything after this is farther
            break
        for v, w in adj[u]:
            nd = d + w
            if nd <= max_km and nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    return dist, prev


def build_path(prev, src, dst):
    stack, node = [], dst
    while node != src:
        stack.append(node)
        node = prev[node]
    stack.append(src)
    return stack[::-1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--group", default="B+", choices=list(COMPATIBLE))
    p.add_argument("--component", default="red_cells",
                   choices=["whole_blood", "red_cells", "platelets", "plasma"])
    p.add_argument("--lat", type=float, default=None, help="user latitude (default: city centre)")
    p.add_argument("--lng", type=float, default=None)
    p.add_argument("--radius", type=float, default=25.0)
    p.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
    args = p.parse_args()

    meta = load(args.data, "meta")
    nodes = load(args.data, "road_nodes")
    edges = load(args.data, "road_edges")
    banks = {b["node_id"]: b for b in load(args.data, "blood_banks")}
    units = load(args.data, "blood_units")
    donors = load(args.data, "donors")
    today = date.fromisoformat(meta["as_of"])

    adj = {n["_id"]: [] for n in nodes}
    for e in edges:
        adj[e["from"]].append((e["to"], e["distance_km"]))
        if not e.get("oneway", False):          # one-way roads: only from -> to
            adj[e["to"]].append((e["from"], e["distance_km"]))

    lat = args.lat if args.lat is not None else meta["center"][0]
    lng = args.lng if args.lng is not None else meta["center"][1]
    src = nearest_node(nodes, lat, lng)
    ok_groups = set(COMPATIBLE[args.group])

    # Stock lookup: bank_id -> count of usable units (hash map).
    stock = {}
    for u in units:
        if (u["status"] == "available" and u["component"] == args.component
                and u["blood_group"] in ok_groups
                and date.fromisoformat(u["expires_on"]) >= today):
            stock[u["bank_id"]] = stock.get(u["bank_id"], 0) + 1

    dist, prev = dijkstra_within(adj, src, args.radius)

    print(f"Search: {args.group} {args.component} from ({lat:.4f}, {lng:.4f}) -> junction {src}")
    print(f"Compatible groups: {', '.join(COMPATIBLE[args.group])}")
    print(f"Junctions reached within {args.radius} km: {len(dist):,}\n")

    found = sorted(
        (dist[node], bank) for node, bank in banks.items()
        if node in dist and stock.get(bank["_id"], 0) > 0
    )

    if found:
        print(f"{len(found)} blood bank(s) with stock, nearest first:")
        for d, bank in found[:5]:
            print(f"  {d:6.2f} km  {bank['name']:<32s} units: {stock[bank['_id']]:>3}  {bank['phone']}")
        d0, nearest = found[0]
        path = build_path(prev, src, nearest["node_id"])
        print(f"\nRoute to {nearest['name']}: {len(path) - 1} road segments, {d0:.2f} km")
        print("  " + " -> ".join(path[:6]) + (" -> ... -> " + path[-1] if len(path) > 6 else ""))
        return

    print(f"No blood bank with stock within {args.radius} km. Matching donors:")
    matches = sorted(
        (dist[d["node_id"]], d) for d in donors
        if d["node_id"] in dist and d["blood_group"] in ok_groups
        and d["eligible"] and d["available"] and d["contact_consent"]
    )
    if not matches:
        print("  None found. Try a larger --radius.")
    for dkm, d in matches[:10]:
        print(f"  {dkm:6.2f} km  {d['name']:<20s} {d['blood_group']:<4s} {d['phone']}")


if __name__ == "__main__":
    main()
