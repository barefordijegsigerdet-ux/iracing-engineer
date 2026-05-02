import io
import pandas as pd
import streamlit as st

SCHEMA = {
    "distance": ["lapdistpct", "distance", "lapdist", "pos"],
    "speed": ["speed", "velocity", "v"],
    "throttle": ["throttle", "gas"],
    "brake": ["brake"],
    "lataccel": ["lataccel", "g_lat"],
    "longaccel": ["longaccel", "g_lon"],
    "lat": ["lat"],
    "lon": ["lon"]
}

def normalize_telemetry(df):
    # Standardize column names
    df.columns = [str(c).lower().strip().replace("_", "") for c in df.columns]
    rename_map = {}

    for target, aliases in SCHEMA.items():
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = target
                break
    
    df = df.rename(columns=rename_map)

    # SCALING LOGIC: Convert 0.0-1.0 to 0-100%
    # We check if the max is <= 1.1 to avoid double-scaling if data is already 0-100
    if df["throttle"].max() <= 1.1:
        df["throttle"] = df["throttle"] * 100.0
        
    if df["brake"].max() <= 1.1:
        df["brake"] = df["brake"] * 100.0

    # Ensure distance and other required columns exist
    required = ["distance", "speed", "throttle", "brake", "lataccel", "longaccel", "lat", "lon"]
    for col in required:
        if col not in df.columns:
            df[col] = 0.0 
    
    return df

@st.cache_data
def load_and_process_data(file_bytes):
    # comment='#' is vital for Garage 61 files to skip the metadata header
    df = pd.read_csv(io.StringIO(file_bytes.read().decode("utf-8", errors="ignore")), comment='#')
    return normalize_telemetry(df)
