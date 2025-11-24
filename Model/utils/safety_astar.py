# Model/utils/safety_astar.py
import heapq
from .geometry_utils import haversine

def a_star_single(graph, start, goal, danger_weight):
    pq = [(0, 0, start)]
    parent = {start: None}
    g_score = {start: 0}

    while pq:
        f, g, node = heapq.heappop(pq)

        if node == goal:
            path = []
            while node is not None:
                path.append(node)
                node = parent[node]
            return list(reversed(path)), g

        for nxt, dist in graph.get_neighbors(node):
            risk = graph.risk.get((node, nxt), 0.0)
            cost = dist + risk * danger_weight
            new_g = g + cost

            if nxt not in g_score or new_g < g_score[nxt]:
                g_score[nxt] = new_g
                parent[nxt] = node

                # Heuristic: straight-line distance (meters)
                h = haversine(nxt[0], nxt[1], goal[0], goal[1])
                heapq.heappush(pq, (new_g + h, new_g, nxt))

    return None, float("inf")


def k_safe_paths(graph, start, goal, k=3, danger_weight=2000):
    # 1. First safest path (for now)
    first_path, first_cost = a_star_single(graph, start, goal, danger_weight)
    if not first_path:
        return []

    routes = [{
        "path": first_path,
        "cost": first_cost
    }]

    candidates = []

    for path_index in range(1, k):
        prev_path = routes[-1]["path"]

        for j in range(len(prev_path) - 1):
            spur_node = prev_path[j]
            root_path = prev_path[:j + 1]

            removed_edges = []
            for r in routes:
                if r["path"][:j + 1] == root_path and j + 1 < len(r["path"]):
                    a = r["path"][j]
                    b = r["path"][j + 1]
                    if graph.has_edge(a, b):
                        removed = graph.remove_edge(a, b)
                        if removed:
                            removed_edges.append((a, b))

            spur_path, spur_cost = a_star_single(graph, spur_node, goal, danger_weight)
            for a, b in removed_edges:
                graph.restore_edge(a, b)

            if spur_path:
                new_path = root_path[:-1] + spur_path
                root_cost = 0.0
                for x in range(len(root_path) - 1):
                    a = root_path[x]
                    b = root_path[x + 1]
                    dist = haversine(a[0], a[1], b[0], b[1])
                    r = graph.risk.get((a, b), 0.0)
                    root_cost += dist + r * danger_weight

                total_cost = root_cost + spur_cost

                if not any(p["path"] == new_path for p in candidates) and not any(p["path"] == new_path for p in routes):
                    candidates.append({
                        "path": new_path,
                        "cost": total_cost
                    })

        if not candidates:
            break

        candidates.sort(key=lambda x: x["cost"])
        routes.append(candidates.pop(0))

    return routes

