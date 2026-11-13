from datetime import date

from tests.fixtures import tiny_state


def test_state_indexes_the_documents():
    state = tiny_state()
    counts = state.counts()
    assert counts["road_nodes"] == 6 and counts["road_edges"] == 5
    assert counts["blood_banks"] == 3 and counts["donors"] == 7 and counts["blood_units"] == 9
    assert state.banks_by_id["BK1"]["node_id"] == "C"
    assert state.banks_by_node["C"] == ["BK1"]
    assert state.hospitals_by_id["H1"]["node_id"] == "A"
    assert sorted(state.donors_by_group["synthetic"]["AB-"]) == ["D1", "D5"]
    assert state.donors_by_id["D5"]["last_donation_date"] == date(2026, 11, 1)


def test_city_roads_graph_and_routes():
    roads = tiny_state().get_roads("synthetic")
    assert sorted(roads.graph.neighbors("D")) == [("C", 1.0), ("E", 1.2), ("F", 30.0)]
    assert roads.node_coords["A"] == (23.00, 72.50)
    assert roads.index.nearest(23.0001, 72.5099)[0] == "B"
    assert roads.route_coords(["A", "B"]) == [[23.00, 72.50], [23.00, 72.51]]
    assert roads.route_minutes(["A", "B", "C", "D", "E"]) == 3 + 3 + 3 + 3.6


def test_one_way_road_is_directed():
    from modules.state import CityRoads

    nodes = [{"_id": "A", "lat": 23.0, "lng": 72.5}, {"_id": "B", "lat": 23.0, "lng": 72.51}]
    edges = [{"_id": "E1", "from": "A", "to": "B", "distance_km": 1.0, "oneway": True, "travel_time_min": 2.0}]
    roads = CityRoads("x", nodes, edges)
    assert roads.graph.neighbors("A") == [("B", 1.0)] and roads.graph.neighbors("B") == []
