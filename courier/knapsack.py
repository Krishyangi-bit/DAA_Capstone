"""
Phase 2b — Box filling with 0/1 Knapsack (Dynamic Programming).

Problem: choose a subset of parcels whose total weight <= capacity W and
whose total value is as large as possible. A parcel is either taken whole
or left behind (0/1), so the greedy value/weight rule is NOT optimal.

Recurrence (i = first i parcels considered, w = capacity available):

    dp[0][w] = 0
    dp[i][w] = dp[i-1][w]                                    if weight_i > w
             = max(dp[i-1][w],                                 (skip parcel i)
                   dp[i-1][w - weight_i] + value_i)            (take parcel i)

Answer = dp[n][W]. The chosen parcels are recovered by walking back from
dp[n][W]: if dp[i][w] != dp[i-1][w] then parcel i was taken.

Time  O(n * W)   Space O(n * W) for the full table (needed for traceback).
"""


def knapsack_01(parcels, capacity):
    """
    Exact 0/1 knapsack.

    Returns a dict:
        selected     - list of chosen parcels (in the order they were given)
        rejected     - parcels left at the depot
        total_value  - optimal value
        total_weight - weight of the chosen parcels
        table        - the full DP table (list of n+1 rows of W+1 ints)
    """
    n = len(parcels)
    W = capacity
    dp = [[0] * (W + 1) for _ in range(n + 1)]

    # fill the table row by row
    for i in range(1, n + 1):
        wt = parcels[i - 1].weight
        val = parcels[i - 1].value
        prev = dp[i - 1]
        row = dp[i]
        for w in range(W + 1):
            row[w] = prev[w]                           # option 1: skip parcel i
            if wt <= w and prev[w - wt] + val > row[w]:
                row[w] = prev[w - wt] + val            # option 2: take parcel i

    # traceback to find which parcels were taken
    chosen = [False] * n
    w = W
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            chosen[i - 1] = True
            w -= parcels[i - 1].weight

    selected = [p for p, c in zip(parcels, chosen) if c]
    rejected = [p for p, c in zip(parcels, chosen) if not c]
    return {
        "selected": selected,
        "rejected": rejected,
        "total_value": dp[n][W],
        "total_weight": sum(p.weight for p in selected),
        "table": dp,
    }


def knapsack_value_1d(parcels, capacity):
    """
    Space-optimised variant used in Phase 4: keeps only ONE row, O(W) space.
    Iterating w from high to low ensures each parcel is used at most once.
    It returns only the optimal value (no traceback is possible without the table).
    """
    dp = [0] * (capacity + 1)
    for p in parcels:
        for w in range(capacity, p.weight - 1, -1):
            if dp[w - p.weight] + p.value > dp[w]:
                dp[w] = dp[w - p.weight] + p.value
    return dp[capacity]


def greedy_by_ratio(parcels, capacity):
    """
    Baseline for comparison: take parcels in decreasing value/weight order
    while they fit. O(n log n) but NOT always optimal for 0/1 knapsack.
    """
    order = sorted(parcels, key=lambda p: p.value / p.weight, reverse=True)
    selected, load = [], 0
    for p in order:
        if load + p.weight <= capacity:
            selected.append(p)
            load += p.weight
    return {"selected": selected,
            "total_value": sum(p.value for p in selected),
            "total_weight": load}
