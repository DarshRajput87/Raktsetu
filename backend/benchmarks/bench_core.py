"""Benchmarks for the core data structures and the search (Phase 7).

    python -m benchmarks.bench_core                 # everything (about 5-10 minutes)
    python -m benchmarks.bench_core --quick         # smaller runs, for a smoke test
    python -m benchmarks.bench_core --only heap     # heap | dijkstra | sizes | cities

Writes CSV files, PNG charts and a summary to benchmarks/results/:
    heap.csv, heap.png                our MinHeap vs Python's heapq, push + pop of n items
    dijkstra.csv, dijkstra.png        25 km cutoff vs full Dijkstra, 200 random start points
    search_latency.csv, .png          search time on synthetic cities of 30, 60 and 100 km
    city_search.csv                   search time on the real road network of each city
    summary.md                        the numbers above as tables, for the report

Runs entirely in memory from the generated JSON (no MongoDB, no API), with
fixed seeds so reruns measure the same work. Timings depend on the machine.
"""

import argparse
import csv
import heapq
import json
import platform
import random
import statistics
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from core.graph import Graph, dijkstra
from core.heap import MinHeap
from modules.compatibility import BLOOD_GROUPS, COMPONENTS
from modules.search import search_blood
from modules.state import AppState, CityRoads

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"
RESULTS = Path(__file__).resolve().parent / "results"
CACHE = Path(__file__).resolve().parent / ".cache"
TODAY = date(2026, 11, 13)
SEED = 42
RADIUS_KM = 25.0

# Chart tokens. Series colours are the validated two-slot categorical pair
# (blue, orange: CVD dE 24.7, normal-vision dE 33.6, both >= 3:1 on white).
SERIES = ["#2a78d6", "#eb6834"]
INK, MUTED, GRID, SURFACE = "#1b2333", "#5b6475", "#e3e6ec", "#ffffff"


# ---- loading ----------------------------------------------------------------

def load_folder(folder: Path) -> dict:
    docs = {}
    for name in ["meta", "road_nodes", "road_edges", "blood_banks", "hospitals", "donors", "blood_units"]:
        with open(folder / f"{name}.json", encoding="utf-8") as f:
            docs[name] = json.load(f)
    return docs


def build_state(docs: dict, city_id: str = "synthetic") -> AppState:
    """The same in-memory state the API builds at startup."""
    nodes = docs["road_nodes"]
    lats, lngs = [n["lat"] for n in nodes], [n["lng"] for n in nodes]
    city = {"_id": city_id, "name": city_id, "center": docs["meta"]["center"],
            "bbox": [min(lats), min(lngs), max(lats), max(lngs)]}
    for collection in ("blood_banks", "hospitals", "donors", "blood_units"):
        for doc in docs[collection]:
            doc["city_id"] = city_id
    roads = CityRoads(city_id, nodes, docs["road_edges"])
    return AppState.build(cities=[city], banks=docs["blood_banks"], hospitals=docs["hospitals"],
                          donors=docs["donors"], units=docs["blood_units"], roads=[roads])


def road_graph(docs: dict) -> Graph:
    graph = Graph()
    for node in docs["road_nodes"]:
        graph.add_node(node["_id"])
    for edge in docs["road_edges"]:
        graph.add_edge(edge["from"], edge["to"], edge["distance_km"], directed=bool(edge.get("oneway")))
    return graph


def synthetic_city(size_km: int) -> Path:
    """Generate (once) a synthetic city of the given size with the standard generator."""
    out = CACHE / f"grid_{size_km}km"
    if not (out / "meta.json").exists():
        subprocess.run([sys.executable, str(DATA / "generate_data.py"), "--size-km", str(size_km),
                        "--seed", str(SEED), "--as-of", TODAY.isoformat(), "--out", str(out)],
                       check=True, capture_output=True)
    return out


# ---- measurements -------------------------------------------------------------

def best_of(repeats: int, fn) -> float:
    """Fastest of several runs, in seconds (the least disturbed by other work)."""
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return min(times)


def bench_heap(sizes: list[int], repeats: int) -> list[dict]:
    """Push n random keys, then pop them all: our MinHeap against heapq.

    heapq stores (key, counter, item) so both heaps do the same job: stable
    order for equal keys.
    """
    rows = []
    for n in sizes:
        keys = [random.Random(SEED + n).random() for _ in range(n)]

        def ours() -> None:
            heap = MinHeap()
            for i, k in enumerate(keys):
                heap.push(k, i)
            while not heap.is_empty():
                heap.pop()

        def reference() -> None:
            heap: list = []
            for i, k in enumerate(keys):
                heapq.heappush(heap, (k, i, i))
            while heap:
                heapq.heappop(heap)

        t_ours, t_ref = best_of(repeats, ours), best_of(repeats, reference)
        rows.append({"n": n, "raktsetu_minheap_ms": round(t_ours * 1000, 2), "python_heapq_ms": round(t_ref * 1000, 2),
                     "ratio": round(t_ours / t_ref, 2)})
        print(f"  heap n={n:>7,}: MinHeap {t_ours * 1000:8.1f} ms   heapq {t_ref * 1000:7.1f} ms   x{t_ours / t_ref:.1f}")
    return rows


def bench_dijkstra(name: str, docs: dict, starts: int) -> dict:
    """Full Dijkstra against the 25 km cutoff, from the same random junctions."""
    graph = road_graph(docs)
    rng = random.Random(SEED)
    nodes = [n["_id"] for n in docs["road_nodes"]]
    sources = [rng.choice(nodes) for _ in range(starts)]
    full_t, full_n, cut_t, cut_n = [], [], [], []
    for source in sources:
        t0 = time.perf_counter()
        dist, _ = dijkstra(graph, source)
        full_t.append(time.perf_counter() - t0)
        full_n.append(len(dist))
        t0 = time.perf_counter()
        dist, _ = dijkstra(graph, source, max_distance=RADIUS_KM)
        cut_t.append(time.perf_counter() - t0)
        cut_n.append(len(dist))
    row = {
        "graph": name, "junctions": graph.node_count, "roads": graph.edge_count, "start_points": starts,
        "full_ms_mean": round(statistics.mean(full_t) * 1000, 2), "cutoff_ms_mean": round(statistics.mean(cut_t) * 1000, 2),
        "full_nodes_mean": round(statistics.mean(full_n)), "cutoff_nodes_mean": round(statistics.mean(cut_n)),
    }
    row["speedup"] = round(row["full_ms_mean"] / row["cutoff_ms_mean"], 1)
    row["nodes_share_pct"] = round(100 * row["cutoff_nodes_mean"] / row["full_nodes_mean"], 1)
    print(f"  dijkstra {name}: full {row['full_ms_mean']} ms / {row['full_nodes_mean']:,} nodes   "
          f"cutoff {row['cutoff_ms_mean']} ms / {row['cutoff_nodes_mean']:,} nodes   x{row['speedup']}")
    return row


def bench_search(name: str, state: AppState, city_id: str, searches: int) -> dict:
    """The full Case 1 search (snap, Dijkstra with cutoff, stock check, donor fallback)
    from random junctions, random blood group and component."""
    roads = state.get_roads(city_id)
    rng = random.Random(SEED)
    coords = list(roads.node_coords.values())
    times, visited, fallbacks = [], [], 0
    for _ in range(searches):
        lat, lng = rng.choice(coords)
        group, component = rng.choice(BLOOD_GROUPS), rng.choice(COMPONENTS)
        t0 = time.perf_counter()
        result = search_blood(state, lat, lng, group, component, RADIUS_KM, TODAY, city_id=city_id)
        times.append((time.perf_counter() - t0) * 1000)
        visited.append(result.junctions_visited)
        fallbacks += not result.banks
    times.sort()
    row = {
        "city": name, "junctions": roads.graph.node_count, "searches": searches,
        "median_ms": round(statistics.median(times), 2), "p95_ms": round(times[int(0.95 * (len(times) - 1))], 2),
        "mean_junctions_visited": round(statistics.mean(visited)), "donor_fallback_pct": round(100 * fallbacks / searches, 1),
    }
    print(f"  search {name}: median {row['median_ms']} ms, p95 {row['p95_ms']} ms, "
          f"{row['mean_junctions_visited']:,} junctions visited, fallback {row['donor_fallback_pct']}%")
    return row


# ---- charts -------------------------------------------------------------------

def chart_style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": "sans-serif", "font.size": 10, "text.color": INK,
        "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "axes.titlecolor": INK,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 12,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 1, "grid.linestyle": "-",
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.major.size": 0, "ytick.major.size": 0,
        "legend.frameon": False, "legend.fontsize": 9.5, "lines.linewidth": 2,
    })
    return plt


def rounded_bar(ax, x: float, height: float, width: float, color: str) -> None:
    """A bar with a 4 px rounded data end and a square base (matplotlib has no such bar)."""
    from matplotlib.patches import FancyBboxPatch, Rectangle

    fig = ax.figure
    fig.canvas.draw()
    x_per_px = (ax.get_xlim()[1] - ax.get_xlim()[0]) / ax.bbox.width
    y_per_px = (ax.get_ylim()[1] - ax.get_ylim()[0]) / ax.bbox.height
    r = 4 * x_per_px
    ax.add_patch(FancyBboxPatch((x - width / 2, 0), width, height, boxstyle=f"round,pad=0,rounding_size={r}",
                                mutation_aspect=y_per_px / x_per_px, facecolor=color, edgecolor="none", zorder=3))
    square = min(height, 6 * y_per_px)
    ax.add_patch(Rectangle((x - width / 2, 0), width, square, facecolor=color, edgecolor="none", zorder=3))


def end_label(ax, x: float, y: float, text: str, dy_px: float = 6) -> None:
    ax.annotate(text, (x, y), xytext=(0, dy_px), textcoords="offset points", ha="center", va="bottom",
                fontsize=9, color=INK, zorder=4)


def chart_heap(rows: list[dict]) -> None:
    plt = chart_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=160)
    n = [r["n"] for r in rows]
    series = [("Our MinHeap (pure Python)", "raktsetu_minheap_ms"), ("Python heapq (C)", "python_heapq_ms")]
    for (label, key), color in zip(series, SERIES):
        ys = [r[key] for r in rows]
        ax.plot(n, ys, color=color, marker="o", markersize=7, markeredgecolor=SURFACE, markeredgewidth=2,
                label=label, zorder=3)
        ax.annotate(f"{ys[-1]:,.0f} ms", (n[-1], ys[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK)
    ax.set_title("Push then pop n items")
    ax.set_xlabel("Items (n)")
    ax.set_ylabel("Time, ms (best of runs)")
    ax.set_xlim(0, n[-1] * 1.15)
    ax.set_ylim(0, max(r["raktsetu_minheap_ms"] for r in rows) * 1.15)
    ax.xaxis.set_major_formatter(lambda v, _: f"{int(v):,}")
    ax.legend(loc="upper left")
    ratio = rows[-1]["ratio"]
    fig.text(0.01, 0.01, f"Both grow as O(n log n). At n = {n[-1]:,} ours takes {ratio}× as long as heapq, which is "
             "written in C.", fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(RESULTS / "heap.png")
    plt.close(fig)


def chart_dijkstra(rows: list[dict]) -> None:
    plt = chart_style()
    n = len(rows)
    height = 3.6 * n + 0.6
    fig, axes = plt.subplots(n, 2, figsize=(8, height), dpi=160, squeeze=False)
    # Margins in inches, converted to figure fractions: room for each row heading and the footnote.
    fig.subplots_adjust(left=0.09, right=0.98, top=1 - 0.75 / height, bottom=1.05 / height, wspace=0.28,
                        hspace=1.25 / 3.6)
    labels = ["Full search", f"{RADIUS_KM:.0f} km cutoff"]
    for row, (ax_time, ax_nodes) in zip(rows, axes):
        panels = [(ax_time, "Time per search, ms", [row["full_ms_mean"], row["cutoff_ms_mean"]], "{:,.1f}"),
                  (ax_nodes, "Junctions explored", [row["full_nodes_mean"], row["cutoff_nodes_mean"]], "{:,.0f}")]
        for ax, title, values, fmt in panels:
            ax.set_title(title, fontsize=10, fontweight="normal", color=MUTED, pad=8)
            ax.set_xlim(-0.6, 1.6)
            ax.set_ylim(0, max(values) * 1.22)
            ax.set_xticks([0, 1], labels)
            ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
            for x, (value, color) in enumerate(zip(values, SERIES)):
                rounded_bar(ax, x, value, 0.42, color)
                end_label(ax, x, value, fmt.format(value))
        top = ax_time.get_position().y1
        fig.text(0.02, top + 0.42 / height, f"{row['graph']} ({row['junctions']:,} junctions)", fontsize=12,
                 fontweight="bold", color=INK, va="bottom")
    fig.text(0.02, 0.12 / height, f"Mean over {rows[0]['start_points']} random start junctions per road network.\n"
             "The cutoff stops Dijkstra once the nearest unsettled junction is more than 25 km away.",
             fontsize=8.5, color=MUTED, va="bottom")
    fig.savefig(RESULTS / "dijkstra.png")
    plt.close(fig)


def chart_search(rows: list[dict]) -> None:
    plt = chart_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=160)
    sizes = [int(r["city"].split()[0]) for r in rows]
    for (label, key), color in zip([("Median", "median_ms"), ("95th percentile", "p95_ms")], SERIES):
        ys = [r[key] for r in rows]
        ax.plot(sizes, ys, color=color, marker="o", markersize=7, markeredgecolor=SURFACE, markeredgewidth=2,
                label=label, zorder=3)
        for x, y in zip(sizes, ys):
            ax.annotate(f"{y:.1f}", (x, y), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9, color=INK)
    ax.set_title("Search time by city size (synthetic grid, 25 km radius)")
    ax.set_xlabel("City width, km (junction every 1 km)")
    ax.set_ylabel("Time per search, ms")
    ax.set_xticks(sizes, [f"{s} × {s} km\n{r['junctions']:,} junctions" for s, r in zip(sizes, rows)])
    ax.set_xlim(sizes[0] - 12, sizes[-1] + 12)
    ax.set_ylim(0, max(r["p95_ms"] for r in rows) * 1.3)
    ax.legend(loc="upper left")
    explored = ", ".join(f"{r['mean_junctions_visited']:,}" for r in rows)
    fig.text(0.01, 0.01, f"Junctions explored per search: {explored}. The 25 km radius bounds the work, "
             "not the size of the city.", fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(RESULTS / "search_latency.png")
    plt.close(fig)


# ---- output -------------------------------------------------------------------

def write_csv(name: str, rows: list[dict]) -> None:
    with open(RESULTS / name, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def md_table(rows: list[dict]) -> str:
    head = list(rows[0])
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(f"{r[h]:,}" if isinstance(r[h], (int, float)) else str(r[h]) for h in head) + " |" for r in rows]
    return "\n".join(lines)


def write_summary(sections: dict[str, list[dict]]) -> None:
    titles = {"heap": "Heap: push then pop n items", "dijkstra": "Dijkstra: 25 km cutoff vs full search",
              "sizes": "Search time by synthetic city size", "cities": "Search time on real roads (Gujarat)"}
    parts = [f"# RaktSetu benchmark results\n\nMachine: {platform.processor() or platform.machine()}, "
             f"Python {platform.python_version()}, {platform.system()} {platform.release()}. "
             f"Seed {SEED}; data as of {TODAY.isoformat()}.\n"]
    for key, rows in sections.items():
        if rows:
            parts.append(f"## {titles[key]}\n\n{md_table(rows)}\n")
    (RESULTS / "summary.md").write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="RaktSetu core benchmarks")
    p.add_argument("--quick", action="store_true", help="fewer and smaller runs")
    p.add_argument("--only", choices=["heap", "dijkstra", "sizes", "cities"], action="append")
    args = p.parse_args()
    run = set(args.only or ["heap", "dijkstra", "sizes", "cities"])
    RESULTS.mkdir(parents=True, exist_ok=True)
    sections: dict[str, list[dict]] = {}

    if "heap" in run:
        print("Heap")
        sizes = [1_000, 10_000, 25_000] if args.quick else [1_000, 10_000, 25_000, 50_000, 75_000, 100_000]
        sections["heap"] = bench_heap(sizes, 2 if args.quick else 5)
        write_csv("heap.csv", sections["heap"])
        chart_heap(sections["heap"])

    if "dijkstra" in run:
        print("Dijkstra")
        starts = 20 if args.quick else 200
        rows = [bench_dijkstra("Synthetic 60 km grid", load_folder(DATA / "output"), starts)]
        real = DATA / "output_cities" / "ahmedabad"
        if (real / "meta.json").exists():
            rows.append(bench_dijkstra("Ahmedabad real roads", load_folder(real), starts))
        else:
            print("  (skipping real roads: run python -m data.import_cities --city ahmedabad first)")
        sections["dijkstra"] = rows
        write_csv("dijkstra.csv", rows)
        chart_dijkstra(rows)

    if "sizes" in run:
        print("Search by city size")
        searches = 30 if args.quick else 200
        rows = [bench_search(f"{size} km grid", build_state(load_folder(synthetic_city(size))), "synthetic", searches)
                for size in (30, 60, 100)]
        sections["sizes"] = rows
        write_csv("search_latency.csv", rows)
        chart_search(rows)

    if "cities" in run:
        print("Search on real roads")
        rows = []
        for folder in sorted((DATA / "output_cities").glob("*/meta.json")):
            city_id = folder.parent.name
            rows.append(bench_search(city_id.title(), build_state(load_folder(folder.parent), city_id), city_id,
                                     20 if args.quick else 100))
        if rows:
            sections["cities"] = rows
            write_csv("city_search.csv", rows)

    write_summary(sections)
    print(f"Results in {RESULTS}")


if __name__ == "__main__":
    main()
