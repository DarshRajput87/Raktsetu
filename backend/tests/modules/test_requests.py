from datetime import datetime, timedelta

import pytest

from modules.requests import (AGING_PER_MINUTE, RequestQueue, decide, effective_priority, fulfil,
                              new_request, process_queue)
from tests.fixtures import TODAY

T0 = datetime(2026, 11, 13, 10, 0, 0)


def minutes(n):
    return T0 + timedelta(minutes=n)


def make(state, request_id, condition, created, group="B+", component="red_cells", units=1):
    request = new_request(request_id, state.hospitals_by_id["H1"], group, component, units, condition, created)
    state.requests_by_id[request_id] = request
    return request


def simple(request_id, condition, created):
    from modules.requests import base_score
    return {"_id": request_id, "base_score": base_score(condition), "created_at": created}


# --- the queue -----------------------------------------------------------------

def test_accident_is_served_before_planned_surgery():
    queue = RequestQueue()
    queue.push(simple("surgery", "planned_surgery", minutes(0)))
    queue.push(simple("accident", "accident", minutes(1)))
    queue.push(simple("dengue", "dengue_low_platelets", minutes(1)))
    assert len(queue) == 3
    order = [queue.pop(minutes(2))["_id"] for _ in range(3)]
    assert order == ["accident", "dengue", "surgery"]
    assert queue.is_empty()
    with pytest.raises(IndexError):
        queue.pop(minutes(2))


def test_equal_priority_is_first_come_first_served():
    queue = RequestQueue()
    queue.push(simple("delivery", "delivery_complication", minutes(0)))
    queue.push(simple("accident", "accident", minutes(0) + timedelta(seconds=1)))
    queue.rekey(minutes(5))
    assert queue.pop(minutes(5))["_id"] == "delivery"


def test_aging_lets_an_old_request_overtake_newer_medium_ones():
    queue = RequestQueue()
    old = simple("old-other", "other", minutes(0))
    queue.push(old)
    # 'other' (20) needs to wait (40 - 20) / AGING_PER_MINUTE minutes to catch a fresh planned_surgery (40).
    catch_up = (40 - 20) / AGING_PER_MINUTE

    queue.push(simple("surgery-1", "planned_surgery", minutes(catch_up - 5)))
    assert queue.pop(minutes(catch_up - 5))["_id"] == "surgery-1"   # not old enough yet

    queue.push(simple("surgery-2", "planned_surgery", minutes(catch_up + 1)))
    assert effective_priority(old, minutes(catch_up + 1)) > 40
    assert queue.pop(minutes(catch_up + 1))["_id"] == "old-other"   # aging won
    # ...but aging never beats a fresh accident that quickly.
    queue.push(old)
    queue.push(simple("accident", "accident", minutes(catch_up + 2)))
    assert queue.pop(minutes(catch_up + 2))["_id"] == "accident"


def test_rekey_is_what_applies_aging():
    """Without a re-key the heap still holds the priorities from push time."""
    queue = RequestQueue()
    queue.push(simple("old-other", "other", minutes(0)))
    queue.push(simple("surgery", "planned_surgery", minutes(100)))
    assert queue.peek()["_id"] == "surgery"       # stale keys: 40 beats 20
    queue.rekey(minutes(100))
    assert queue.peek()["_id"] == "old-other"     # 20 + 100 * 0.5 = 70 beats 40


# --- fulfilment ----------------------------------------------------------------

def test_fulfil_takes_units_from_the_nearest_bank_first(tiny):
    request = make(tiny, "R1", "accident", T0, units=4)
    fulfil(tiny, request, TODAY, T0)
    assert request["status"] == "allocated" and request["sequence"] == 1
    first, second = request["allocations"]
    # BK1 (2 km): both B+ units earliest expiry first, then its O-; BK2 (4.2 km) gives the rest.
    assert (first["bank_id"], first["unit_ids"]) == ("BK1", ["U2", "U1", "U3"])
    assert (second["bank_id"], second["unit_ids"]) == ("BK2", ["U4"])
    assert all(tiny.inventory.get(u)["status"] == "reserved" for u in ["U1", "U2", "U3", "U4"])
    # Donors are listed even when banks cover the request: B+ red cells -> B+, B-, O+, O-.
    assert [d["donor_id"] for d in request["donor_suggestions"]] == ["D2", "D7"]
    assert [e["action"] for e in tiny.audit.recent("BK1")] == ["reserved"]


def test_partial_result_comes_with_donors(tiny):
    request = make(tiny, "R1", "accident", T0, units=9)
    fulfil(tiny, request, TODAY, T0)
    assert request["status"] == "partial"
    assert sum(len(a["unit_ids"]) for a in request["allocations"]) == 5   # U1-U5
    assert [d["donor_id"] for d in request["donor_suggestions"]] == ["D2", "D7"]   # O- and B-


def test_unfulfilled_request_lists_donors(tiny):
    request = make(tiny, "R1", "dengue_low_platelets", T0, group="AB-", component="platelets")
    fulfil(tiny, request, TODAY, T0)
    assert request["status"] == "unfulfilled" and request["allocations"] == []
    assert [d["donor_id"] for d in request["donor_suggestions"]] == ["D2", "D1", "D7"]


def test_process_queue_allocates_the_accident_first(tiny):
    surgery = make(tiny, "R-surgery", "planned_surgery", minutes(0), units=3)
    accident = make(tiny, "R-accident", "accident", minutes(1), units=3)
    tiny.request_queue.push(surgery)
    tiny.request_queue.push(accident)
    processed = process_queue(tiny, TODAY, minutes(2))
    assert [r["_id"] for r in processed] == ["R-accident", "R-surgery"]
    assert accident["sequence"] < surgery["sequence"]
    # The accident got the nearest bank's units; the surgery got what was left.
    assert [a["bank_id"] for a in accident["allocations"]] == ["BK1"]
    assert [a["bank_id"] for a in surgery["allocations"]] == ["BK2"]
    assert surgery["status"] == "partial"


def test_bank_accepts(tiny):
    request = make(tiny, "R1", "accident", T0, units=2)
    fulfil(tiny, request, TODAY, T0)
    decide(tiny, request, "BK1", True, "admin1", T0)
    assert request["status"] == "completed"
    assert tiny.inventory.get("U2")["status"] == "issued"
    assert tiny.audit.recent("BK1")[0]["action"] == "issued"
    with pytest.raises(LookupError):
        decide(tiny, request, "BK1", True, "admin1", T0)


def test_bank_rejects_and_the_request_moves_on(tiny):
    request = make(tiny, "R1", "accident", T0, units=2)
    fulfil(tiny, request, TODAY, T0)
    decide(tiny, request, "BK1", False, "admin1", T0)
    assert request["status"] == "queued" and len(tiny.request_queue) == 1
    assert tiny.inventory.get("U2")["status"] == "available"      # back in stock
    process_queue(tiny, TODAY, minutes(1))
    assert request["allocations"][0]["status"] == "rejected"
    assert request["allocations"][1]["bank_id"] == "BK2"          # BK1 is left out this time
    assert request["status"] == "allocated"
