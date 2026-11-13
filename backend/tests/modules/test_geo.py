import random

import pytest

from modules.geo import GridIndex, haversine_km, nearest_node


def test_haversine_known_distance():
    # Ahmedabad -> Gandhinagar is about 23 km in a straight line.
    assert haversine_km(23.0225, 72.5714, 23.2156, 72.6369) == pytest.approx(22.5, abs=1.0)
    assert haversine_km(23.0, 72.5, 23.0, 72.5) == 0


def test_nearest_node_matches_linear_scan():
    rng = random.Random(5)
    coords = {f"N{i}": (23.0 + rng.uniform(-0.3, 0.3), 72.5 + rng.uniform(-0.3, 0.3)) for i in range(2000)}
    index = GridIndex(coords)
    for _ in range(300):
        lat, lng = 23.0 + rng.uniform(-0.4, 0.4), 72.5 + rng.uniform(-0.4, 0.4)
        expected = min(coords, key=lambda n: haversine_km(lat, lng, *coords[n]))
        assert nearest_node(index, lat, lng) == expected


def test_nearest_node_sparse_and_far_points():
    coords = {"A": (23.0, 72.5), "B": (23.5, 73.0)}
    index = GridIndex(coords)
    assert nearest_node(index, 23.01, 72.51) == "A"
    assert nearest_node(index, 23.3, 72.8) == "B"
    assert nearest_node(index, 10.0, 60.0) == "A"   # far outside the city
    node, km = index.nearest(23.0, 72.5)
    assert node == "A" and km == 0


def test_empty_index_raises():
    with pytest.raises(ValueError):
        GridIndex({}).nearest(23.0, 72.5)
