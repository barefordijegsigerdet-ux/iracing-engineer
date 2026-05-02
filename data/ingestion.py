import io
import pandas as pd
import streamlit as st

# Expanded SCHEMA to catch common racing telemetry variations
SCHEMA = {
    "distance": ["distance", "lapdist", "track_position", "dist", "lap distance", "pos"],
    "speed": ["speed", "velocity", "v", "speed (km/h)", "speed (mph)", "ground speed"],
    "throttle": ["throttle", "gas", "accel", "throttle_pedal", "pedal_f"],
    "brake": ["brake", "brake_pedal", "pedal_b", "brake_f"],
    "lataccel": ["lataccel", "g_lat", "ay", "lateral acceleration"],
    "longaccel": ["longaccel", "g_lon", "ax", "longitudinal acceleration"],
    "lat": ["lat", "latitude", "gps_lat"],
    "lon": ["lon", "longitude", "gps_lon"]
}

def normalize_telemetry(df):
    # Standardize column names: lowercase, strip spaces, remove underscores
    df.columns = [str(c).lower().strip().replace("_", "") for c in df.columns]
    rename_map = {}

    for target, aliases in SCHEMA.items():
        # Check for direct alias matches
        for alias in aliases:
            clean_alias = alias.lower().replace("_", "")
            if clean_alias in df.columns:
                rename_map[clean_alias] = target
                break
        
        # If still not found, try "contains" matching (e.g., 'dist' inside 'lapdistpct')
        if target not in rename_map.values():
            for col in df.columns:
                if any(a in col for a in [target] + SCHEMA[target]):
                    rename_map[col] = target
                    break

    df = df.rename(columns=rename_map)

    # Ensure critical columns exist to prevent KeyError
    required = ["distance", "speed", "throttle", "brake", "lataccel", "longaccel"]
    for col in required:
        if col not in df.columns:
            # Fallback: create a column of zeros so the app doesn't crash
            df[col] = 0.0
            st.sidebar.warning(f"⚠️ Could not find '{col}' column. Using zeros.")

    # Scaling
    if df["throttle"].max() <= 1.05: df["throttle"] *= 100.0
    if df["brake"].max() <= 1.05: df["brake"] *= 100.0
    
    return df

@st.cache_data
def load_and_process_data(file_bytes):
    # Read the CSV, skipping the Garage 61 metadata headers
    df = pd.read_csv(io.StringIO(file_bytes.read().decode("utf-8", errors="ignore")), comment='#')
    return normalize_telemetry(df)
