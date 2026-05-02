import io
import pandas as pd
import streamlit as st

SCHEMA = {
    "distance": ["distance", "lapdist", "track_position", "dist", "pos"],
    "speed": ["speed", "velocity", "v", "speed (km/h)", "speed (mph)"],
    "throttle": ["throttle", "gas", "accel", "throttle_pedal"],
    "brake": ["brake", "brake_pedal", "pedal_b"],
    "lataccel": ["lataccel", "g_lat", "ay", "lateral"],
    "longaccel": ["longaccel", "g_lon", "ax", "longitudinal"],
    "lat": ["lat", "latitude", "gps_lat", "y"],
    "lon": ["lon", "longitude", "gps_lon", "x"]
}

def normalize_telemetry(df):
    # Standardize column names for easier matching
    df.columns = [str(c).lower().strip().replace("_", "") for c in df.columns]
    rename_map = {}

    for target, aliases in SCHEMA.items():
        for alias in aliases:
            clean_alias = alias.lower().replace("_", "")
            if clean_alias in df.columns:
                rename_map[clean_alias] = target
                break
    
    df = df.rename(columns=rename_map)

    # CRITICAL: Fix for the KeyError. 
    # If columns are missing, we create them with 0s so charts.py doesn't crash.
    required_columns = ["distance", "speed", "throttle", "brake", "lataccel", "longaccel", "lat", "lon"]
    for col in required_columns:
        if col not in df.columns:
            df[col] = 0.0 

    # Scaling for 0.0-1.0 formats
    if df["throttle"].max() <= 1.05: df["throttle"] *= 100.0
    if df["brake"].max() <= 1.05: df["brake"] *= 100.0
    
    return df

@st.cache_data
def load_and_process_data(file_bytes):
    # comment='#' skips the metadata lines at the top of Garage 61 CSVs
    df = pd.read_csv(io.StringIO(file_bytes.read().decode("utf-8", errors="ignore")), comment='#')
    return normalize_telemetry(df)
