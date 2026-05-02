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

    # CRITICAL: If we are using LapDistPct, we should treat it as our distance baseline
    # Ensure it's floats
    if "distance" in df.columns:
        df["distance"] = df["distance"].astype(float)

    # Safety fallbacks for missing columns
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
