"""Build city road graphs from a downloaded OpenStreetMap extract (.osm.pbf).

The public Overpass servers are often overloaded and ask automated tools to
use extracts instead. This reads a regional extract once (for Gujarat:
https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf) and, in
a single pass, builds the drivable road graph of every requested city bbox. Each
graph is saved as downloads/<city_id>.graphml, the same cache that
import_cities.py and generate_real_data.py read, so nothing after this step
changes.

    python -m data.import_cities --all --pbf data/downloads/western-zone.osm.pbf

The "drivable" rules follow OSMnx's network_type="drive" filter: no footways,
cycleways, tracks, service roads, private access or roads closed to cars;
one-way streets (oneway=yes/-1, roundabouts) stay one-way.
"""

import math
import time
from pathlib import Path

import networkx as nx
import osmium

NOT_DRIVABLE = {
    "abandoned", "bridleway", "bus_guideway", "construction", "corridor", "cycleway", "elevator",
    "escalator", "footway", "no", "path", "pedestrian", "planned", "platform", "proposed", "raceway",
    "razed", "rest_area", "service", "services", "steps", "track", "bus_stop", "busway", "via_ferrata",
}
NO_CARS = {"no"}
EXCLUDED_SERVICE = {"alley", "driveway", "emergency_access", "parking", "parking_aisle", "private"}

Bbox = tuple[float, float, float, float]  # south, west, north, east


def is_drivable(tags) -> bool:
    """OSMnx 'drive' filter applied to one way's tags."""
    highway = tags.get("highway")
    if not highway or highway in NOT_DRIVABLE or tags.get("area") == "yes":
        return False
    if tags.get("access") == "private":
        return False
    if tags.get("motor_vehicle") in NO_CARS or tags.get("motorcar") in NO_CARS:
        return False
    return tags.get("service") not in EXCLUDED_SERVICE


def oneway_direction(tags) -> int:
    """1: one-way along the way, -1: one-way against it, 0: two-way."""
    value = tags.get("oneway", "")
    if value in ("yes", "true", "1"):
        return 1
    if value in ("-1", "reverse"):
        return -1
    if tags.get("junction") in ("roundabout", "circular") and value != "no":
        return 1
    return 0


def segment_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def inside(bbox: Bbox, lat: float, lng: float) -> bool:
    return bbox[0] <= lat <= bbox[2] and bbox[1] <= lng <= bbox[3]


class _RoadCollector(osmium.SimpleHandler):
    """One pass over the file: drivable road segments inside each city's bbox."""

    def __init__(self, bboxes: dict[str, Bbox]) -> None:
        super().__init__()
        self.bboxes = bboxes
        self.graphs = {city: nx.MultiDiGraph(crs="epsg:4326") for city in bboxes}
        self.ways_seen = 0

    def way(self, w) -> None:
        if not is_drivable(w.tags):
            return
        self.ways_seen += 1
        points = []
        for node in w.nodes:
            if not node.location.valid():
                return
            points.append((node.ref, node.location.lat, node.location.lon))
        direction = oneway_direction(w.tags)
        attrs = {"osmid": w.id, "highway": w.tags.get("highway"), "oneway": direction != 0}
        name = w.tags.get("name")
        if name:
            attrs["name"] = name
        for city, bbox in self.bboxes.items():
            graph = self.graphs[city]
            for (u, lat1, lng1), (v, lat2, lng2) in zip(points, points[1:]):
                # Keep a segment only if both ends are inside the city's bbox.
                if not (inside(bbox, lat1, lng1) and inside(bbox, lat2, lng2)) or u == v:
                    continue
                graph.add_node(u, y=lat1, x=lng1)
                graph.add_node(v, y=lat2, x=lng2)
                length = segment_m(lat1, lng1, lat2, lng2)
                if direction >= 0:
                    graph.add_edge(u, v, length=length, reversed=False, **attrs)
                if direction <= 0:
                    graph.add_edge(v, u, length=length, reversed=direction == 0, **attrs)


def build_graphs(pbf: Path, bboxes: dict[str, Bbox]) -> dict[str, nx.MultiDiGraph]:
    """Read the extract once and return a simplified, connected road graph per city."""
    import osmnx as ox

    t0 = time.time()
    print(f"Reading {pbf.name} for {len(bboxes)} city(ies). This takes a few minutes ...")
    collector = _RoadCollector(bboxes)
    collector.apply_file(str(pbf), locations=True, idx="sparse_mem_array")
    print(f"  {collector.ways_seen:,} drivable ways read in {time.time() - t0:.0f} s")

    graphs = {}
    for city, graph in collector.graphs.items():
        if graph.number_of_nodes() == 0:
            print(f"  {city}: no roads found inside its bbox (is it covered by this extract?)")
            continue
        raw = graph.number_of_nodes()
        # Merge chains of junction-free points into single road segments, as OSMnx does.
        graph = ox.simplify_graph(graph)
        graph = ox.truncate.largest_component(graph, strongly=False)
        print(f"  {city}: {raw:,} points -> {graph.number_of_nodes():,} junctions, "
              f"{graph.number_of_edges():,} directed road segments")
        graphs[city] = graph
    return graphs


def save_graphs(pbf: Path, bboxes: dict[str, Bbox], out_dir: Path) -> list[str]:
    """Build and cache the graphs; returns the city ids that were written."""
    import osmnx as ox

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for city, graph in build_graphs(pbf, bboxes).items():
        path = out_dir / f"{city}.graphml"
        ox.save_graphml(graph, path)
        written.append(city)
        print(f"  saved {path}")
    return written
