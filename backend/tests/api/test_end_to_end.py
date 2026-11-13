"""End-to-end scenarios for the hospital, donor, bank admin and system admin roles,
against the seeded test database."""

from api.services import dispatch_requests, purge_expired
from config import get_settings

CENTRE = {"lat": 23.0225, "lng": 72.5714}


async def dispatch(api):
    """What the background loop does every few seconds (it is switched off in tests)."""
    return await dispatch_requests(api.state, api.db, get_settings())


# --- hospital (Case 2) -----------------------------------------------------------

async def test_accident_is_allocated_before_planned_surgery(api):
    hospital = await api.staff_login("h001@hospital.raktsetu.test")
    surgery = await api.client.post("/hospital/requests", headers=hospital, json={
        "group": "O+", "component": "red_cells", "units_needed": 3, "patient_condition": "planned_surgery"})
    accident = await api.client.post("/hospital/requests", headers=hospital, json={
        "group": "O+", "component": "red_cells", "units_needed": 3, "patient_condition": "accident"})
    assert surgery.status_code == 201 and accident.status_code == 201
    assert surgery.json()["status"] == "queued" and accident.json()["base_score"] == 100

    processed = await dispatch(api)
    assert [r["_id"] for r in processed] == [accident.json()["id"], surgery.json()["id"]]

    first = (await api.client.get(f"/hospital/requests/{accident.json()['id']}", headers=hospital)).json()
    second = (await api.client.get(f"/hospital/requests/{surgery.json()['id']}", headers=hospital)).json()
    assert first["sequence"] < second["sequence"]
    assert first["status"] == "allocated" and first["units_allocated"] == 3

    # Nearest banks first; within a bank and group, earliest expiry first.
    distances = [a["distance_km"] for a in first["allocations"]]
    assert distances == sorted(distances)
    for allocation in first["allocations"]:
        for group in {u["blood_group"] for u in allocation["units"]}:
            dates = [u["expires_on"] for u in allocation["units"] if u["blood_group"] == group]
            assert dates == sorted(dates)
        for unit in allocation["units"]:
            assert api.state.inventory.get(unit["unit_id"])["status"] == "reserved"
            assert (await api.db.blood_units.find_one({"_id": unit["unit_id"]}))["status"] == "reserved"

    listed = (await api.client.get("/hospital/requests", headers=hospital)).json()
    assert {r["id"] for r in listed} >= {first["id"], second["id"]}
    stored = await api.db.requests.find_one({"_id": first["id"]})
    assert stored["status"] == "allocated" and stored["sequence"] == first["sequence"]


async def test_bank_accepts_and_rejects_requests(api):
    hospital = await api.staff_login("h002@hospital.raktsetu.test")
    created = (await api.client.post("/hospital/requests", headers=hospital, json={
        "group": "A+", "component": "plasma", "units_needed": 1, "patient_condition": "thalassemia"})).json()
    await dispatch(api)
    request = (await api.client.get(f"/hospital/requests/{created['id']}", headers=hospital)).json()
    allocation = request["allocations"][0]
    bank = await api.staff_login(f"{allocation['bank_id'].lower()}@bank.raktsetu.test")

    incoming = (await api.client.get("/bank/requests", headers=bank)).json()
    assert any(r["request_id"] == created["id"] and r["status"] == "pending" for r in incoming)

    # Reject: the unit returns to stock and the request finds another bank.
    rejected = await api.client.patch(f"/bank/requests/{created['id']}", headers=bank, json={"action": "reject"})
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    unit_id = allocation["units"][0]["unit_id"]
    assert (await api.db.blood_units.find_one({"_id": unit_id}))["status"] == "available"
    await dispatch(api)
    request = (await api.client.get(f"/hospital/requests/{created['id']}", headers=hospital)).json()
    assert [a["status"] for a in request["allocations"]] == ["rejected", "pending"]
    assert request["allocations"][1]["bank_id"] != allocation["bank_id"]

    # Accept at the second bank: the unit is issued and the request completes.
    second = request["allocations"][1]
    bank2 = await api.staff_login(f"{second['bank_id'].lower()}@bank.raktsetu.test")
    accepted = await api.client.patch(f"/bank/requests/{created['id']}", headers=bank2, json={"action": "accept"})
    assert accepted.json()["status"] == "accepted"
    assert (await api.db.blood_units.find_one({"_id": second["units"][0]["unit_id"]}))["status"] == "issued"
    request = (await api.client.get(f"/hospital/requests/{created['id']}", headers=hospital)).json()
    assert request["status"] == "completed"
    again = await api.client.patch(f"/bank/requests/{created['id']}", headers=bank2, json={"action": "accept"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "nothing_pending"


async def test_hospital_request_failure_cases(api):
    hospital = await api.staff_login("h003@hospital.raktsetu.test")
    bad = await api.client.post("/hospital/requests", headers=hospital, json={
        "group": "O+", "component": "red_cells", "units_needed": 0, "patient_condition": "accident"})
    assert bad.status_code == 422
    assert (await api.client.get("/hospital/requests/NOPE", headers=hospital)).status_code == 404
    assert (await api.client.get("/hospital/requests")).status_code == 401


# --- donor (Case 3) --------------------------------------------------------------

async def test_donor_registers_is_linked_to_nearest_bank_and_donates(api):
    user = await api.otp_login()
    suggested = (await api.client.get("/donors/me/suggested-banks", params=CENTRE, headers=user)).json()
    assert len(suggested) == 5
    assert [b["distance_km"] for b in suggested] == sorted(b["distance_km"] for b in suggested)
    assert suggested[0]["name"] == "Hari Nagar Blood Centre"

    response = await api.client.post("/donors/register", headers=user, json={
        "name": "Test Donor", "age": 30, "gender": "M", "blood_group": "A-", **CENTRE,
        "contact_consent": True})
    assert response.status_code == 201, response.text
    body = response.json()
    donor = body["donor"]
    assert donor["eligible"] is True and donor["linked_bank_id"] == suggested[0]["id"]
    assert body["user"]["role"] == "donor" and body["user"]["donor_id"] == donor["id"]
    donor_headers = {"Authorization": f"Bearer {body['token']}"}
    assert (await api.db.donors.find_one({"_id": donor["id"]}))["linked_bank_id"] == suggested[0]["id"]

    duplicate = await api.client.post("/donors/register", headers=donor_headers, json={
        "name": "Test Donor", "age": 30, "gender": "M", "blood_group": "A-", **CENTRE})
    assert duplicate.status_code == 409

    # The donor gives blood at the linked bank.
    bank = await api.staff_login(f"{donor['linked_bank_id'].lower()}@bank.raktsetu.test")
    before = (await api.client.get("/bank/stock", headers=bank)).json()["total_units"]
    added = await api.client.post("/bank/units", headers=bank,
                                  json={"component": "whole_blood", "donor_id": donor["id"]})
    assert added.status_code == 201 and added.json()["blood_group"] == "A-"
    assert added.json()["expires_on"] == "2026-12-18"                 # 35 days of shelf life
    assert (await api.client.get("/bank/stock", headers=bank)).json()["total_units"] == before + 1

    me = (await api.client.get("/donors/me", headers=donor_headers)).json()
    assert me["eligible"] is False and me["last_donation_date"] == "2026-11-13"
    assert me["next_eligible_date"] == "2027-02-11"                   # 90 days for a male donor
    assert me["donations"][0]["unit_id"] == added.json()["id"]
    stored = await api.db.donors.find_one({"_id": donor["id"]})
    assert stored["eligible"] is False and len(stored["donations"]) == 1

    second = await api.client.post("/bank/units", headers=bank,
                                   json={"component": "whole_blood", "donor_id": donor["id"]})
    assert second.status_code == 409 and second.json()["error"]["code"] == "donor_not_eligible"


async def test_donor_updates_availability_and_details(api):
    user = await api.otp_login()
    body = (await api.client.post("/donors/register", headers=user, json={
        "name": "Second Donor", "age": 17, "gender": "F", "blood_group": "O+", **CENTRE,
        "linked_bank_id": "B006"})).json()
    headers = {"Authorization": f"Bearer {body['token']}"}
    assert body["donor"]["eligible"] is False and body["donor"]["linked_bank_id"] == "B006"
    assert "Age" in body["donor"]["eligibility_reasons"][0]

    updated = await api.client.patch("/donors/me", headers=headers, json={"available": False, "age": 25})
    assert updated.status_code == 200
    assert updated.json()["available"] is False and updated.json()["eligible"] is True
    stored = await api.db.donors.find_one({"_id": body["donor"]["id"]})
    assert stored["available"] is False and stored["age"] == 25

    bad = await api.client.patch("/donors/me", headers=headers, json={"linked_bank_id": "NOPE"})
    assert bad.status_code == 400
    outside = await api.client.post("/donors/register", headers=await api.otp_login(), json={
        "name": "Far Away", "age": 30, "gender": "M", "blood_group": "O+", "lat": 28.61, "lng": 77.21})
    assert outside.status_code == 404 and outside.json()["error"]["code"] == "area_not_supported"


# --- blood bank admin (Case 4) ---------------------------------------------------

async def test_bank_issues_fefo_then_undoes(api):
    bank = await api.staff_login("b006@bank.raktsetu.test")
    stock = (await api.client.get("/bank/stock", headers=bank)).json()
    row = max(stock["rows"], key=lambda r: r["units"])
    group, component = row["blood_group"], row["component"]

    issued = await api.client.post("/bank/units/issue", headers=bank,
                                   json={"group": group, "component": component, "count": 2})
    assert issued.status_code == 200
    units = issued.json()["issued"]
    assert len(units) == 2 and units[0]["expires_on"] == row["earliest_expiry"]      # earliest expiry first
    assert units[0]["expires_on"] <= units[1]["expires_on"]
    assert (await api.db.blood_units.find_one({"_id": units[0]["id"]}))["status"] == "issued"
    after = (await api.client.get("/bank/stock", headers=bank)).json()
    assert after["total_units"] == stock["total_units"] - 2

    undone = await api.client.post("/bank/undo", headers=bank)
    assert undone.status_code == 200 and "issue 2" in undone.json()["undone"]
    restored = (await api.client.get("/bank/stock", headers=bank)).json()
    assert restored["total_units"] == stock["total_units"] and restored["rows"] == stock["rows"]
    assert (await api.db.blood_units.find_one({"_id": units[0]["id"]}))["status"] == "available"

    log = (await api.client.get("/bank/transactions", headers=bank, params={"limit": 2})).json()
    assert [entry["action"] for entry in log] == ["returned", "issued"]              # newest first
    assert sorted(log[0]["unit_ids"]) == sorted(u["id"] for u in units)
    assert await api.db.transactions.count_documents({"bank_id": "B006"}) >= 2


async def test_bank_adds_a_unit_then_undoes_twice(api):
    bank = await api.staff_login("b007@bank.raktsetu.test")
    before = (await api.client.get("/bank/stock", headers=bank)).json()["total_units"]
    added = await api.client.post("/bank/units", headers=bank, json={"component": "platelets", "blood_group": "AB-"})
    assert added.status_code == 201 and added.json()["expires_on"] == "2026-11-18"
    assert (await api.client.get("/bank/stock", headers=bank)).json()["total_units"] == before + 1
    assert await api.db.blood_units.find_one({"_id": added.json()["id"]}) is not None

    undone = (await api.client.post("/bank/undo", headers=bank)).json()
    assert "AB- platelets" in undone["undone"] and undone["can_undo_more"] is False
    assert (await api.client.get("/bank/stock", headers=bank)).json()["total_units"] == before
    assert await api.db.blood_units.find_one({"_id": added.json()["id"]}) is None

    nothing = await api.client.post("/bank/undo", headers=bank)
    assert nothing.status_code == 409 and nothing.json()["error"]["code"] == "nothing_to_undo"


async def test_bank_failure_cases(api):
    bank = await api.staff_login("b008@bank.raktsetu.test")
    too_many = await api.client.post("/bank/units/issue", headers=bank,
                                     json={"group": "AB-", "component": "platelets", "count": 99})
    assert too_many.status_code == 409 and too_many.json()["error"]["code"] == "not_enough_stock"
    no_group = await api.client.post("/bank/units", headers=bank, json={"component": "plasma"})
    assert no_group.status_code == 400
    no_donor = await api.client.post("/bank/units", headers=bank, json={"component": "plasma", "donor_id": "NOPE"})
    assert no_donor.status_code == 404
    assert (await api.client.patch("/bank/requests/NOPE", headers=bank, json={"action": "accept"})).status_code == 404
    assert (await api.client.get("/bank/transactions", headers=bank, params={"limit": 0})).status_code == 422


# --- system admin and upkeep -----------------------------------------------------

async def test_admin_verifies_places(api):
    admin = await api.staff_login("admin@raktsetu.test")
    places = (await api.client.get("/admin/places", headers=admin)).json()
    assert len(places) == 70 and {p["kind"] for p in places} == {"hospital", "bank"}

    response = await api.client.patch("/admin/hospitals/H040/verify", headers=admin, json={"verified": False})
    assert response.status_code == 200 and response.json()["verified"] is False
    assert (await api.db.hospitals.find_one({"_id": "H040"}))["verified"] is False
    login = await api.client.post("/auth/login", json={"email": "h040@hospital.raktsetu.test",
                                                       "password": "raktsetu123"})
    assert login.status_code == 403

    # An unverified bank disappears from search and from the public list.
    await api.client.patch("/admin/banks/B029/verify", headers=admin, json={"verified": False})
    assert "B029" not in [b["id"] for b in (await api.client.get("/banks")).json()]
    await api.client.patch("/admin/banks/B029/verify", headers=admin, json={"verified": True})
    assert (await api.client.patch("/admin/banks/NOPE/verify", headers=admin, json={})).status_code == 404
    assert (await api.client.get("/admin/reports", headers=await api.otp_login())).status_code == 403


async def test_purge_marks_expired_units(api):
    unit = await api.db.blood_units.find_one({"status": "available"})
    api.state.inventory.get(unit["_id"])["expires_on"] = get_settings().today.replace(year=2020)
    # The heap is keyed by the old date, so rebuild the unit's entry with the new one.
    api.state.inventory.set_status(unit["_id"], "available")
    count = await purge_expired(api.state, api.db, get_settings().today)
    assert count >= 1
    assert (await api.db.blood_units.find_one({"_id": unit["_id"]}))["status"] == "expired"
    assert api.state.audit.recent(unit["bank_id"], 1)[0]["action"] == "expired"
