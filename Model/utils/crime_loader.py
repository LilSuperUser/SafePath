# model/utils/crime_loader.py
import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

def load_crime_data():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    csv_path = os.path.join(BASE_DIR, "data/delhi_crime_data.csv")

    if not os.path.exists(csv_path):
        logger.error("Crime CSV not found at %s", csv_path)
        return pd.DataFrame()

    try:
        df = pd.read_csv(csv_path, engine="python", encoding="utf-8-sig")
    except Exception as e:
        logger.exception("Failed to load crime CSV:", e)
        return pd.DataFrame()

    # Normalize headers
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    # Explicit mapping based on the CSV:
    # crime_type, crime, latitude, longitude, severity, description
    rename_map = {}
    if "crime_type" in df.columns:
        rename_map["crime_type"] = "crime_type"
    if "crime" in df.columns:
        rename_map["crime"] = "crime_subtype"
    if "latitude" in df.columns:
        rename_map["latitude"] = "latitude"
    if "longitude" in df.columns:
        rename_map["longitude"] = "longitude"
    if "severity" in df.columns:
        rename_map["severity"] = "severity"
    if "description" in df.columns:
        rename_map["description"] = "description"

    df = df.rename(columns=rename_map)

    # Required columns
    required = ["latitude", "longitude", "severity", "crime_type"]
    for col in required:
        if col not in df.columns:
            logger.error("Missing required column: %s", col)
            return pd.DataFrame()

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["severity"] = pd.to_numeric(df["severity"], errors="coerce").fillna(1.0)

    df = df.dropna(subset=["latitude", "longitude", "severity"])

    logger.info("Loaded %d crime rows.", len(df))
    return df

