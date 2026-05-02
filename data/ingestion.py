import pandas as pd
import numpy as np

# Mapping Garage 61 / iRacing names to our internal app names
SCHEMA = {
    "distance": ["lapdistpct", "lapdist", "distance"],
    "speed": ["speed", "velocity", "vel"],
    "throttle": ["throttle", "thr"],
    "brake": ["brake", "brk"],
    "lataccel": ["lataccel", "g_lat", "lat_g"],
    "longaccel": ["longaccel", "g_long", "long_g"],
    "lat": ["lat", "latitude"],
    "lon": ["lon", "longitude"]
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

    # --- MATH CONVERSIONS ---
    
    # 1. SPEED: Convert m/s to km/h
    if df["speed"].max() < 100:
        df["speed"] = df["speed"] * 3.6

    # 2. ACCEL: Convert m/s² to Gs
    if df["lataccel"].abs().max() > 5:
        df["lataccel"] = df["lataccel"] / 9.80665
        df["longaccel"] = df["longaccel"] / 9.80665

    # 3. PEDALS: Convert 0.0-1.0 to 0-100%
    if df["throttle"].max() <= 1.1:
        df["throttle"] = (df["throttle"] * 100).round(1)
    if df["brake"].max() <= 1.1:
        df["brake"] = (df["brake"] * 100).round(1)

    # 4. SORTING: Prevent "ghost lines" by ordering by distance
    df = df.sort_values("distance").reset_index(drop=True)

    # Fill missing columns with zeros
    required = ["distance", "speed", "throttle", "brake", "lataccel", "longaccel", "lat", "lon"]
    for col in required:
        if col not in df.columns:
            df[col] = 0.0 
            
    return df

def load_and_process_data(user_file, ref_file):
    user_raw = pd.read_csv(user_file, comment='#')
    ref_raw = pd.read_csv(ref_file, comment='#')
    
    return normalize_telemetry(user_raw), normalize_telemetry(ref_raw)
