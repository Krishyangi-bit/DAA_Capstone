"""
Phase 4 — Performance testing.

Measures how each component scales with input size and writes:
    results/benchmark.json      raw numbers (also shown on the website)
    docs/charts/*.png           runtime charts for the report

    python benchmark.py            # full run (~1 minute)
    python benchmark.py --quick    # fewer sizes / repeats

Experiments
  1. Sorting      insertion vs merge vs quick vs heap, n = 100 .. 5000
  2. Knapsack     2-D table vs 1-D optimised, growing n * W
  3. Dijkstra     single-source on random road graphs, V = 100 .. 3200
  4. TSP          nearest-neighbour vs NN + 2-opt: time and route quality,
                  and gap to the exact optimum for small k
  5. Pipeline     time of every stage on the small / medium / large datasets
"""

import argparse
import json
import math
import os
import random
import statistics
import time

import matplotlib
matplotlib.use("Agg")                       # draw to files, no window needed
import matplotlib.pyplot as plt             # noqa: E402

from courier.graph import Graph, dijkstra                                       # noqa: E402
from courier.knapsack import knapsack_01, knapsack_value_1d                     # noqa: E402
from courier.models import Parcel, load_dataset                                 # noqa: E402
from courier.planner import plan_delivery                                       # noqa: E402
from courier.sorting import ALGORITHMS                                          # noqa: E402
from courier.tsp import nearest_neighbour, two_opt, brute_force, tour_length    # noqa: E402
from data.generate import generate                                              # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(ROOT, "docs", "charts")
RESULT_FILE = os.path.join(ROOT, "results", "benchmark.json")

# Validated categorical palette, used in fixed order (see README "Charts")
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"


def time_ms(fn, *args, repeats=3):
    """Median wall-clock time of fn(*args) in milliseconds."""
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn(*args)
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def random_parcels(n, rng):
    return [Parcel(f"P{i}", "X", rng.randint(1, 12), rng.randint(5, 80),
                   rng.randint(1, 12), rng.randint(1, 5)) for i in range(n)]


# ------------------------------------------------------------------ experiments
def bench_sorting(sizes, repeats):
    rng = random.Random(1)
    out = {name: [] for name in ALGORITHMS}
    key = lambda p: p.sort_key()                                   # noqa: E731
    for n in sizes:
        parcels = random_parcels(n, rng)
        for name, fn in ALGORITHMS.items():
            if name == "insertion" and n > 2000:                   # O(n^2): too slow to matter
                out[name].append(None)
                continue
            out[name].append(round(time_ms(fn, parcels, key, repeats=repeats), 3))
        print(f"  sorting n={n:<5} " + "  ".join(f"{k}={v[-1]}" for k, v in out.items()))
    return {"sizes": sizes, "times_ms": out}


def bench_knapsack(configs, repeats):
    rng = random.Random(2)
    res = {"cells": [], "n": [], "W": [], "table_2d": [], "row_1d": []}
    for n, W in configs:
        parcels = random_parcels(n, rng)
        res["n"].append(n)
        res["W"].append(W)
        res["cells"].append(n * W)
        res["table_2d"].append(round(time_ms(knapsack_01, parcels, W, repeats=repeats), 3))
        res["row_1d"].append(round(time_ms(knapsack_value_1d, parcels, W, repeats=repeats), 3))
        print(f"  knapsack n={n} W={W}  2d={res['table_2d'][-1]}  1d={res['row_1d'][-1]}")
    return res


def bench_dijkstra(sizes, repeats):
    res = {"nodes": [], "edges": [], "times_ms": []}
    for v in sizes:
        data = generate("bench", v, 1, 10, seed=v)
        g = Graph()
        for e in data["edges"]:
            g.add_edge(e["from"], e["to"], e["distance"])
        res["nodes"].append(g.num_nodes)
        res["edges"].append(g.num_edges)
        res["times_ms"].append(round(time_ms(dijkstra, g, "D", repeats=repeats), 3))
        print(f"  dijkstra V={g.num_nodes} E={g.num_edges}  {res['times_ms'][-1]} ms")
    return res


def bench_tsp(sizes, repeats):
    """Random points in the unit square; Euclidean distances are a metric."""
    rng = random.Random(4)
    res = {"stops": [], "nn_ms": [], "two_opt_ms": [], "nn_len": [], "two_opt_len": []}
    for k in sizes:
        pts = {str(i): (rng.random(), rng.random()) for i in range(k + 1)}
        m = {a: {b: math.dist(pts[a], pts[b]) for b in pts} for a in pts}
        stops = [s for s in pts if s != "0"]
        nn = nearest_neighbour("0", stops, m)
        opt = two_opt(nn, m)
        res["stops"].append(k)
        res["nn_ms"].append(round(time_ms(nearest_neighbour, "0", stops, m, repeats=repeats), 3))
        res["two_opt_ms"].append(round(time_ms(two_opt, nn, m, repeats=repeats), 3))
        res["nn_len"].append(round(tour_length(nn, m), 4))
        res["two_opt_len"].append(round(tour_length(opt, m), 4))
        print(f"  tsp k={k}  nn={res['nn_ms'][-1]}ms  2opt={res['two_opt_ms'][-1]}ms  "
              f"improvement={100 * (1 - res['two_opt_len'][-1] / res['nn_len'][-1]):.1f}%")

    # quality versus the exact optimum (brute force is O(k!), so k <= 8)
    gaps = {"stops": [], "nn_gap_pct": [], "two_opt_gap_pct": []}
    for k in range(3, 9):
        nn_g, opt_g = [], []
        for _ in range(20):
            pts = {str(i): (rng.random(), rng.random()) for i in range(k + 1)}
            m = {a: {b: math.dist(pts[a], pts[b]) for b in pts} for a in pts}
            stops = [s for s in pts if s != "0"]
            best = tour_length(brute_force("0", stops, m), m)
            nn = nearest_neighbour("0", stops, m)
            nn_g.append(100 * (tour_length(nn, m) / best - 1))
            opt_g.append(100 * (tour_length(two_opt(nn, m), m) / best - 1))
        gaps["stops"].append(k)
        gaps["nn_gap_pct"].append(round(statistics.mean(nn_g), 2))
        gaps["two_opt_gap_pct"].append(round(statistics.mean(opt_g), 2))
    res["optimality_gap"] = gaps
    return res


def bench_pipeline(repeats):
    res = {}
    for name in ("small", "medium", "large"):
        ds = load_dataset(os.path.join(ROOT, "data", f"{name}.json"))
        runs = [plan_delivery(ds)["timings_ms"] for _ in range(repeats)]
        res[name] = {stage: round(statistics.median(r[stage] for r in runs), 3)
                     for stage in runs[0]}
        res[name]["parcels"] = len(ds.parcels)
        res[name]["nodes"] = len(ds.nodes)
        print(f"  pipeline {name}: {res[name]}")
    return res


# ------------------------------------------------------------------ charts
def style(ax, title, xlabel, ylabel):
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12, fontweight="semibold")
    ax.set_xlabel(xlabel, color=INK_2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK_2, fontsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)


def line(ax, xs, ys, label, color):
    pts = [(x, y) for x, y in zip(xs, ys) if y is not None]
    ax.plot(*zip(*pts), color=color, linewidth=2, marker="o", markersize=4,
            markeredgecolor="white", markeredgewidth=1, label=label)
    # direct label at the end of each line (text in ink, not series color)
    ax.annotate(label, pts[-1], xytext=(6, 0), textcoords="offset points",
                va="center", fontsize=8, color=INK_2)


def save(fig, name):
    os.makedirs(CHART_DIR, exist_ok=True)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, name), dpi=150, facecolor="white")
    plt.close(fig)


def draw_charts(r):
    s = r["sorting"]
    fig, ax = plt.subplots(figsize=(7, 4))
    for (name, ys), c in zip(s["times_ms"].items(), SERIES):
        line(ax, s["sizes"], ys, name, c)
    style(ax, "Sorting parcels — runtime vs n", "number of parcels (n)", "time (ms)")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_2)
    save(fig, "sorting.png")

    k = r["knapsack"]
    fig, ax = plt.subplots(figsize=(7, 4))
    line(ax, k["cells"], k["table_2d"], "2-D table", SERIES[0])
    line(ax, k["cells"], k["row_1d"], "1-D row", SERIES[1])
    style(ax, "0/1 Knapsack DP — runtime vs n × W", "table cells (n × W)", "time (ms)")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_2)
    save(fig, "knapsack.png")

    d = r["dijkstra"]
    fig, ax = plt.subplots(figsize=(7, 4))
    line(ax, d["nodes"], d["times_ms"], "Dijkstra (heap)", SERIES[0])
    style(ax, "Dijkstra — runtime vs graph size", "nodes (V)", "time (ms)")
    save(fig, "dijkstra.png")

    t = r["tsp"]
    fig, ax = plt.subplots(figsize=(7, 4))
    line(ax, t["stops"], t["nn_ms"], "nearest neighbour", SERIES[0])
    line(ax, t["stops"], t["two_opt_ms"], "2-opt pass", SERIES[1])
    style(ax, "Route construction — runtime vs stops", "stops (k)", "time (ms)")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_2)
    save(fig, "tsp_runtime.png")

    g = t["optimality_gap"]
    fig, ax = plt.subplots(figsize=(7, 4))
    line(ax, g["stops"], g["nn_gap_pct"], "nearest neighbour", SERIES[0])
    line(ax, g["stops"], g["two_opt_gap_pct"], "NN + 2-opt", SERIES[1])
    style(ax, "Route quality — % longer than the exact optimum", "stops (k)", "gap to optimum (%)")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_2)
    save(fig, "tsp_quality.png")

    p = r["pipeline"]
    stages = ["sorting", "knapsack", "dijkstra", "tsp_nn", "two_opt"]
    names = list(p.keys())
    fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.16
    for i, (stage, c) in enumerate(zip(stages, SERIES + ["#e87ba4"])):
        xs = [j + (i - 2) * (width + 0.02) for j in range(len(names))]
        ax.bar(xs, [p[n][stage] for n in names], width, color=c, label=stage)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([f"{n}\n{p[n]['parcels']} parcels, {p[n]['nodes']} nodes" for n in names])
    style(ax, "Pipeline — time per stage on each dataset", "", "time (ms)")
    ax.grid(False, axis="x")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_2, ncol=5, loc="upper left")
    save(fig, "pipeline.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    repeats = 1 if args.quick else 3

    sort_sizes = [100, 500, 1000, 2000] if args.quick else [100, 250, 500, 1000, 2000, 3500, 5000]
    knap = [(20, 50), (50, 100), (100, 200)] if args.quick else \
        [(20, 50), (50, 100), (100, 200), (150, 300), (200, 400), (300, 500)]
    graph_sizes = [100, 400, 800] if args.quick else [100, 200, 400, 800, 1600, 3200]
    tsp_sizes = [10, 25, 50] if args.quick else [10, 25, 50, 100, 150, 200]

    print("Running benchmarks ...")
    results = {
        "sorting": bench_sorting(sort_sizes, repeats),
        "knapsack": bench_knapsack(knap, repeats),
        "dijkstra": bench_dijkstra(graph_sizes, repeats),
        "tsp": bench_tsp(tsp_sizes, repeats),
        "pipeline": bench_pipeline(max(repeats, 5)),
    }
    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    draw_charts(results)
    print(f"\nSaved {RESULT_FILE} and charts in {CHART_DIR}")


if __name__ == "__main__":
    main()
