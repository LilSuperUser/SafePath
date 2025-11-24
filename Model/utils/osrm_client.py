# Model/utils/osrm_client.py
import requests

OSRM_URL = "http://router.project-osrm.org/route/v1/driving"

def get_osrm_edges(start_lat, start_lon, end_lat, end_lon):

    url = (
        f"{OSRM_URL}/{start_lon},{start_lat};{end_lon},{end_lat}"
        "?overview=full&geometries=geojson&alternatives=3&steps=false"
    )

    res = requests.get(url, timeout=15)
    data = res.json()

    routes = data.get("routes", [])
    if not routes:
        raise Exception("OSRM returned no routes.")

    all_route_coords = []
    for route in routes:
        coords = [(float(lat), float(lon)) for lon, lat in route["geometry"]["coordinates"]]
        all_route_coords.append(coords)

    main_coords = all_route_coords[0]
    start_node = main_coords[0]
    goal_node = main_coords[-1]
    edges = []
    for coords in all_route_coords:
        for i in range(len(coords) - 1):
            a = coords[i]
            b = coords[i + 1]
            edges.append((a, b))

    return main_coords, start_node, goal_node, edges, all_route_coords