import random
from datetime import date, timedelta

import pytest

from modules.compatibility import PLASMA_COMPATIBLE, compatible_groups
from modules.eligibility import eligibility_reasons, is_eligible
from modules.inventory import Inventory

TODAY = date(2026, 11, 13)


def unit(_id, expires, group="B+", component="red_cells", bank="BK1", status="available"):
    return {"_id": _id, "bank_id": bank, "blood_group": group, "component": component,
            "collected_on": TODAY, "expires_on": expires, "status": status}


def day(n):
    return TODAY + timedelta(days=n)


# --- compatibility -------------------------------------------------------------

def test_compatible_groups_red_cells():
    assert compatible_groups("O-", "red_cells") == ["O-"]
    assert compatible_groups("B+", "whole_blood") == ["B+", "B-", "O+", "O-"]
    assert compatible_groups("AB+", "red_cells")[0] == "AB+"
    for group in ["O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]:
        groups = compatible_groups(group, "red_cells")
        assert groups[0] == group and groups[-1] == "O-"
    assert compatible_groups("A+", "platelets") == compatible_groups("A+", "red_cells")


def test_compatible_groups_plasma_is_reversed():
    assert compatible_groups("AB+", "plasma") == ["AB+", "AB-"]
    assert set(compatible_groups("O-", "plasma")) == set(PLASMA_COMPATIBLE)
    assert compatible_groups("A+", "plasma") == ["A+", "A-", "AB+", "AB-"]


def test_compatible_groups_rejects_unknown_values():
    with pytest.raises(ValueError):
        compatible_groups("C+", "red_cells")
    with pytest.raises(ValueError):
        compatible_groups("A+", "serum")


def test_returned_list_is_a_copy():
    compatible_groups("B+", "red_cells").append("X")
    assert compatible_groups("B+", "red_cells") == ["B+", "B-", "O+", "O-"]


# --- eligibility ---------------------------------------------------------------

def donor(**changes):
    base = {"age": 30, "gender": "M", "last_donation_date": None,
            "health_checklist": {"recent_illness": False, "on_medication": False}}
    base.update(changes)
    return base


def test_eligibility_rules():
    assert is_eligible(donor(), TODAY)
    assert not is_eligible(donor(age=17), TODAY) and not is_eligible(donor(age=66), TODAY)
    assert is_eligible(donor(age=18), TODAY) and is_eligible(donor(age=65), TODAY)
    assert not is_eligible(donor(health_checklist={"recent_illness": True}), TODAY)
    assert not is_eligible(donor(last_donation_date=day(-89)), TODAY)
    assert is_eligible(donor(last_donation_date=day(-90)), TODAY)
    assert not is_eligible(donor(gender="F", last_donation_date=day(-119)), TODAY)
    assert is_eligible(donor(gender="F", last_donation_date=day(-120)), TODAY)
    reasons = eligibility_reasons(donor(age=70, last_donation_date=day(-1)), TODAY)
    assert len(reasons) == 2 and day(89).isoformat() in reasons[1]


# --- inventory -----------------------------------------------------------------

def test_issue_takes_earliest_expiry_first():
    inv = Inventory()
    for i, d in enumerate([9, 3, 7, 1, 5]):
        inv.add_unit(unit(f"U{i}", day(d)))
    issued = inv.issue("BK1", ["B+"], "red_cells", 3, TODAY)
    assert [u["expires_on"] for u in issued] == [day(1), day(3), day(5)]
    assert all(u["status"] == "issued" for u in issued)
    assert inv.count_available("BK1", ["B+"], "red_cells", TODAY) == 2


def test_issue_tries_groups_in_order():
    inv = Inventory()
    inv.add_unit(unit("O1", day(1), group="O-"))     # expires first, but is the fallback group
    inv.add_unit(unit("B1", day(8)))
    inv.add_unit(unit("B2", day(4)))
    issued = inv.issue("BK1", ["B+", "O-"], "red_cells", 3, TODAY)
    assert [u["_id"] for u in issued] == ["B2", "B1", "O1"]


def test_issue_returns_fewer_when_stock_runs_out():
    inv = Inventory()
    inv.add_unit(unit("U1", day(2)))
    assert len(inv.issue("BK1", ["B+"], "red_cells", 5, TODAY)) == 1
    assert inv.issue("BK1", ["B+"], "red_cells", 1, TODAY) == []
    assert inv.issue("NOPE", ["B+"], "red_cells", 1, TODAY) == []


def test_only_available_units_are_in_the_heaps():
    inv = Inventory()
    inv.add_unit(unit("U1", day(2), status="reserved"))
    inv.add_unit(unit("U2", day(3), status="issued"))
    inv.add_unit(unit("U3", day(4), status="expired"))
    inv.add_unit(unit("U4", day(5)))
    assert len(inv) == 4
    assert inv.count_available("BK1", ["B+"], "red_cells", TODAY) == 1
    assert [u["_id"] for u in inv.issue("BK1", ["B+"], "red_cells", 9, TODAY)] == ["U4"]


def test_available_units_lists_only_usable_units_of_one_heap():
    inv = Inventory()
    inv.add_unit(unit("U1", day(2)))
    inv.add_unit(unit("U2", day(-1)))                       # expired
    inv.add_unit(unit("U3", day(4), status="reserved"))
    inv.add_unit(unit("U4", day(5), group="O+"))            # other group
    inv.add_unit(unit("U5", day(6)))
    inv.set_status("U5", "issued")                          # stale heap entry
    assert [u["_id"] for u in inv.available_units("BK1", "B+", "red_cells", TODAY)] == ["U1"]
    assert inv.available_units("BK1", "B+", "platelets", TODAY) == []


def test_expired_units_are_never_counted_or_issued():
    inv = Inventory()
    inv.add_unit(unit("OLD", day(-1)))
    inv.add_unit(unit("TODAY", day(0)))   # expiring today is still usable
    assert inv.count_available("BK1", ["B+"], "red_cells", TODAY) == 1
    assert [u["_id"] for u in inv.issue("BK1", ["B+"], "red_cells", 2, TODAY)] == ["TODAY"]
    assert inv.get("OLD")["status"] == "expired"
    assert [u["_id"] for u in inv.purge_expired(TODAY)] == ["OLD"]   # reported once
    assert inv.purge_expired(TODAY) == []


def test_reserve_then_release_puts_the_unit_back():
    inv = Inventory()
    inv.add_unit(unit("U1", day(2)))
    inv.add_unit(unit("U2", day(6)))
    reserved = inv.reserve("BK1", ["B+"], "red_cells", 1, TODAY)
    assert reserved[0]["_id"] == "U1" and reserved[0]["status"] == "reserved"
    assert inv.count_available("BK1", ["B+"], "red_cells", TODAY) == 1
    inv.set_status("U1", "available")
    inv.set_status("U1", "available")     # a repeated release must not duplicate the unit
    assert inv.count_available("BK1", ["B+"], "red_cells", TODAY) == 2
    assert [u["_id"] for u in inv.issue("BK1", ["B+"], "red_cells", 5, TODAY)] == ["U1", "U2"]


def test_remove_unit():
    inv = Inventory()
    inv.add_unit(unit("U1", day(2)))
    inv.remove_unit("U1")
    assert inv.get("U1") is None and len(inv) == 0
    assert inv.issue("BK1", ["B+"], "red_cells", 1, TODAY) == []


def test_purge_expired():
    inv = Inventory()
    inv.add_unit(unit("U1", day(-3)))
    inv.add_unit(unit("U2", day(-1), group="O-"))
    inv.add_unit(unit("U3", day(0)))
    inv.add_unit(unit("U4", day(-2), bank="BK2", component="platelets"))
    expired = inv.purge_expired(TODAY)
    assert sorted(u["_id"] for u in expired) == ["U1", "U2", "U4"]
    assert all(u["status"] == "expired" for u in expired)
    assert inv.get("U3")["status"] == "available"


def test_expiring_within_and_stock_table():
    inv = Inventory()
    inv.add_unit(unit("U1", day(5)))
    inv.add_unit(unit("U2", day(1)))
    inv.add_unit(unit("U3", day(2), group="O-", component="platelets"))
    inv.add_unit(unit("U4", day(30)))
    inv.add_unit(unit("U5", day(1), bank="BK2"))
    assert [u["_id"] for u in inv.expiring_within("BK1", 5, TODAY)] == ["U2", "U3", "U1"]
    table = {(r["blood_group"], r["component"]): r for r in inv.stock_table("BK1", TODAY, soon_days=3)}
    assert table[("B+", "red_cells")] == {"blood_group": "B+", "component": "red_cells", "units": 3,
                                          "earliest_expiry": day(1), "expiring_soon": 1}
    assert table[("O-", "platelets")]["units"] == 1
    assert inv.available_by_group("BK1", ["B+", "O-", "A+"], "red_cells", TODAY) == {"B+": 3}


def test_property_always_issues_earliest_expiring_unit():
    """Random adds, issues, reserves and releases, checked against a plain list."""
    rng = random.Random(11)
    for _ in range(30):
        inv, model, reserved, n = Inventory(), [], [], 0
        for _ in range(200):
            action = rng.random()
            if action < 0.5:
                n += 1
                u = unit(f"U{n}", day(rng.randint(0, 40)))
                inv.add_unit(u)
                model.append(u["_id"])
            elif action < 0.75:
                count = rng.randint(1, 4)
                got = inv.issue("BK1", ["B+"], "red_cells", count, TODAY,
                                new_status=rng.choice(["issued", "reserved"]))
                # Earliest expiry first; equal dates may come out in any order.
                expected = sorted(model, key=lambda i: inv.get(i)["expires_on"])[:count]
                assert [u["expires_on"] for u in got] == [inv.get(i)["expires_on"] for i in expected]
                for u in got:
                    model.remove(u["_id"])
                    if u["status"] == "reserved":
                        reserved.append(u["_id"])
            elif reserved:
                unit_id = reserved.pop(rng.randrange(len(reserved)))
                inv.set_status(unit_id, "available")
                model.append(unit_id)
            assert inv.count_available("BK1", ["B+"], "red_cells", TODAY) == len(model)
