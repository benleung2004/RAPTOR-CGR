"""Execute every example graph used in the three answers and print what really happens.

    python comparisons/shortest-paths/verify.py
"""

import math


def bellman_ford(vertices, edges, source):
    """Edges are relaxed in the given order, updates take effect immediately (as in all three answers)."""
    d = {v: math.inf for v in vertices}
    d[source] = 0
    passes = []
    for _ in range(len(vertices) - 1):
        changed = False
        for u, v, w in edges:
            if d[u] + w < d[v]:
                d[v] = d[u] + w
                changed = True
        passes.append(dict(d))
        if not changed:
            break
    negative_cycle = any(d[u] + w < d[v] for u, v, w in edges)
    return passes, negative_cycle


def dijkstra(vertices, edges, source, skip_settled):
    """skip_settled=False: relax every edge (CLRS / both fast answers' pseudocode).
    skip_settled=True: only relax vertices still in the queue (deep answer's `if v in Q`)."""
    adj = {v: [] for v in vertices}
    for u, v, w in edges:
        adj[u].append((v, w))
    d = {v: math.inf for v in vertices}
    d[source] = 0
    queue = set(vertices)
    while queue:
        u = min(queue, key=lambda x: d[x])
        queue.remove(u)
        for v, w in adj[u]:
            if skip_settled and v not in queue:
                continue
            if d[u] + w < d[v]:
                d[v] = d[u] + w
    return d


def true_distances(vertices, edges, source):
    return bellman_ford(vertices, edges, source)[0][-1]


def show_dijkstra(name, vertices, edges):
    s = vertices[0]
    print(f"\n{name}")
    print("  true shortest distances        :", true_distances(vertices, edges, s))
    print("  Dijkstra, relax every edge     :", dijkstra(vertices, edges, s, skip_settled=False))
    print("  Dijkstra, skip settled vertices:", dijkstra(vertices, edges, s, skip_settled=True))


def show_bellman_ford(name, vertices, edges):
    passes, neg = bellman_ford(vertices, edges, vertices[0])
    print(f"\n{name}")
    for i, p in enumerate(passes, 1):
        print(f"  pass {i}: {p}")
    print("  negative cycle reachable:", neg)


if __name__ == "__main__":
    print("=== Dijkstra counterexamples ===")
    show_dijkstra("Tutor (fast), first attempt: s->a 1, s->b 2, a->b -2", "sab",
                  [("s", "a", 1), ("s", "b", 2), ("a", "b", -2)])
    show_dijkstra("Tutor (fast), second attempt: s->a 1, s->b 2, b->a -2", "sab",
                  [("s", "a", 1), ("s", "b", 2), ("b", "a", -2)])
    show_dijkstra("Perplexity: S->A 3, S->B 4, B->A -2", "SAB",
                  [("S", "A", 3), ("S", "B", 4), ("B", "A", -2)])
    show_dijkstra("Tutor (deep): A->B 1, A->C 2, C->B -2", "ABC",
                  [("A", "B", 1), ("A", "C", 2), ("C", "B", -2)])
    show_dijkstra("Counterexample that fails for EVERY Dijkstra variant (error propagates to C)", "SABC",
                  [("S", "A", 3), ("S", "B", 4), ("B", "A", -2), ("A", "C", 1)])

    print("\n=== Bellman-Ford traces ===")
    show_bellman_ford("Tutor (fast)", "sabcd",
                      [("s", "a", 6), ("s", "b", 7), ("a", "c", 5), ("a", "b", 8), ("b", "c", -3),
                       ("b", "d", 9), ("c", "d", 7), ("d", "s", 2)])
    show_bellman_ford("Perplexity", "SABCD",
                      [("S", "A", 6), ("S", "B", 7), ("A", "B", 8), ("A", "C", 5), ("A", "D", -4),
                       ("B", "C", -3), ("B", "D", 9), ("C", "A", -2), ("D", "S", 2), ("D", "C", 7)])
    show_bellman_ford("Tutor (deep)", "sabcd",
                      [("b", "c", 2), ("c", "d", 1), ("a", "b", -3), ("s", "b", 5), ("s", "a", 4)])
    show_bellman_ford("Tutor (fast) with the prompt-only fix (rejected): contains a negative cycle", "sabcd",
                      [("s", "a", 6), ("s", "b", 7), ("a", "c", 5), ("a", "d", -4), ("b", "a", 8),
                       ("b", "d", 9), ("c", "d", -3), ("d", "a", 2)])
