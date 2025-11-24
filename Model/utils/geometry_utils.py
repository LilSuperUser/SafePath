# Model/utils/geometry_utils.py
import math

def haversine(lat1, lon1, lat2, lon2):
    """
    Returns distance in meters between two lat/lon points.
    """
    R = 6371  # km

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)

    c = 2 * math.asin(math.sqrt(a))
    return R * c * 1000.0  # meters

