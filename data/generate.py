"""
Sample dataset generator.

Creates connected random road networks with parcels, so the planner can be
tested on small, medium and large inputs (Phase 4).

    python data/generate.py                 # regenerate medium.json and large.json
    python data/generate.py --nodes 80 --parcels 120 --capacity 60 --out data/custom.json

Graph construction:
  * nodes are random points on a 100 x 100 map, depot "D" in the centre
  * each node is joined to its 3 nearest neighbours (sparse, road-like)
  * extra edges are added until the graph is connected
  * road distance = straight-line distance x a random detour factor (1.0 - 1.3)
"""

import argparse
import json
import math
import os
import random


def _connect_components(nodes, edges, rng):
    """Join disconnected pieces with the shortest possible bridge each time."""
    def components():
        parent = {n["id"]: n["id"] for n in nodes}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for a, b in edges:
            parent[find(a)] = find(b)
        groups = {}
        for n in nodes:
            groups.setdefault(find(n["id"]), []).append(n)
        return list(groups.values())

    comps = components()
    while len(comps) > 1:
        first, rest = comps[0], [n for c in comps[1:] for n in c]
        a, b = min(((x, y) for x in first for y in rest),
                   key=lambda pair: math.dist((pair[0]["x"], pair[0]["y"]),
                                              (pair[1]["x"], pair[1]["y"])))
        edges.add(tuple(sorted((a["id"], b["id"]))))
        comps = components()


def generate(name, num_nodes, num_parcels, capacity, seed):
    rng = random.Random(seed)
    nodes = [{"id": "D", "name": "Depot", "x": 50.0, "y": 50.0}]
    for i in range(1, num_nodes):
        nodes.append({"id": f"N{i:03d}", "name": f"Customer {i}",
                      "x": round(rng.uniform(3, 97), 1), "y": round(rng.uniform(3, 97), 1)})

    pos = {n["id"]: (n["x"], n["y"]) for n in nodes}
    edges = set()
    for n in nodes:
        nearest = sorted((m for m in nodes if m["id"] != n["id"]),
                         key=lambda m: math.dist(pos[n["id"]], pos[m["id"]]))[:3]
        for m in nearest:
            edges.add(tuple(sorted((n["id"], m["id"]))))
    _connect_components(nodes, edges, rng)

    edge_list = [{"from": a, "to": b,
                  "distance": round(math.dist(pos[a], pos[b]) * rng.uniform(1.0, 1.3), 1)}
                 for a, b in sorted(edges)]

    customers = [n["id"] for n in nodes if n["id"] != "D"]
    parcels = []
    for i in range(1, num_parcels + 1):
        priority = rng.randint(1, 5)
        weight = rng.randint(1, 12)
        parcels.append({
            "id": f"P{i:03d}",
            "destination": rng.choice(customers),
            "weight": weight,
            # value grows with priority and (a little) with weight
            "value": priority * 10 + weight * 2 + rng.randint(0, 10),
            "deadline": rng.randint(1, 12),
            "priority": priority,
        })

    return {"name": name, "depot": "D", "capacity": capacity,
            "nodes": nodes, "edges": edge_list, "parcels": parcels}


def save(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {path}: {len(data['nodes'])} nodes, {len(data['edges'])} edges, "
          f"{len(data['parcels'])} parcels, capacity {data['capacity']}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Generate courier datasets")
    ap.add_argument("--nodes", type=int)
    ap.add_argument("--parcels", type=int)
    ap.add_argument("--capacity", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.nodes and args.parcels and args.out:
        name = os.path.splitext(os.path.basename(args.out))[0]
        save(generate(name, args.nodes, args.parcels, args.capacity, args.seed), args.out)
    else:
        save(generate("medium", 30, 40, 50, seed=11), os.path.join(here, "medium.json"))
        save(generate("large", 120, 200, 120, seed=23), os.path.join(here, "large.json"))
