import heapq
import random
from datetime import date

import pytest

from modules.cities import CityNotSupported
from modules.geo import haversine_km
from modules.compatibility import BLOOD_GROUPS, COMPONENTS, compatible_groups
from modules.search import nearest_banks, public_name, route_to_bank, search_blood
from tests.fixtures import TODAY

CENTRE = (23.0225, 72.5714)


# --- tiny hand-made city -------------------------------------------------------

def test_banks_nearest_first_with_route(tiny):
    result = search_blood(tiny, 23.0, 72.50, "B+", "red_cells", 25, TODAY)
    assert result.start_node == "A"
    assert [(b.bank_id, b.distance_km) for b in result.banks] == [("BK1", 2.0), ("BK2", 4.2)]
    assert result.banks[0].units_by_group == {"B+": 2, "O-": 1} and result.banks[0].units == 3
    assert result.banks[0].est_travel_min == 6.0
    assert result.route == [[23.0, 72.50], [23.0, 72.51], [23.0, 72.52]]
    assert result.route_bank_id == "BK1" and result.donors == []


def test_expired_and_reserved_units_do_not_count(tiny):
    # A+ red cells: BK1 only has an expired A+ unit, but its O- unit is compatible.
    result = search_blood(tiny, 23.0, 72.50, "A+", "red_cells", 25, TODAY)
    assert result.banks[0].units_by_group == {"O-": 1}
    # AB- platelets: BK1's unit is reserved and BK3 is beyond the radius.
    result = search_blood(tiny, 23.0, 72.50, "AB-", "platelets", 25, TODAY)
    assert result.banks == [] and result.route == []


def test_donor_fallback_filters_and_orders(tiny):
    result = search_blood(tiny, 23.0, 72.50, "AB-", "platelets", 25, TODAY)
    # D2 (O-, 0 km), D1 (AB-, 1 km), D7 (B-, 4.2 km). Left out: D3 no consent,
    # D4 unavailable, D5 not eligible, D6 beyond the radius.
    assert [(d.donor_id, d.distance_km) for d in result.donors] == [("D2", 0.0), ("D1", 1.0), ("D7", 4.2)]
    assert not hasattr(result.donors[0], "phone")


def test_wider_radius_reaches_the_far_bank(tiny):
    result = search_blood(tiny, 23.0, 72.50, "AB-", "platelets", 50, TODAY)
    assert [(b.bank_id, b.distance_km) for b in result.banks] == [("BK3", 33.0)]


def test_unverified_and_excluded_banks_are_skipped(tiny):
    tiny.banks_by_id["BK1"]["verified"] = False
    assert [b.bank_id for b in search_blood(tiny, 23.0, 72.50, "B+", "red_cells", 25, TODAY).banks] == ["BK2"]
    result = search_blood(tiny, 23.0, 72.50, "B+", "red_cells", 25, TODAY, exclude_banks=["BK2"])
    assert result.banks == []


def test_trace_lists_visits_in_order(tiny):
    result = search_blood(tiny, 23.0, 72.50, "B+", "red_cells", 25, TODAY, trace=True)
    assert [t["node"] for t in result.trace] == ["A", "B", "C", "D", "E"]
    assert result.trace[0] == {"node": "A", "lat": 23.0, "lng": 72.5, "dist_km": 0.0, "parent": None}
    assert result.trace[2]["parent"] == "B"
    assert [(b["bank_id"], b["has_stock"]) for b in result.banks_reached] == [("BK1", True), ("BK2", True)]


def test_location_outside_every_city(tiny):
    with pytest.raises(CityNotSupported, match="not available in this area yet"):
        search_blood(tiny, 28.61, 77.21, "B+", "red_cells", 25, TODAY)


def test_route_to_bank_and_nearest_banks(tiny):
    route = route_to_bank(tiny, 23.0, 72.50, "BK2")
    assert route.distance_km == 4.2 and route.est_travel_min == 12.6 and len(route.route) == 5
    assert [(b["_id"], km) for b, km in nearest_banks(tiny, 23.0, 72.50, k=2)] == [("BK1", 2.0), ("BK2", 4.2)]
    assert len(nearest_banks(tiny, 23.0, 72.50, k=5)) == 3


def test_public_name():
    assert public_name("Rohan Sharma") == "Rohan S."
    assert public_name("Rohan") == "Rohan"


# --- the three demo cases on the generated city (seed 42, as of 2026-11-13) -----

def test_demo_case_banks_found_at_city_centre(generated_state, generated_today):
    result = search_blood(generated_state, *CENTRE, "B+", "red_cells", 25, generated_today)
    assert result.start_node == "N030030"
    assert len(result.banks) == 22
    assert [(b.name, round(b.distance_km, 2), b.units) for b in result.banks[:3]] == [
        ("Hari Nagar Blood Centre", 1.94, 21),
        ("Kamal Nagar Blood Centre", 7.12, 19),
        ("Gokul Wadi Blood Centre", 7.17, 21),
    ]
    assert len(result.route) == 3 and result.donors == []   # 2 road segments
    assert result.junctions_visited == 1108


def test_demo_case_one_far_bank(generated_state, generated_today):
    result = search_blood(generated_state, 23.2021, 72.7706, "AB-", "platelets", 25, generated_today)
    assert [(b.name, round(b.distance_km, 2), b.units) for b in result.banks] == [
        ("Gandhi Park Blood Centre", 19.93, 2)]
    assert len(result.route) == 20   # 19 road segments


def test_demo_case_donor_fallback(generated_state, generated_today):
    result = search_blood(generated_state, 22.8021, 72.3275, "O-", "platelets", 25, generated_today)
    assert result.banks == [] and result.route == []
    assert [(d.name, round(d.distance_km, 2)) for d in result.donors] == [
        ("Vikram S.", 8.60), ("Amit P.", 18.18), ("Imran P.", 18.83), ("Aditya M.", 21.65),
        ("Aditya G.", 22.97)]


# --- our search against a reference written with heapq (as in data/demo_search.py)

def reference_search(docs, lat, lng, group, component, radius, today):
    nodes, groups = docs["road_nodes"], set(compatible_groups(group, component))
    adj = {n["_id"]: [] for n in nodes}
    for e in docs["road_edges"]:
        adj[e["from"]].append((e["to"], e["distance_km"]))
        adj[e["to"]].append((e["from"], e["distance_km"]))
    src = min(nodes, key=lambda n: haversine_km(lat, lng, n["lat"], n["lng"]))["_id"]
    dist, heap = {src: 0.0}, [(0.0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd <= radius and nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    stock = {}
    for u in docs["blood_units"]:
        if (u["status"] == "available" and u["component"] == component and u["blood_group"] in groups
                and date.fromisoformat(u["expires_on"]) >= today):
            stock[u["bank_id"]] = stock.get(u["bank_id"], 0) + 1
    banks = sorted((round(dist[b["node_id"]], 3), b["_id"], stock[b["_id"]]) for b in docs["blood_banks"]
                   if b["node_id"] in dist and stock.get(b["_id"]))
    donors = sorted((round(dist[d["node_id"]], 3), d["_id"]) for d in docs["donors"]
                    if d["node_id"] in dist and d["blood_group"] in groups
                    and d["eligible"] and d["available"] and d["contact_consent"])
    return banks, donors


def test_matches_reference_on_random_searches(generated_state, generated_docs, generated_today):
    rng = random.Random(7)
    fallbacks = 0
    for _ in range(40):
        lat = CENTRE[0] + rng.uniform(-0.26, 0.26)
        lng = CENTRE[1] + rng.uniform(-0.28, 0.28)
        group, component = rng.choice(BLOOD_GROUPS), rng.choice(COMPONENTS)
        radius = rng.choice([5, 10, 25])
        banks, donors = reference_search(generated_docs, lat, lng, group, component, radius, generated_today)
        result = search_blood(generated_state, lat, lng, group, component, radius, generated_today)
        assert sorted((b.distance_km, b.bank_id, b.units) for b in result.banks) == banks
        assert [b.distance_km for b in result.banks] == sorted(b.distance_km for b in result.banks)
        if not banks:
            fallbacks += 1
            assert sorted((d.distance_km, d.donor_id) for d in result.donors) == donors[:50]
    assert fallbacks > 0   # the fallback path was really exercised
