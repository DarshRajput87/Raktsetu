"""Phase 7: the donor-fallback scenario as one story, end to end through the API.

Search on the outskirts finds no bank with stock -> matching donors are listed
without phone numbers -> a logged-in user opens a donor's number -> the view is
logged -> after 20 views in a day the user is refused.

(The other four Phase 7 scenarios are in test_end_to_end.py and test_public.py:
banks + route, accident before planned surgery, donor registration and donation,
issue and undo.)
"""

OUTSKIRTS = {"group": "O-", "component": "platelets", "lat": 22.8021, "lng": 72.3275}


async def test_outskirts_search_falls_back_to_donors_then_contact_is_logged_and_limited(api):
    # 1. No bank within 25 km has O- platelets: donors instead, without phone numbers.
    response = await api.client.get("/search", params=OUTSKIRTS)
    body = response.json()
    assert response.status_code == 200
    assert body["banks"] == [] and body["route"] == []
    assert len(body["donors"]) >= 1
    assert all(d["blood_group"] == "O-" for d in body["donors"])
    distances = [d["distance_km"] for d in body["donors"]]
    assert distances == sorted(distances) and distances[-1] <= 25
    assert "+91-00000" not in response.text
    nearest = body["donors"][0]["donor_id"]

    # 2. The number needs a login.
    assert (await api.client.get(f"/donors/{nearest}/contact")).status_code == 401

    # 3. A logged-in user sees it, and the view is written to the access log.
    user = await api.otp_login()
    user_id = (await api.client.get("/auth/me", headers=user)).json()["id"]
    first = await api.client.get(f"/donors/{nearest}/contact", headers=user)
    assert first.status_code == 200
    assert first.json()["phone"] == api.state.donors_by_id[nearest]["phone"]
    log = await api.db.contact_access_logs.find_one({"viewer_id": user_id})
    assert log is not None and log["donor_id"] == nearest

    # 4. Every view counts; the 21st in a day is refused and not logged.
    for _ in range(19):
        assert (await api.client.get(f"/donors/{nearest}/contact", headers=user)).status_code == 200
    refused = await api.client.get(f"/donors/{nearest}/contact", headers=user)
    assert refused.status_code == 429 and refused.json()["error"]["code"] == "rate_limited"
    assert await api.db.contact_access_logs.count_documents({"viewer_id": user_id}) == 20

    # 5. A wider search (50 km) is the user's next step; it still answers.
    wider = await api.client.get("/search", params={**OUTSKIRTS, "radius": 50})
    assert wider.status_code == 200 and wider.json()["radius_km"] == 50
