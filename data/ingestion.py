import io
import pandas as pd
import streamlit as st

SCHEMA = {
    "distance": ["distance", "lapdist", "track_position"],
    "speed": ["speed", "velocity", "v", "speed (km/h)"],
    "throttle": ["throttle", "gas", "accel"],
    "brake": ["brake", "brake_pedal"],
    "lataccel": ["lataccel", "g_lat", "ay"],
    "longaccel": ["longaccel", "g_lon", "ax"],
    "lat": ["lat", "latitude"],
    "lon": ["lon", "longitude"]
}

def normalize_telemetry(df):
    df.columns = [str(c).lower().strip() for c in df.columns]
    rename_map = {}
    for target, aliases in SCHEMA.items():
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = target
                break
    df = df.rename(columns=rename_map)
    # Basic scaling for 0-1 range inputs
    if df["throttle"].max() <= 1.05: df["throttle"] *= 100.0
    if df["brake"].max() <= 1.05: df["brake"] *= 100.0
    return df

@st.cache_data
def load_and_process_data(file_bytes):
    df = pd.read_csv(io.StringIO(file_bytes.read().decode("utf-8", errors="ignore")), comment='#')
    return normalize_telemetry(df)
