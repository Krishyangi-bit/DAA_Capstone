"""
The integrated Mini-Courier Planner pipeline.

    sort parcels  ->  knapsack DP  ->  Dijkstra distance matrix  ->  NN TSP (+2-opt)

`plan_delivery` runs every stage, times it with time.perf_counter, and
returns a plain dictionary that the CLI, the web UI and the tests all use.
"""

import time

from .graph import Graph, distance_matrix
from .knapsack import knapsack_01, greedy_by_ratio
from .sorting import prioritise
from .tsp import nearest_neighbour, two_opt, tour_length, expand_route


def _timed(fn, *args, **kwargs):
    """Run fn and return (result, elapsed milliseconds)."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, (time.perf_counter() - start) * 1000


def plan_delivery(dataset, capacity=None, sort_algorithm="merge", use_two_opt=True):
    capacity = capacity or dataset.capacity
    timings = {}

    # 1) prioritise parcels by deadline / priority / value
    ordered, timings["sorting"] = _timed(prioritise, dataset.parcels, sort_algorithm)

    # 2) choose the best set of parcels for one trip (exact DP)
    packing, timings["knapsack"] = _timed(knapsack_01, ordered, capacity)
    greedy = greedy_by_ratio(ordered, capacity)       # baseline, for comparison only

    # 3) shortest paths between depot and every stop
    graph = Graph.from_dataset(dataset)
    stops = list(dict.fromkeys(p.destination for p in packing["selected"]))
    points = [dataset.depot] + [s for s in stops if s != dataset.depot]
    (matrix, paths), timings["dijkstra"] = _timed(distance_matrix, graph, points)

    # 4) visiting order with nearest neighbour, then optional 2-opt polish
    nn_tour, timings["tsp_nn"] = _timed(nearest_neighbour, dataset.depot, points, matrix)
    nn_length = tour_length(nn_tour, matrix)
    if use_two_opt:
        tour, timings["two_opt"] = _timed(two_opt, nn_tour, matrix)
    else:
        tour, timings["two_opt"] = nn_tour, 0.0
    length = tour_length(tour, matrix)

    timings["total"] = sum(timings.values())

    # which parcels are dropped at each stop, in visiting order
    drops = {}
    for p in packing["selected"]:
        drops.setdefault(p.destination, []).append(p.id)

    legs = [{"from": tour[i], "to": tour[i + 1],
             "distance": round(matrix[tour[i]][tour[i + 1]], 2),
             "path": paths[tour[i]][tour[i + 1]]}
            for i in range(len(tour) - 1)]

    return {
        "dataset": dataset.name,
        "capacity": capacity,
        "sort_algorithm": sort_algorithm,
        "graph": {"nodes": graph.num_nodes, "edges": graph.num_edges},
        "sorted_parcels": ordered,
        "packing": packing,
        "greedy": greedy,
        "stops": stops,
        "nn_tour": nn_tour,
        "nn_length": round(nn_length, 2),
        "tour": tour,
        "route_length": round(length, 2),
        "full_path": expand_route(tour, paths),
        "legs": legs,
        "drops": drops,
        "timings_ms": {k: round(v, 3) for k, v in timings.items()},
    }
