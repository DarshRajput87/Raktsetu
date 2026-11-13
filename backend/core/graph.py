"""Weighted road graph and Dijkstra's shortest path.

V = number of nodes, E = number of edges in the part of the graph that is
actually explored (with a distance cutoff this is usually far smaller than the
whole graph).
"""

from typing import Callable, Hashable, Iterator

from core.heap import MinHeap
from core.stack import Stack

Node = Hashable


class Graph:
    """Weighted graph stored as an adjacency list: node -> [(neighbour, weight)].

    Edges are undirected by default; pass directed=True for a one-way road.
    """

    def __init__(self) -> None:
        self._adj: dict[Node, list[tuple[Node, float]]] = {}
        self._edge_count = 0

    def add_node(self, node: Node) -> None:
        """Add a node if it is new. O(1) average (dict insert)."""
        if node not in self._adj:
            self._adj[node] = []

    def add_edge(self, u: Node, v: Node, weight: float, directed: bool = False) -> None:
        """Add an edge u - v (or u -> v only, when directed). O(1) average.

        Missing nodes are created. Weights must not be negative: Dijkstra
        depends on it.
        """
        if weight < 0:
            raise ValueError("edge weight must not be negative")
        self.add_node(u)
        self.add_node(v)
        self._adj[u].append((v, weight))
        if not directed:
            self._adj[v].append((u, weight))
        self._edge_count += 1

    def neighbors(self, node: Node) -> list[tuple[Node, float]]:
        """Outgoing (neighbour, weight) pairs. O(1). Raises KeyError if unknown."""
        return self._adj[node]

    def has_node(self, node: Node) -> bool:
        """O(1) average."""
        return node in self._adj

    def nodes(self) -> Iterator[Node]:
        """All node ids. O(V) for a full pass."""
        return iter(self._adj)

    @property
    def node_count(self) -> int:
        """O(1)."""
        return len(self._adj)

    @property
    def edge_count(self) -> int:
        """Number of add_edge calls (a two-way road counts once). O(1)."""
        return self._edge_count


def dijkstra(
    graph: Graph, source: Node, max_distance: float | None = None
) -> tuple[dict[Node, float], dict[Node, Node]]:
    """Shortest distance from source to every reachable node.

    Returns (dist, prev): dist[node] is the shortest distance, prev[node] is
    the node before it on that shortest path.

    If max_distance is set, nodes farther than that are never added and the
    search stops as soon as the nearest unsettled node is beyond it.

    Time O((V + E) log V) with our binary MinHeap, space O(V + E).
    The heap has no decrease-key, so a node can be pushed several times; old
    entries are skipped when popped ("lazy deletion").
    """
    dist: dict[Node, float] = {}
    prev: dict[Node, Node] = {}
    for _ in _settle(graph, source, max_distance, dist, prev):
        pass
    return dist, prev


def dijkstra_until(
    graph: Graph,
    source: Node,
    is_target: Callable[[Node], bool],
    max_distance: float | None = None,
    prev: dict[Node, Node] | None = None,
    on_visit: Callable[[Node, float, Node | None], None] | None = None,
) -> Iterator[tuple[Node, float]]:
    """Yield (node, distance) for target nodes, nearest first.

    This is a generator: the search only advances when the caller asks for the
    next target, so taking the first k targets costs only the work needed to
    reach the k-th one. Worst case (generator exhausted) is the same as
    dijkstra: O((V + E) log V).

    prev, if given, is filled in as the search runs so the caller can call
    build_path for any node yielded so far. on_visit(node, distance, parent)
    is called for every settled node, in visit order (used for the animation).
    """
    if prev is None:
        prev = {}
    dist: dict[Node, float] = {}
    for node, d in _settle(graph, source, max_distance, dist, prev):
        if on_visit is not None:
            on_visit(node, d, prev.get(node))
        if is_target(node):
            yield node, d


def _settle(
    graph: Graph,
    source: Node,
    max_distance: float | None,
    dist: dict[Node, float],
    prev: dict[Node, Node],
) -> Iterator[tuple[Node, float]]:
    """The Dijkstra loop: yield each node once, in increasing distance order."""
    if not graph.has_node(source):
        raise KeyError(f"unknown source node: {source!r}")
    dist[source] = 0.0
    heap = MinHeap()
    heap.push(0.0, source)
    while not heap.is_empty():
        d, u = heap.pop()
        if d > dist[u]:
            continue  # stale entry: u was already settled with a shorter distance
        if max_distance is not None and d > max_distance:
            break  # everything left in the heap is at least this far
        yield u, d
        for v, weight in graph.neighbors(u):
            nd = d + weight
            if max_distance is not None and nd > max_distance:
                continue
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heap.push(nd, v)


def build_path(prev: dict[Node, Node], source: Node, target: Node) -> list[Node]:
    """The node ids from source to target, or [] if target was not reached.

    Walks prev backwards from the target, pushing onto our Stack, then pops to
    get the path in forward order. O(path length).
    """
    if target != source and target not in prev:
        return []
    stack = Stack()
    node = target
    while node != source:
        stack.push(node)
        if node not in prev:
            return []
        node = prev[node]
    stack.push(source)
    path = []
    while not stack.is_empty():
        path.append(stack.pop())
    return path
