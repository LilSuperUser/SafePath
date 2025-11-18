# model/views.py  (replace safe_route function with this)
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .utils.osrm_client import get_osrm_edges
from .utils.crime_loader import load_crime_data
from .utils.safety_graph import RoadGraph, haversine
from .utils.crime_scoring import summarize_crime_for_segment
from .utils.safety_astar import safe_a_star

@api_view(["GET"])
def safe_route(request):
    """
    GET params: start_lat, start_lon, end_lat, end_lon
    Returns:
      original_route: [[lat, lon], ...]  (OSRM points)
      segment_risks: [0.12, 0.3, ...]    (risk for each original segment)
      safe_path: [[lat, lon], ...]       (nodes in the safe A* path)
      distance_meters: float             (sum of distances for original route in meters)
      nodes, segments: ints
    """
    start_lat = float(request.GET.get("start_lat"))
    start_lon = float(request.GET.get("start_lon"))
    end_lat = float(request.GET.get("end_lat"))
    end_lon = float(request.GET.get("end_lon"))

    # 1. Load crime data
    crime_df = load_crime_data()

    # 2. Get road segments from OSRM
    start_node, goal_node, edges = get_osrm_edges(start_lat, start_lon, end_lat, end_lon)

    # coords list for original route (OSRM returned coords in order)
    original_coords = []
    for a, b in edges:
        # ensure we include the first point at start
        if not original_coords:
            original_coords.append([a[0], a[1]])
        original_coords.append([b[0], b[1]])

    # 3. Build graph
    graph = RoadGraph()
    for a, b in edges:
        graph.add_edge(a, b)

    # 4. Score each segment with local crime, collect risks & distance
    segment_risks = []
    total_distance = 0.0
    for a, b in edges:
        r = summarize_crime_for_segment(a, b, crime_df)
        graph.set_risk(a, b, r)
        segment_risks.append(r)
        total_distance += haversine(a[0], a[1], b[0], b[1])

    # 5. Find safe route (list of nodes)
    safe_path_nodes = safe_a_star(graph, start_node, goal_node)

    # convert nodes (tuples) into [lat, lon] lists so JSON serializable
    safe_path = [[p[0], p[1]] for p in safe_path_nodes]

    # some aggregate stats
    avg_risk = float(sum(segment_risks) / len(segment_risks)) if segment_risks else 0.0

    return Response({
        "original_route": original_coords,
        "segment_risks": segment_risks,
        "safe_path": safe_path,
        "distance_meters": total_distance,
        "avg_risk": avg_risk,
        "nodes": len(graph.edges),
        "segments": len(edges)
    })

