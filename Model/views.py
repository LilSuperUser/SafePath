# Model/views.py

from rest_framework.decorators import api_view
from rest_framework.response import Response
import logging

from .utils.crime_loader import load_crime_data
from .utils.crime_scoring import summarize_crime_for_segment
from .utils.osrm_client import get_osrm_edges
from .utils.safety_graph import RoadGraph
from .utils.safety_astar import k_safe_paths
logger = logging.getLogger("safepath")

@api_view(["GET"])
def safe_route(request):
    try:
        start_lat = float(request.GET.get("start_lat"))
        start_lon = float(request.GET.get("start_lon"))
        end_lat = float(request.GET.get("end_lat"))
        end_lon = float(request.GET.get("end_lon"))
    except Exception:
        return Response({"error": "Missing or invalid coordinates"}, status=400)

    # 1. Crime data
    crime_df = load_crime_data()

    # 2. OSRM routes
    try:
        shortest_route, start_node, goal_node, edges, all_routes = get_osrm_edges(
            start_lat, start_lon, end_lat, end_lon
        )
    except Exception as e:
        logger.exception("OSRM error: %s", e)
        return Response({"error": f"OSRM error: {e}"}, status=500)

    shortest_osrm_route = [[p[0], p[1]] for p in shortest_route]

    # 3. Build graph
    graph = RoadGraph()
    segment_risks_map = {}

    # add edges from OSRM alternatives (edges is list of (a,b))
    for a, b in edges:
        graph.add_edge(a, b)

    # 4. Score segments once (map keys use 6-decimal formatting to match frontend)
    for a, b in edges:
        # ensure tuple types
        a_t = (float(a[0]), float(a[1]))
        b_t = (float(b[0]), float(b[1]))

        key_forward = f"{a_t[0]:.6f},{a_t[1]:.6f}|{b_t[0]:.6f},{b_t[1]:.6f}"
        key_backward = f"{b_t[0]:.6f},{b_t[1]:.6f}|{a_t[0]:.6f},{a_t[1]:.6f}"

        # Avoid recomputing the same segment twice
        if key_forward in segment_risks_map or key_backward in segment_risks_map:
            continue

        risk, explanation = summarize_crime_for_segment(a_t, b_t, crime_df)
        graph.set_risk(a_t, b_t, risk)

        segment_risks_map[key_forward] = risk
        segment_risks_map[key_backward] = risk

    # 5. MULTIPLE A* SAFE PATHS (K=3) - guard against failures
    try:
        k_paths = k_safe_paths(graph, start_node, goal_node, k=3, danger_weight=2000)
    except Exception as e:
        logger.exception("A* error: %s", e)
        k_paths = []

    if not k_paths:
        # fallback: return OSRM primary route only with heuristics
        return Response({
            "shortest_osrm_route": shortest_osrm_route,
            "safe_osrm_alternatives": [],
            "recommended_safe_route": {"avg_risk": None, "route": shortest_osrm_route},
            "astar_safe_path": shortest_osrm_route,
            "astar_extra_paths": [],
            "segment_risks_map": segment_risks_map,
            "crime_hotspots": [],
            "all_osrm_routes": all_routes,
            "segments": len(edges),
            "graph_nodes": len(graph.edges)
        })

    astar_main_path = [[p[0], p[1]] for p in k_paths[0]["path"]]
    astar_extra = [
        {
            "cost": item["cost"],
            "path": [[p[0], p[1]] for p in item["path"]]
        }
        for item in k_paths[1:]
    ]

    # 6. Safest OSRM alternative
    safe_osrm_alts = []
    for route in all_routes:
        total_r = 0.0
        seg_count = 0

        for i in range(len(route) - 1):
            a = (float(route[i][0]), float(route[i][1]))
            b = (float(route[i + 1][0]), float(route[i + 1][1]))

            k1 = f"{a[0]:.6f},{a[1]:.6f}|{b[0]:.6f},{b[1]:.6f}"
            k2 = f"{b[0]:.6f},{b[1]:.6f}|{a[0]:.6f},{a[1]:.6f}"
            r = segment_risks_map.get(k1)
            if r is None:
                r = segment_risks_map.get(k2)

            if r is None:
                # compute on-the-fly (rare)
                r, _ = summarize_crime_for_segment(a, b, crime_df)

            total_r += r
            seg_count += 1

        avg_risk = total_r / seg_count if seg_count else 0.0
        safe_osrm_alts.append({
            "avg_risk": avg_risk,
            "route": [[p[0], p[1]] for p in route]
        })

    safe_osrm_alts.sort(key=lambda x: x["avg_risk"])
    recommended_route = safe_osrm_alts[0] if safe_osrm_alts else {"avg_risk": None, "route": shortest_osrm_route}

    # 7. Crime hotspots (simple clustering by rounded coords)
    hotspots = []
    try:
        if crime_df is not None and not crime_df.empty:
            grouped = (
                crime_df.groupby([
                    crime_df["latitude"].round(4),
                    crime_df["longitude"].round(4)
                ])
                .agg(count=("latitude", "count"), avg_sev=("severity", "mean"))
                .reset_index()
            )

            for _, row in grouped.iterrows():
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                weight = float(row["count"]) * (1 + float(row["avg_sev"]) / 10)
                hotspots.append([lat, lon, weight])
    except Exception:
        logger.exception("Error computing hotspots")

    # 8. Response JSON
    return Response({
        "shortest_osrm_route": shortest_osrm_route,
        "safe_osrm_alternatives": safe_osrm_alts,
        "recommended_safe_route": recommended_route,

        "astar_safe_path": astar_main_path,
        "astar_extra_paths": astar_extra,

        "segment_risks_map": segment_risks_map,
        "crime_hotspots": hotspots,
        "all_osrm_routes": all_routes,

        "segments": len(edges),
        "graph_nodes": len(graph.edges)
    })

