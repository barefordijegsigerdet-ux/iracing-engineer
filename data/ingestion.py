import difflib
import io
import streamlit as st
import pandas as pd

SCHEMA = {
    "distance": ["distance", "lapdist", "lapdistpct", "track_position"],
    "speed": ["speed", "velocity", "v", "speed (km/h)", "speed (mph)"],
    "throttle": ["throttle", "gas", "accel"],
    "brake": ["brake", "brake_pedal"],
    "time": ["time", "sessiontime", "laptime"],
    "lataccel": ["lataccel", "g_lat", "ay"],
    "longaccel": ["longaccel", "g_lon", "ax"],
    "lat": ["lat", "latitude", "gps_lat"],
    "lon": ["lon", "longitude", "gps_lon"],
    "steer": ["steer", "steering"],
    "gear": ["gear", "currentgear"],
}

def normalize_telemetry(df):
    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    available = list(df.columns)
    rename_map = {}
    
    for target, aliases in SCHEMA.items():
        # Find the best match for each required channel
        for alias in aliases:
            if alias in available:
                rename_map[alias] = target
                break

    speed_src = next((k for k, v in rename_map.items() if v == "speed"), "")
    df = df.rename(columns=rename_map)

    # Fill missing optional columns with zeros
    for opt in ["time", "lataccel", "longaccel", "lat", "lon", "steer", "gear"]:
        if opt not in df.columns: df[opt] = 0.0

    # Auto-scale Throttle/Brake
    if df["throttle"].max() <= 1.05: df["throttle"] *= 100.0
    if df["brake"].max() <= 1.05: df["brake"] *= 100.0

    # Unit Detection logic
    max_spd = df["speed"].max()
    if "mph" in speed_src.lower() or (max_spd < 250 and "km" not in speed_src.lower() and max_spd > 100):
        df["speed"] *= 1.60934
        df.attrs["speed_unit"] = "mph"
    elif max_spd < 100 or "m/s" in speed_src.lower():
        df["speed"] *= 3.6
        df.attrs["speed_unit"] = "m/s"
    else:
        df.attrs["speed_unit"] = "km/h"
    return df

@st.cache_data(show_spinner=False)
def load_and_process_data(file_bytes, speed_unit_override="Auto-detect", downsample=True):
    raw = file_bytes.read()
    text = raw.decode("utf-8", errors="ignore")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(("#", ";"))]
    df = pd.read_csv(io.StringIO("\n".join(lines)))
    
    if downsample and len(df) > 5000:
        df = df.iloc[::3].reset_index(drop=True)
    
    df = normalize_telemetry(df)

    if speed_unit_override != "Auto-detect":
        det = df.attrs.get("speed_unit", "km/h")
        if det == "mph": df["speed"] /= 1.60934
        elif det == "m/s": df["speed"] /= 3.6
        
        if "mph" in speed_unit_override: df["speed"] *= 1.60934
        elif "m/s" in speed_unit_override: df["speed"] *= 3.6
            
    return df
