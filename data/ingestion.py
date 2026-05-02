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
    # Standardiser kolonnenavne
    df.columns = [str(c).lower().strip().replace("_", "") for c in df.columns]
    rename_map = {}

    for target, aliases in SCHEMA.items():
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = target
                break
    
    df = df.rename(columns=rename_map)

    # --- TVUNGET KONVERTERING (Ingen tjek, bare gør det) ---
    
    # 1. SPEED: Vi ved Garage 61 bruger m/s. Gør det altid til km/t.
    df["speed"] = df["speed"] * 3.6

    # 2. ACCEL: Gør det altid til G-kræfter (divider med tyngdekraften)
    # Hvis dine data allerede er i G, vil dette gøre dem meget små, 
    # men i dit tilfælde ser det ud til de mangler divisionen.
    if df["lataccel"].abs().max() > 5:
        df["lataccel"] = df["lataccel"] / 9.80665
        df["longaccel"] = df["longaccel"] / 9.80665

    # 3. PEDALER: Tving dem til 0-100 skalaen
    # Vi bruger .clip for at sikre, at vi ikke får mærkelige værdier over 100
    df["throttle"] = (df["throttle"] * 100).clip(0, 100)
    df["brake"] = (df["brake"] * 100).clip(0, 100)

    # 4. SORTERING: Vigtigt for at undgå de vandrette streger
    df = df.sort_values("distance").reset_index(drop=True)

    # Fyld manglende kolonner
    required = ["distance", "speed", "throttle", "brake", "lataccel", "longaccel", "lat", "lon"]
    for col in required:
        if col not in df.columns:
            df[col] = 0.0 
            
    return df

def load_and_process_data(user_file, ref_file):
    user_raw = pd.read_csv(user_file, comment='#')
    ref_raw = pd.read_csv(ref_file, comment='#')
    
    return normalize_telemetry(user_raw), normalize_telemetry(ref_raw)
