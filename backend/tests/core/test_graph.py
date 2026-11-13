import random

import pytest

from core.graph import Graph, build_path, dijkstra, dijkstra_until


@pytest.fixture
def six() -> Graph:
    """Classic 6-node graph. Shortest distances from A:
    A0 B7 C9 D20 E20 F11 (A-C-F-E = 9+2+9, A-C-D = 9+11); G is isolated."""
    g = Graph()
    for u, v, w in [("A", "B", 7), ("A", "C", 9), ("A", "F", 14), ("B", "C", 10),
                    ("B", "D", 15), ("C", "D", 11), ("C", "F", 2), ("D", "E", 6), ("E", "F", 9)]:
        g.add_edge(u, v, w)
    g.add_node("G")
    return g


def test_graph_counts_and_neighbors(six):
    assert six.node_count == 7 and six.edge_count == 9
    assert sorted(six.neighbors("A")) == [("B", 7), ("C", 9), ("F", 14)]
    assert six.neighbors("G") == []
    assert six.has_node("A") and not six.has_node("Z")


def test_add_node_is_idempotent():
    g = Graph()
    g.add_edge("A", "B", 1)
    g.add_node("A")
    assert g.node_count == 2 and g.neighbors("A") == [("B", 1)]


def test_negative_weight_rejected():
    with pytest.raises(ValueError):
        Graph().add_edge("A", "B", -1)


def test_dijkstra_known_answers(six):
    dist, prev = dijkstra(six, "A")
    assert dist == {"A": 0, "B": 7, "C": 9, "D": 20, "E": 20, "F": 11}
    assert build_path(prev, "A", "E") == ["A", "C", "F", "E"]
    assert build_path(prev, "A", "D") == ["A", "C", "D"]
    assert build_path(prev, "A", "A") == ["A"]


def test_unreachable_node(six):
    dist, prev = dijkstra(six, "A")
    assert "G" not in dist
    assert build_path(prev, "A", "G") == []


def test_cutoff_respected(six):
    dist, prev = dijkstra(six, "A", max_distance=11)
    assert dist == {"A": 0, "B": 7, "C": 9, "F": 11}
    assert build_path(prev, "A", "E") == []
    assert dijkstra(six, "A", max_distance=0)[0] == {"A": 0}


def test_unknown_source_raises(six):
    with pytest.raises(KeyError):
        dijkstra(six, "Z")


def test_directed_edge_is_one_way():
    g = Graph()
    g.add_edge("A", "B", 1, directed=True)
    g.add_edge("B", "C", 1)
    g.add_edge("A", "C", 5)
    assert g.neighbors("B") == [("C", 1)]
    assert dijkstra(g, "A")[0] == {"A": 0, "B": 1, "C": 2}
    # Going back, the one-way street A -> B cannot be used.
    dist, prev = dijkstra(g, "B")
    assert dist == {"B": 0, "C": 1, "A": 6}
    assert build_path(prev, "B", "A") == ["B", "C", "A"]


def test_dijkstra_until_yields_targets_nearest_first(six):
    prev = {}
    found = list(dijkstra_until(six, "A", lambda n: n in {"D", "E", "F"}, None, prev))
    assert found == [("F", 11), ("D", 20), ("E", 20)]
    assert build_path(prev, "A", "F") == ["A", "C", "F"]


def test_dijkstra_until_is_lazy_and_respects_cutoff(six):
    visited = []
    gen = dijkstra_until(six, "A", lambda n: n in {"B", "E"}, None,
                         on_visit=lambda node, d, parent: visited.append((node, d, parent)))
    assert next(gen) == ("B", 7)
    assert visited == [("A", 0, None), ("B", 7, "A")]  # stopped at the first target
    assert list(dijkstra_until(six, "A", lambda n: n == "E", 15)) == []


def bellman_ford(nodes, edges, source):
    dist = {source: 0.0}
    for _ in range(len(nodes)):
        changed = False
        for u, v, w in edges:
            for a, b in ((u, v), (v, u)):
                if a in dist and dist[a] + w < dist.get(b, float("inf")):
                    dist[b] = dist[a] + w
                    changed = True
        if not changed:
            break
    return dist


def test_matches_bellman_ford_on_random_graphs():
    rng = random.Random(42)
    for _ in range(50):
        n = rng.randint(2, 12)
        nodes = list(range(n))
        edges = [(rng.randrange(n), rng.randrange(n), rng.randint(1, 20))
                 for _ in range(rng.randint(0, 3 * n))]
        g = Graph()
        for node in nodes:
            g.add_node(node)
        for u, v, w in edges:
            g.add_edge(u, v, w)

        expected = bellman_ford(nodes, edges, 0)
        dist, prev = dijkstra(g, 0)
        assert dist == expected

        weight = {}
        for u, v, w in edges:
            for key in ((u, v), (v, u)):
                weight[key] = min(w, weight.get(key, w))
        for target in dist:
            path = build_path(prev, 0, target)
            assert path[0] == 0 and path[-1] == target
            assert sum(weight[(a, b)] for a, b in zip(path, path[1:])) == dist[target]

        cutoff = rng.randint(1, 30)
        assert dijkstra(g, 0, max_distance=cutoff)[0] == {k: v for k, v in expected.items() if v <= cutoff}
