"""A tiny hand-made city for tests that must run without MongoDB.

    A --1-- B --1-- C --1-- D --30-- F        (km of road)
                            |
                           1.2
                            |
                            E

Banks: BK1 at C, BK2 at E, BK3 at F (30 km beyond D: outside the 25 km radius from A).
"""

import copy
from datetime import date

TODAY = date(2026, 11, 13)

NODES = [
    {"_id": "A", "lat": 23.00, "lng": 72.50},
    {"_id": "B", "lat": 23.00, "lng": 72.51},
    {"_id": "C", "lat": 23.00, "lng": 72.52},
    {"_id": "D", "lat": 23.00, "lng": 72.53},
    {"_id": "E", "lat": 23.01, "lng": 72.53},
    {"_id": "F", "lat": 23.00, "lng": 72.80},
]
EDGES = [
    {"_id": "E1", "from": "A", "to": "B", "distance_km": 1.0, "road_type": "local", "travel_time_min": 3.0},
    {"_id": "E2", "from": "B", "to": "C", "distance_km": 1.0, "road_type": "local", "travel_time_min": 3.0},
    {"_id": "E3", "from": "C", "to": "D", "distance_km": 1.0, "road_type": "local", "travel_time_min": 3.0},
    {"_id": "E4", "from": "D", "to": "E", "distance_km": 1.2, "road_type": "local", "travel_time_min": 3.6},
    {"_id": "E5", "from": "D", "to": "F", "distance_km": 30.0, "road_type": "highway", "travel_time_min": 40.0},
]
CITY = {"_id": "synthetic", "name": "Tiny", "center": [23.0, 72.52], "bbox": [22.9, 72.4, 23.1, 72.9]}


def place(_id, node):
    lat, lng = next((n["lat"], n["lng"]) for n in NODES if n["_id"] == node)
    return {"_id": _id, "name": f"Place {_id}", "area": "Test", "node_id": node, "lat": lat, "lng": lng,
            "phone": "+91-00000-00001", "verified": True}


BANKS = [place("BK1", "C"), place("BK2", "E"), place("BK3", "F")]
HOSPITALS = [place("H1", "A")]


def unit(_id, bank, group, component, expires, status="available"):
    return {"_id": _id, "bank_id": bank, "blood_group": group, "component": component,
            "collected_on": "2026-11-01", "expires_on": expires, "status": status}


UNITS = [
    unit("U1", "BK1", "B+", "red_cells", "2026-11-20"),
    unit("U2", "BK1", "B+", "red_cells", "2026-11-15"),
    unit("U3", "BK1", "O-", "red_cells", "2026-11-14"),
    unit("U4", "BK2", "B+", "red_cells", "2026-11-30"),
    unit("U5", "BK2", "O+", "red_cells", "2026-11-18"),
    unit("U6", "BK2", "A+", "plasma", "2027-06-01"),
    unit("U7", "BK1", "A+", "red_cells", "2026-11-10"),               # past expiry
    unit("U8", "BK1", "AB-", "platelets", "2026-11-16", "reserved"),  # not available
    unit("U9", "BK3", "AB-", "platelets", "2026-11-16"),              # only in the far bank
]


def donor(_id, node, group, gender="M", age=30, last=None, eligible=True, available=True, consent=True):
    lat, lng = next((n["lat"], n["lng"]) for n in NODES if n["_id"] == node)
    return {"_id": _id, "name": f"Donor {_id}", "age": age, "gender": gender, "blood_group": group,
            "phone": f"+91-00000-1000{_id[-1]}", "node_id": node, "lat": lat, "lng": lng,
            "linked_bank_id": "BK1", "last_donation_date": last,
            "health_checklist": {"recent_illness": False, "recent_surgery": False,
                                 "on_medication": False, "chronic_condition": False},
            "eligible": eligible, "available": available, "contact_consent": consent}


DONORS = [
    donor("D1", "B", "AB-"),
    donor("D2", "A", "O-"),
    donor("D3", "D", "A-", consent=False),
    donor("D4", "C", "B-", available=False),
    donor("D5", "E", "AB-", eligible=False, last="2026-11-01"),
    donor("D6", "F", "O-"),           # too far from A
    donor("D7", "E", "B-", gender="F"),
]


def tiny_documents() -> dict:
    """Fresh copies, so a test can change them freely."""
    return copy.deepcopy({"cities": [CITY], "nodes": NODES, "edges": EDGES, "banks": BANKS,
                          "hospitals": HOSPITALS, "units": UNITS, "donors": DONORS})


def tiny_state():
    from modules.state import AppState, CityRoads

    docs = tiny_documents()
    roads = CityRoads("synthetic", docs["nodes"], docs["edges"])
    return AppState.build(cities=docs["cities"], banks=docs["banks"], hospitals=docs["hospitals"],
                          donors=docs["donors"], units=docs["units"], roads=[roads])
