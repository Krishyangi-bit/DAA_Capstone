"""
Mini-Courier Planner — command-line interface.

    python main.py                                # small dataset, full trace
    python main.py data/large.json                # any dataset file
    python main.py data/medium.json --capacity 40 --sort quick --no-2opt
    python main.py data/small.json --show-table   # print the complete DP table
"""

import argparse

from courier.models import load_dataset
from courier.planner import plan_delivery
from courier.sorting import ALGORITHMS


def rule(title):
    print(f"\n{title}\n{'-' * len(title)}")


def print_parcels(parcels, limit=None):
    print(f"{'#':>3}  {'id':<6}{'dest':<7}{'kg':>4}{'value':>7}{'deadline':>10}{'prio':>6}")
    for i, p in enumerate(parcels[:limit] if limit else parcels, 1):
        print(f"{i:>3}  {p.id:<6}{p.destination:<7}{p.weight:>4}{p.value:>7}{p.deadline:>9}h{p.priority:>6}")
    if limit and len(parcels) > limit:
        print(f"  ... {len(parcels) - limit} more")


def print_dp_table(parcels, table, max_cols=None):
    """Rows = parcels considered so far, columns = capacity 0..W."""
    W = len(table[0]) - 1
    cols = list(range(W + 1)) if max_cols is None or W <= max_cols else \
        list(range(0, W + 1, max(1, W // max_cols)))
    print("      " + "".join(f"{w:>5}" for w in cols))
    print("   -  " + "".join(f"{table[0][w]:>5}" for w in cols))
    for i, p in enumerate(parcels, 1):
        print(f"{p.id:>5} " + "".join(f"{table[i][w]:>5}" for w in cols))


def main():
    ap = argparse.ArgumentParser(description="Mini-Courier Planner")
    ap.add_argument("dataset", nargs="?", default="data/small.json")
    ap.add_argument("--capacity", type=int, help="override van capacity (kg)")
    ap.add_argument("--sort", choices=ALGORITHMS.keys(), default="merge")
    ap.add_argument("--no-2opt", action="store_true", help="plain nearest-neighbour route")
    ap.add_argument("--show-table", action="store_true", help="print the whole DP table")
    args = ap.parse_args()

    ds = load_dataset(args.dataset)
    r = plan_delivery(ds, args.capacity, args.sort, use_two_opt=not args.no_2opt)
    big = len(ds.parcels) > 25

    print(f"MINI-COURIER PLANNER  |  dataset: {ds.name}  |  "
          f"{r['graph']['nodes']} nodes, {r['graph']['edges']} roads, "
          f"{len(ds.parcels)} parcels  |  capacity {r['capacity']} kg")

    rule(f"1. Parcels prioritised with {args.sort} sort  (deadline asc, priority desc, value desc)")
    print_parcels(r["sorted_parcels"], limit=15 if big else None)

    rule("2. Packing plan  (0/1 knapsack, dynamic programming)")
    if args.show_table or not big:
        print_dp_table(r["sorted_parcels"], r["packing"]["table"],
                       max_cols=None if args.show_table else 25)
        print()
    pk = r["packing"]
    print(f"Selected parcels : {', '.join(p.id for p in pk['selected'])}")
    print(f"Load             : {pk['total_weight']} / {r['capacity']} kg")
    print(f"Total value      : {pk['total_value']}   (greedy by value/weight: {r['greedy']['total_value']})")
    print(f"Left for next trip: {len(pk['rejected'])} parcels")

    rule("3. Route  (Dijkstra shortest paths + nearest-neighbour TSP)")
    print(f"Stops to visit    : {len(r['stops'])}")
    print(f"Nearest-neighbour : {' -> '.join(r['nn_tour'])}  =  {r['nn_length']} km")
    if not args.no_2opt:
        print(f"After 2-opt       : {' -> '.join(r['tour'])}  =  {r['route_length']} km")
    print("\nLegs (road-level path from Dijkstra):")
    for leg in r["legs"][:20]:
        drop = r["drops"].get(leg["to"], [])
        drop_txt = f"  drop {', '.join(drop)}" if drop else ""
        print(f"  {leg['from']:>5} -> {leg['to']:<5} {leg['distance']:>7.1f} km   "
              f"via {' > '.join(leg['path'])}{drop_txt}")
    if len(r["legs"]) > 20:
        print(f"  ... {len(r['legs']) - 20} more legs")
    print(f"\nTotal route length: {r['route_length']} km")

    rule("4. Runtime of each stage (ms)")
    for stage, ms in r["timings_ms"].items():
        print(f"  {stage:<10}{ms:>10.3f}")


if __name__ == "__main__":
    main()
