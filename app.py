"""
Mini-Courier Planner — JSON API (backend only, no web pages).

    pip install -r requirements.txt
    python app.py

Endpoints
    GET  /api/datasets                     list the sample datasets
    GET  /api/plan?dataset=small           run the planner on a sample
         optional: &capacity=30 &sort=quick &two_opt=off
    POST /api/plan                         run the planner on a dataset sent as JSON
    GET  /api/benchmark                    saved Phase 4 benchmark results

Example
    curl "http://127.0.0.1:5000/api/plan?dataset=small"
    curl -X POST -H "Content-Type: application/json" --data @data/medium.json http://127.0.0.1:5000/api/plan
"""

import json
import os

from flask import Flask, jsonify, request

from courier.models import from_dict
from courier.planner import plan_delivery
from courier.sorting import ALGORITHMS

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
SAMPLES = ["small", "medium", "large"]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024      # request bodies up to 2 MB


def read_sample(name):
    if name not in SAMPLES:
        raise ValueError(f"Unknown dataset '{name}'. Choose one of {SAMPLES}")
    with open(os.path.join(DATA_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def options():
    """Read optional planner settings from the query string."""
    capacity = request.args.get("capacity", type=int)
    if capacity is not None and not 1 <= capacity <= 5000:
        raise ValueError("capacity must be between 1 and 5000 kg")
    sort = request.args.get("sort", "merge")
    if sort not in ALGORITHMS:
        raise ValueError(f"sort must be one of {list(ALGORITHMS)}")
    two_opt = request.args.get("two_opt", "on") != "off"
    return capacity, sort, two_opt


def to_json(r):
    """Convert the planner result into plain JSON (DP table omitted — it can be huge)."""
    pk = r["packing"]
    return {
        "dataset": r["dataset"],
        "capacity": r["capacity"],
        "sort_algorithm": r["sort_algorithm"],
        "graph": r["graph"],
        "sorted_parcels": [p.to_dict() for p in r["sorted_parcels"]],
        "packing": {
            "selected": [p.id for p in pk["selected"]],
            "rejected": [p.id for p in pk["rejected"]],
            "total_value": pk["total_value"],
            "total_weight": pk["total_weight"],
        },
        "greedy_baseline": {
            "selected": [p.id for p in r["greedy"]["selected"]],
            "total_value": r["greedy"]["total_value"],
            "total_weight": r["greedy"]["total_weight"],
        },
        "route": {
            "nearest_neighbour_tour": r["nn_tour"],
            "nearest_neighbour_length": r["nn_length"],
            "tour": r["tour"],
            "length": r["route_length"],
            "full_path": r["full_path"],
            "legs": r["legs"],
            "drops": r["drops"],
        },
        "timings_ms": r["timings_ms"],
    }


@app.errorhandler(ValueError)
def bad_input(exc):
    return jsonify({"error": str(exc)}), 400


@app.route("/")
@app.route("/api/datasets")
def datasets():
    return jsonify({"datasets": SAMPLES,
                    "endpoints": ["/api/datasets", "/api/plan", "/api/benchmark"]})


@app.route("/api/plan", methods=["GET", "POST"])
def api_plan():
    capacity, sort, two_opt = options()
    if request.method == "POST":
        raw = request.get_json(silent=True)
        if raw is None:
            raise ValueError("POST body must be a JSON dataset")
    else:
        raw = read_sample(request.args.get("dataset", "small"))
    try:
        ds = from_dict(raw)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Invalid dataset: {exc}")
    return jsonify(to_json(plan_delivery(ds, capacity, sort, use_two_opt=two_opt)))


@app.route("/api/benchmark")
def api_benchmark():
    path = os.path.join(ROOT, "results", "benchmark.json")
    if not os.path.exists(path):
        raise ValueError("No results yet — run: python benchmark.py")
    with open(path, encoding="utf-8") as f:
        return jsonify(json.load(f))


if __name__ == "__main__":
    app.run(debug=True)
