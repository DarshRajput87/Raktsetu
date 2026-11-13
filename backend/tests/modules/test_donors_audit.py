from datetime import datetime, timedelta

import pytest

from core.lru_cache import LRUCache
from modules import donors, stock
from modules.audit import AuditLog, UndoManager
from modules.cities import CityGraphCache, CityNotSupported, city_for_location
from tests.fixtures import TODAY

NOW = datetime(2026, 11, 13, 10, 0, 0)
NEW_DONOR = {"name": "Test Person", "age": 28, "gender": "F", "blood_group": "O+",
             "phone": "+91-00000-99999", "lat": 23.0001, "lng": 72.5301, "contact_consent": True}


# --- donors --------------------------------------------------------------------

def test_register_snaps_links_nearest_bank_and_computes_eligibility(tiny):
    donor = donors.register(tiny, dict(NEW_DONOR), TODAY)
    assert donor["node_id"] == "D" and donor["city_id"] == "synthetic"
    assert donor["linked_bank_id"] == "BK1"     # C is 1 km from D, E is 1.2 km
    assert donor["eligible"] is True and donor["available"] is True
    assert tiny.donors_by_id[donor["_id"]] is donor
    assert donor["_id"] in tiny.donors_by_group["synthetic"]["O+"]


def test_register_with_chosen_bank_and_ineligible_donor(tiny):
    data = dict(NEW_DONOR, linked_bank_id="BK2", age=17)
    donor = donors.register(tiny, data, TODAY)
    assert donor["linked_bank_id"] == "BK2" and donor["eligible"] is False
    with pytest.raises(ValueError):
        donors.register(tiny, dict(NEW_DONOR, linked_bank_id="NOPE"), TODAY)
    with pytest.raises(CityNotSupported):
        donors.register(tiny, dict(NEW_DONOR, lat=28.6, lng=77.2), TODAY)


def test_donation_creates_a_unit_and_turns_eligibility_off(tiny):
    donor = donors.register(tiny, dict(NEW_DONOR), TODAY)
    before = tiny.inventory.count_available("BK1", ["O+"], "whole_blood", TODAY)
    unit = donors.record_donation(tiny, donor["_id"], "BK1", "whole_blood", TODAY)
    assert unit["blood_group"] == "O+" and unit["expires_on"] == TODAY + timedelta(days=35)
    assert tiny.inventory.count_available("BK1", ["O+"], "whole_blood", TODAY) == before + 1
    assert donor["last_donation_date"] == TODAY and donor["eligible"] is False
    assert donor["donations"][0]["unit_id"] == unit["_id"]
    with pytest.raises(donors.NotEligible):
        donors.record_donation(tiny, donor["_id"], "BK1", "whole_blood", TODAY + timedelta(days=30))
    # Female donors wait 120 days.
    assert donors.update(tiny, donor["_id"], {}, TODAY + timedelta(days=119))["eligible"] is False
    assert donors.update(tiny, donor["_id"], {}, TODAY + timedelta(days=120))["eligible"] is True


def test_update_and_availability(tiny):
    assert donors.set_availability(tiny, "D1", False)["available"] is False
    donor = donors.update(tiny, "D1", {"blood_group": "O+", "linked_bank_id": "BK2"}, TODAY)
    assert donor["blood_group"] == "O+" and donor["linked_bank_id"] == "BK2"
    groups = tiny.donors_by_group["synthetic"]
    assert "D1" in groups["O+"] and "D1" not in groups["AB-"]


# --- audit log and undo --------------------------------------------------------

def test_audit_log_keeps_order_per_bank():
    log = AuditLog()
    for i in range(5):
        log.record("BK1", "added", [f"U{i}"], "admin", NOW + timedelta(seconds=i))
    log.record("BK2", "issued", ["X"], "admin", NOW)
    assert [e["unit_ids"] for e in log.recent("BK1", 3)] == [["U4"], ["U3"], ["U2"]]   # newest first
    assert len(log.recent("BK1")) == 5 and len(log.recent("BK2")) == 1 and log.recent("NOPE") == []
    assert len(log.take_unsaved()) == 6 and log.take_unsaved() == []
    with pytest.raises(ValueError):
        log.record("BK1", "teleported", [], None, NOW)


def test_undo_manager_is_last_in_first_out_per_admin():
    undo, calls = UndoManager(), []
    undo.push("a", "first", lambda: calls.append(1))
    undo.push("a", "second", lambda: calls.append(2))
    undo.push("b", "other", lambda: calls.append(3))
    assert undo.undo("a")[0] == "second" and undo.undo("a")[0] == "first"
    assert calls == [2, 1] and undo.can_undo("b") and not undo.can_undo("a")
    with pytest.raises(IndexError):
        undo.undo("a")


def test_add_unit_then_undo(tiny):
    unit = stock.add_unit(tiny, "BK1", "A-", "plasma", "admin1", TODAY, NOW)
    assert tiny.inventory.count_available("BK1", ["A-"], "plasma", TODAY) == 1
    description, _ = tiny.undo.undo("admin1")
    assert "A- plasma" in description
    assert tiny.inventory.get(unit["_id"]) is None
    assert tiny.inventory.count_available("BK1", ["A-"], "plasma", TODAY) == 0
    assert [e["action"] for e in tiny.audit.recent("BK1")] == ["removed", "added"]


def test_issue_is_fefo_and_undo_returns_the_units(tiny):
    units = stock.issue_units(tiny, "BK1", "B+", "red_cells", 2, "admin1", TODAY, NOW)
    assert [u["_id"] for u in units] == ["U2", "U1"]      # U2 expires first
    assert tiny.inventory.count_available("BK1", ["B+"], "red_cells", TODAY) == 0
    with pytest.raises(ValueError, match=r"Only 0 B\+ red cells unit"):
        stock.issue_units(tiny, "BK1", "B+", "red_cells", 1, "admin1", TODAY, NOW)
    tiny.undo.undo("admin1")
    assert tiny.inventory.count_available("BK1", ["B+"], "red_cells", TODAY) == 2
    assert tiny.inventory.get("U2")["status"] == "available"
    assert [e["action"] for e in tiny.audit.recent("BK1")] == ["returned", "issued"]


def test_donation_through_the_bank_and_undo(tiny):
    unit = stock.add_unit(tiny, "BK1", None, "whole_blood", "admin1", TODAY, NOW, donor_id="D2")
    donor = tiny.donors_by_id["D2"]
    assert unit["blood_group"] == "O-" and donor["eligible"] is False
    tiny.undo.undo("admin1")
    assert donor["last_donation_date"] is None and donor["eligible"] is True and donor["donations"] == []


def test_purge_expired_is_logged(tiny):
    expired = stock.purge_expired(tiny, TODAY, NOW)
    assert [u["_id"] for u in expired] == ["U7"]
    assert tiny.audit.recent("BK1")[0]["action"] == "expired"


# --- cities and the LRU cache --------------------------------------------------

def test_lru_cache_evicts_least_recently_used():
    cache = LRUCache(2)
    assert cache.put("a", 1) is None and cache.put("b", 2) is None
    assert cache.get("a") == 1                 # 'a' is now the most recently used
    assert cache.put("c", 3) == ("b", 2)       # so 'b' is evicted
    assert cache.keys() == ["c", "a"] and "b" not in cache and len(cache) == 2
    assert cache.get("b") is None and cache.get("b", "x") == "x"
    assert cache.put("a", 10) is None and cache.keys() == ["a", "c"]   # update counts as use
    assert cache.peek("c") == 3 and cache.keys() == ["a", "c"]         # peek does not
    assert cache.put("d", 4) == ("c", 3)
    with pytest.raises(ValueError):
        LRUCache(0)


def test_lru_cache_eviction_order_over_many_operations():
    cache, order = LRUCache(3), []
    for key in "abcadbeafc":
        if cache.get(key) is None:
            evicted = cache.put(key, key.upper())
            if evicted:
                order.append(evicted[0])
    assert order == ["b", "c", "a", "d", "b", "e"]
    assert cache.keys() == ["c", "f", "a"]


def test_city_graph_cache_counts_hits_and_misses():
    loads = []
    cache = CityGraphCache(2, loader=lambda city: loads.append(city) or f"roads of {city}")
    assert cache.get("ahmedabad") == "roads of ahmedabad"
    assert cache.get("ahmedabad") == "roads of ahmedabad"
    assert (cache.hits, cache.misses, loads) == (1, 1, ["ahmedabad"])
    cache.get("surat")
    cache.get("vadodara")                       # evicts ahmedabad
    assert cache.loaded() == ["vadodara", "surat"] and "ahmedabad" not in cache
    cache.get("ahmedabad")
    assert loads == ["ahmedabad", "surat", "vadodara", "ahmedabad"]
    with pytest.raises(KeyError):
        CityGraphCache(1).get("nowhere")


def test_city_for_location():
    cities = {
        "ahmedabad": {"center": [23.02, 72.57], "bbox": [22.7, 72.2, 23.4, 72.95]},
        "vadodara": {"center": [22.31, 73.18], "bbox": [22.0, 72.85, 22.75, 73.5]},
    }
    assert city_for_location(cities, 23.0225, 72.5714) == "ahmedabad"
    assert city_for_location(cities, 23.2156, 72.6369) == "ahmedabad"       # Gandhinagar
    assert city_for_location(cities, 22.70, 72.95) == "vadodara"             # in both: nearer centre
    assert city_for_location(cities, 22.70, 72.95, picked="ahmedabad") == "ahmedabad"
    assert city_for_location(cities, 23.0, 72.5, picked="vadodara") == "ahmedabad"   # pick not confirmed
    with pytest.raises(CityNotSupported, match="not available in this area yet"):
        city_for_location(cities, 19.07, 72.87)
