"""Public endpoints: search, route, banks, cities."""

import time

CENTRE = {"lat": 23.0225, "lng": 72.5714}
OUTSKIRTS = {"lat": 22.8021, "lng": 72.3275}


async def test_health_and_docs(api):
    assert (await api.client.get("/health")).json() == {"status": "ok"}
    paths = (await api.client.get("/openapi.json")).json()["paths"]
    for path in ["/search", "/route", "/banks", "/banks/{bank_id}", "/donors/{donor_id}/contact",
                 "/hospital/requests", "/hospital/requests/{request_id}", "/donors/register", "/donors/me",
                 "/donors/me/suggested-banks", "/donors/{donor_id}/report", "/bank/stock", "/bank/units",
                 "/bank/units/issue", "/bank/requests", "/bank/requests/{request_id}", "/bank/transactions",
                 "/bank/undo", "/admin/hospitals/{hospital_id}/verify", "/admin/banks/{bank_id}/verify",
                 "/admin/reports", "/auth/otp/send", "/auth/otp/verify"]:
        assert path in paths, path


async def test_search_finds_banks_with_a_route(api):
    response = await api.client.get("/search", params={"group": "B+", "component": "red_cells", **CENTRE})
    body = response.json()
    assert response.status_code == 200 and body["city_id"] == "synthetic"
    assert len(body["banks"]) == 22 and body["donors"] == []
    nearest = body["banks"][0]
    assert nearest["name"] == "Hari Nagar Blood Centre" and round(nearest["distance_km"], 2) == 1.94
    assert nearest["units"] == 21 and nearest["phone"].startswith("+91-00000")
    assert [b["distance_km"] for b in body["banks"]] == sorted(b["distance_km"] for b in body["banks"])
    assert len(body["route"]) == 3 and body["route_bank_id"] == nearest["bank_id"]
    assert "trace" not in body


async def test_search_falls_back_to_donors_without_phone_numbers(api):
    response = await api.client.get("/search", params={"group": "O-", "component": "platelets", **OUTSKIRTS})
    body = response.json()
    assert body["banks"] == [] and body["route"] == []
    assert [(d["name"], round(d["distance_km"], 2)) for d in body["donors"]][:2] == [
        ("Vikram S.", 8.60), ("Amit P.", 18.18)]
    assert all("phone" not in donor for donor in body["donors"])
    assert "+91-00000" not in response.text          # no phone number anywhere in the response


async def test_search_radius_and_trace(api):
    params = {"group": "AB-", "component": "platelets", "lat": 23.2021, "lng": 72.7706}
    body = (await api.client.get("/search", params=params)).json()
    assert [(b["name"], round(b["distance_km"], 2)) for b in body["banks"]] == [("Gandhi Park Blood Centre", 19.93)]
    narrow = (await api.client.get("/search", params={**params, "radius": 10})).json()
    assert narrow["banks"] == [] and narrow["radius_km"] == 10

    traced = (await api.client.get("/search", params={**params, "trace": "true"})).json()
    trace = traced["trace"]
    assert len(trace) == traced["junctions_visited"] == 756
    assert trace[0]["dist_km"] == 0 and trace[0]["parent"] is None
    assert [t["dist_km"] for t in trace] == sorted(t["dist_km"] for t in trace)      # visit order
    assert set(trace[5]) == {"node", "lat", "lng", "dist_km", "parent"}
    with_stock = [b for b in traced["banks_reached"] if b["has_stock"]]
    assert len(with_stock) == 1 and len(traced["banks_reached"]) > 1
    assert traced["route"][-1] == [with_stock[0]["lat"], with_stock[0]["lng"]]


async def test_search_errors(api):
    delhi = await api.client.get("/search", params={"group": "B+", "component": "red_cells",
                                                    "lat": 28.61, "lng": 77.21})
    assert delhi.status_code == 404
    assert delhi.json() == {"error": {"code": "area_not_supported",
                                      "message": "RaktSetu is not available in this area yet"}}
    bad = await api.client.get("/search", params={"group": "Z+", "component": "red_cells", **CENTRE})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    missing = await api.client.get("/search", params={"group": "B+", "component": "red_cells"})
    assert missing.status_code == 422


async def test_search_is_fast(api):
    params = {"group": "B+", "component": "red_cells", **CENTRE}
    await api.client.get("/search", params=params)
    t0 = time.perf_counter()
    for _ in range(5):
        assert (await api.client.get("/search", params=params)).status_code == 200
    assert (time.perf_counter() - t0) / 5 < 0.2      # under 200 ms each


async def test_repeat_searches_use_the_cached_city_graph(api):
    before = (api.state.roads.hits, api.state.roads.misses)
    params = {"group": "B+", "component": "red_cells", **CENTRE}
    await api.client.get("/search", params=params)
    await api.client.get("/search", params=params)
    assert api.state.roads.misses == before[1] and api.state.roads.hits == before[0] + 2


async def test_route(api):
    response = await api.client.get("/route", params={**CENTRE, "bank_id": "B006"})
    body = response.json()
    assert response.status_code == 200 and body["bank_id"] == "B006"
    assert body["distance_km"] > 0 and body["est_travel_min"] > 0 and len(body["route"]) >= 2
    bank = (await api.client.get("/banks/B006")).json()
    assert body["route"][-1] == [bank["lat"], bank["lng"]]
    missing = await api.client.get("/route", params={**CENTRE, "bank_id": "NOPE"})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


async def test_banks_and_cities(api):
    banks = (await api.client.get("/banks")).json()
    assert len(banks) == 30 and {"id", "name", "lat", "lng", "phone", "city_id"} <= set(banks[0])
    detail = (await api.client.get("/banks/B001")).json()
    assert detail["id"] == "B001" and isinstance(detail["stock"], list)
    assert (await api.client.get("/banks/NOPE")).status_code == 404
    cities = (await api.client.get("/cities")).json()
    assert [c["id"] for c in cities] == ["synthetic"] and len(cities[0]["bbox"]) == 4
    meta = (await api.client.get("/meta")).json()
    assert meta["today"] == "2026-11-13" and meta["patient_conditions"]["accident"] == 100
