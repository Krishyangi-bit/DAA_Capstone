"""
Correctness tests (Phase 4). Run with:

    python -m unittest discover tests -v

Each algorithm is checked against a simple, obviously-correct reference:
  sorting   -> Python's built-in sorted()
  knapsack  -> brute force over every subset
  dijkstra  -> hand-worked example + Bellman-Ford style relaxation
  TSP       -> brute force over every permutation (heuristic must be valid and >= optimum)
"""

import itertools
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from courier.graph import Graph, dijkstra, reconstruct_path, distance_matrix  # noqa: E402
from courier.knapsack import knapsack_01, knapsack_value_1d, greedy_by_ratio  # noqa: E402
from courier.models import Parcel, load_dataset, from_dict                    # noqa: E402
from courier.planner import plan_delivery                                      # noqa: E402
from courier.sorting import ALGORITHMS, prioritise                             # noqa: E402
from courier.tsp import nearest_neighbour, two_opt, brute_force, tour_length   # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def make_parcel(i, weight, value, deadline=1, priority=1):
    return Parcel(f"P{i}", "X", weight, value, deadline, priority)


class SortingTests(unittest.TestCase):
    def test_matches_builtin_on_random_lists(self):
        rng = random.Random(1)
        for _ in range(300):
            data = [rng.randint(-100, 100) for _ in range(rng.randint(0, 50))]
            for name, fn in ALGORITHMS.items():
                self.assertEqual(fn(data), sorted(data), name)

    def test_edge_cases(self):
        for name, fn in ALGORITHMS.items():
            self.assertEqual(fn([]), [], name)
            self.assertEqual(fn([7]), [7], name)
            self.assertEqual(fn([3, 3, 3]), [3, 3, 3], name)
            self.assertEqual(fn(list(range(30, 0, -1))), list(range(1, 31)), name)

    def test_input_not_modified(self):
        data = [5, 1, 4]
        for fn in ALGORITHMS.values():
            fn(data)
        self.assertEqual(data, [5, 1, 4])

    def test_merge_sort_is_stable(self):
        # equal keys must keep their original order
        parcels = [make_parcel(i, 1, 10, deadline=2, priority=3) for i in range(10)]
        out = prioritise(parcels, "merge")
        self.assertEqual([p.id for p in out], [p.id for p in parcels])

    def test_parcel_priority_order(self):
        a = Parcel("a", "X", 1, 10, deadline=5, priority=5)
        b = Parcel("b", "X", 1, 10, deadline=2, priority=1)
        c = Parcel("c", "X", 1, 10, deadline=2, priority=4)
        self.assertEqual([p.id for p in prioritise([a, b, c])], ["c", "b", "a"])


class KnapsackTests(unittest.TestCase):
    def brute(self, parcels, W):
        best = 0
        for r in range(len(parcels) + 1):
            for combo in itertools.combinations(parcels, r):
                if sum(p.weight for p in combo) <= W:
                    best = max(best, sum(p.value for p in combo))
        return best

    def test_matches_brute_force(self):
        rng = random.Random(2)
        for _ in range(150):
            ps = [make_parcel(i, rng.randint(1, 10), rng.randint(1, 60))
                  for i in range(rng.randint(0, 10))]
            W = rng.randint(1, 30)
            res = knapsack_01(ps, W)
            self.assertEqual(res["total_value"], self.brute(ps, W))
            self.assertLessEqual(res["total_weight"], W)
            self.assertEqual(sum(p.value for p in res["selected"]), res["total_value"])
            self.assertEqual(knapsack_value_1d(ps, W), res["total_value"])

    def test_textbook_example_where_greedy_fails(self):
        ps = [make_parcel(1, 10, 60), make_parcel(2, 20, 100), make_parcel(3, 30, 120)]
        self.assertEqual(knapsack_01(ps, 50)["total_value"], 220)
        self.assertEqual(greedy_by_ratio(ps, 50)["total_value"], 160)

    def test_nothing_fits(self):
        res = knapsack_01([make_parcel(1, 9, 10)], 5)
        self.assertEqual(res["selected"], [])
        self.assertEqual(res["total_value"], 0)


class DijkstraTests(unittest.TestCase):
    def setUp(self):
        self.g = Graph()
        for u, v, d in [("A", "B", 4), ("A", "C", 1), ("C", "B", 2),
                        ("B", "D", 5), ("C", "D", 8)]:
            self.g.add_edge(u, v, d)
        self.g.add_node("Z")       # isolated node

    def test_hand_worked_example(self):
        dist, prev = dijkstra(self.g, "A")
        self.assertEqual(dist, {"A": 0, "B": 3, "C": 1, "D": 8, "Z": math.inf})
        self.assertEqual(reconstruct_path(prev, "A", "D"), ["A", "C", "B", "D"])

    def test_unreachable(self):
        _, prev = dijkstra(self.g, "A")
        self.assertEqual(reconstruct_path(prev, "A", "Z"), [])

    def test_against_bellman_ford_on_dataset(self):
        ds = load_dataset(os.path.join(DATA, "medium.json"))
        g = Graph.from_dataset(ds)
        dist, _ = dijkstra(g, ds.depot)
        ref = {v: math.inf for v in g.adj}
        ref[ds.depot] = 0
        for _ in range(g.num_nodes - 1):
            for u in g.adj:
                for v, w in g.adj[u]:
                    ref[v] = min(ref[v], ref[u] + w)
        for v in g.adj:
            self.assertAlmostEqual(dist[v], ref[v])

    def test_matrix_is_symmetric(self):
        m, paths = distance_matrix(self.g, ["A", "B", "D"])
        self.assertEqual(m["A"]["D"], m["D"]["A"])
        self.assertEqual(paths["D"]["A"], ["D", "B", "C", "A"])


class TSPTests(unittest.TestCase):
    def test_heuristics_valid_and_not_better_than_optimum(self):
        rng = random.Random(3)
        for _ in range(60):
            pts = {str(i): (rng.random(), rng.random()) for i in range(rng.randint(2, 8))}
            m = {a: {b: math.dist(pts[a], pts[b]) for b in pts} for a in pts}
            stops = [k for k in pts if k != "0"]
            nn = nearest_neighbour("0", stops, m)
            opt2 = two_opt(nn, m)
            best = brute_force("0", stops, m)
            for tour in (nn, opt2):
                self.assertEqual(tour[0], "0")
                self.assertEqual(tour[-1], "0")
                self.assertCountEqual(tour[1:-1], stops)
            self.assertLessEqual(tour_length(best, m), tour_length(opt2, m) + 1e-9)
            self.assertLessEqual(tour_length(opt2, m), tour_length(nn, m) + 1e-9)


class PlannerTests(unittest.TestCase):
    def test_small_dataset_end_to_end(self):
        r = plan_delivery(load_dataset(os.path.join(DATA, "small.json")))
        self.assertEqual(r["packing"]["total_value"], 215)
        self.assertLessEqual(r["packing"]["total_weight"], 24)
        self.assertEqual(r["tour"][0], "D")
        self.assertEqual(r["tour"][-1], "D")
        self.assertCountEqual(r["tour"][1:-1], r["stops"])
        self.assertAlmostEqual(r["route_length"], sum(l["distance"] for l in r["legs"]))

    def test_all_datasets_and_sorts(self):
        for name in ("small", "medium", "large"):
            ds = load_dataset(os.path.join(DATA, f"{name}.json"))
            values = {plan_delivery(ds, sort_algorithm=s)["packing"]["total_value"]
                      for s in ALGORITHMS}
            self.assertEqual(len(values), 1, f"sort choice changed the optimum on {name}")

    def test_validation_rejects_bad_input(self):
        bad = {"depot": "D", "capacity": 10, "nodes": [{"id": "D", "x": 0, "y": 0}],
               "edges": [], "parcels": [{"id": "P1", "destination": "Q", "weight": 1,
                                         "value": 1, "deadline": 1, "priority": 1}]}
        with self.assertRaises(ValueError):
            from_dict(bad)


if __name__ == "__main__":
    unittest.main()
