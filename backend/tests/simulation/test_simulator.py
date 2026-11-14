"""The Phase 8 simulator on a few days of the generated city (no MongoDB)."""

from pathlib import Path

import pytest

from simulation import simulator as sim
from tests.conftest import OUTPUT

DAYS = 4


@pytest.fixture(scope="module")
def world():
    if not (OUTPUT / "meta.json").exists():
        pytest.skip("data/output is missing: run `python generate_data.py --as-of 2026-11-13` in backend/data")
    return sim.World(Path(OUTPUT), sim.Config(days=DAYS))


@pytest.fixture(scope="module")
def events(world):
    return sim.generate_events(world, seed=7)


@pytest.fixture(scope="module")
def results(world, events):
    rows = {}
    for method in sim.METHODS:
        s = sim.Simulation(world, method, seed=7)
        rows[method] = (s.run(*events), s)
    return rows


def test_events_are_reproducible(world, events):
    assert sim.generate_events(world, seed=7) == events
    assert sim.generate_events(world, seed=8) != events


def test_every_method_sees_every_request(results, events):
    for row, s in results.values():
        assert row["requests"] == len(events[1])
        assert len(s.daily) == DAYS


def test_metrics_are_in_range(results):
    for row, _ in results.values():
        for key in ("wastage_pct", "fulfilment_pct", "critical_fulfilment_pct", "donor_fallback_pct"):
            assert 0 <= row[key] <= 100
        assert row["locate_min_p90"] >= row["locate_min_mean"] * 0.5


def test_traditional_has_no_donor_fallback_and_no_transfers(results):
    row, _ = results["traditional"]
    assert row["donor_fallback_pct"] == 0
    assert row["transfers"] == 0
    assert results["raktsetu"][0]["transfers"] == 0


def test_raktsetu_never_goes_beyond_the_radius(results, world):
    _, s = results["raktsetu"]
    for outcome in s.outcomes:
        assert outcome.bank_km <= world.config.radius_km * outcome.request["units_needed"]


def test_raktsetu_travels_less_than_traditional(results):
    assert results["raktsetu"][0]["distance_km_mean"] < results["traditional"][0]["distance_km_mean"]


def test_issued_units_match_fulfilled_requests(results):
    """Fulfilled requests take their units from banks or donors; unfulfilled ones take none."""
    for method in ("traditional", "raktsetu"):
        _, s = results[method]
        issued = sum(1 for u in s.state.inventory._units.values() if u["status"] == "issued")
        initially_issued = sum(1 for u in s.world.docs["blood_units"] if u["status"] == "issued")
        bank_units_used = issued - initially_issued
        needed = sum(o.request["units_needed"] for o in s.outcomes if o.fulfilled)
        assert 0 < bank_units_used <= needed
        assert not any(u["status"] == "reserved" and u["_id"].startswith("S")
                       for u in s.state.inventory._units.values())


def test_transfers_move_units_once(results):
    _, s = results["raktsetu_transfer"]
    moved = [u for u in s.state.inventory._units.values() if u.get("moved")]
    assert len(moved) == s.transfers
    assert not any(u["_id"].endswith("-T-T") for u in moved)


def test_percentile_is_nearest_rank():
    assert sim.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90) == 9
    assert sim.percentile([5], 90) == 5
