"""Shared fixtures."""

import json
import os

# Test settings. Set before anything imports config.get_settings (it is cached).
os.environ.update(DB_NAME="raktsetu_test", BACKGROUND_TASKS="false", AS_OF_DATE="2026-11-13",
                  ENVIRONMENT="development", JWT_SECRET="test-secret", CITY_CACHE_CAPACITY="5")
from datetime import date
from pathlib import Path

import pytest

from modules.state import AppState, CityRoads
from tests.fixtures import tiny_state

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "output"


def load_generated() -> dict:
    """The generated synthetic city (data/output), read straight from the JSON files."""
    if not (OUTPUT / "meta.json").exists():
        pytest.skip("data/output is missing: run `python generate_data.py --as-of 2026-11-13` in backend/data")
    docs = {}
    for name in ["meta", "road_nodes", "road_edges", "blood_banks", "hospitals", "donors", "blood_units"]:
        with open(OUTPUT / f"{name}.json", encoding="utf-8") as f:
            docs[name] = json.load(f)
    return docs


def state_from_generated(docs: dict) -> AppState:
    nodes = docs["road_nodes"]
    lats, lngs = [n["lat"] for n in nodes], [n["lng"] for n in nodes]
    city = {"_id": "synthetic", "name": "Synthetic", "center": docs["meta"]["center"],
            "bbox": [min(lats), min(lngs), max(lats), max(lngs)]}
    roads = CityRoads("synthetic", nodes, docs["road_edges"])
    return AppState.build(cities=[city], banks=docs["blood_banks"], hospitals=docs["hospitals"],
                          donors=docs["donors"], units=docs["blood_units"], roads=[roads])


@pytest.fixture(scope="session")
def generated_docs() -> dict:
    return load_generated()


@pytest.fixture(scope="session")
def generated_today(generated_docs) -> date:
    return date.fromisoformat(generated_docs["meta"]["as_of"])


@pytest.fixture(scope="session")
def generated_state(generated_docs) -> AppState:
    """Read-only state on the generated city. Tests must not change it."""
    return state_from_generated(json.loads(json.dumps(generated_docs)))


@pytest.fixture
def fresh_generated_state(generated_docs) -> AppState:
    """A private copy that a test may change."""
    return state_from_generated(json.loads(json.dumps(generated_docs)))


@pytest.fixture
def tiny() -> AppState:
    return tiny_state()
