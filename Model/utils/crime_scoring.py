# Model/utils/crime_scoring.py
from .geometry_utils import haversine
from .local_ai_client import analyze_crime_risk, USE_LOCAL_AI
import json
import logging

logger = logging.getLogger(__name__)

def summarize_crime_for_segment(a, b, crime_df, radius=700):
    lat1, lon1 = float(a[0]), float(a[1])
    lat2, lon2 = float(b[0]), float(b[1])

    mid_lat = (lat1 + lat2) / 2.0
    mid_lon = (lon1 + lon2) / 2.0

    # No crime data
    if crime_df is None or crime_df.empty:
        return 0.1, "No crime data"

    # Find crimes near midpoint
    try:
        nearby = crime_df[
            crime_df.apply(
                lambda row: haversine(mid_lat, mid_lon, float(row["latitude"]), float(row["longitude"])) < radius,
                axis=1
            )
        ]
    except Exception as e:
        logger.exception("Error while filtering nearby crimes: %s", e)
        return 0.3, "Error inspecting crime data - fallback risk"

    if nearby.empty:
        return 0.1, "No nearby crime"

    avg_sev = float(nearby["severity"].mean())
    summary_obj = {
        "segment_midpoint": {"lat": mid_lat, "lon": mid_lon},
        "segment_endpoints": {"a": {"lat": lat1, "lon": lon1}, "b": {"lat": lat2, "lon": lon2}},
        "total_crimes": int(len(nearby)),
        "average_severity": avg_sev,
        "crime_types": nearby["crime_type"].value_counts().to_dict()
    }

    summary_text = json.dumps(summary_obj, ensure_ascii=False)

    # Attempt local AI only if enabled
    if USE_LOCAL_AI:
        try:
            ai_result = analyze_crime_risk(summary_text)
            if ai_result:
                risk = float(ai_result.get("risk", 0.0))
                explanation = ai_result.get("explanation", "")
                risk = max(0.0, min(1.0, risk))
                return risk, explanation
        except Exception as e:
            logger.exception("Local AI failed for segment; falling back to heuristic: %s", e)

    # Fallback heuristic: normalize avg severity and scale by number of incidents
    try:
        heuristic_risk = min(1.0, avg_sev / 10.0)
        count_boost = min(0.5, len(nearby) / 50.0)
        fallback_risk = max(0.0, min(1.0, heuristic_risk + count_boost))
        explanation = f"Heuristic: {len(nearby)} crimes, avg severity {avg_sev:.2f}"
        return fallback_risk, explanation
    except Exception as e:
        logger.exception("Fallback heuristic failed: %s", e)
        return 0.3, "Fallback heuristic failed"

