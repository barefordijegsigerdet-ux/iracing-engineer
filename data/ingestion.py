import streamlit as st
import pandas as pd
import difflib

def normalize_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    # Clean current columns
    df.columns =[str(c).lower().strip() for c in df.columns]

    # Target schema and broad aliases
    SCHEMA = {
        'distance':['distance', 'distance (m)', 'lapdist', 'lap_distance', 'dist', 'lapdistpct'],
        'speed':['speed', 'speed (km/h)', 'speed (mph)', 'velocity', 'v'],
        'throttle': ['throttle', 'throttle %', 'throttle_raw', 'gas', 'accel'],
        'brake': ['brake', 'brake %', 'brake_raw', 'dec', 'brake_pedal'],
        'time': ['time', 'sessiontime', 'laptime', 'current_time', 'elapsed_time']
    }

    normalized_columns = {}
    for target, aliases in SCHEMA.items():
        found = False
        
        # Phase A: Exact Alias Match
        for col in df.columns:
            if col in aliases:
                normalized_columns[col] = target
                found = True
                break
        
        # Phase B: Substring Match (Catches headers like 'time (s)' or 'session time')
        if not found:
            for col in df.columns:
                if target in col: 
                    normalized_columns[col] = target
                    found = True
                    break
        
        # Phase C: Fuzzy Match Fallback
        if not found:
            matches = difflib.get_close_matches(target, df.columns, n=1, cutoff=0.6)
            if matches:
                normalized_columns[matches[0]] = target

    # Rename columns to our standard schema
    df = df.rename(columns=normalized_columns)
    
    # Validation: Ensure critical physics pillars exist
    essential = ['distance', 'speed', 'throttle', 'brake']
    missing =[col for col in essential if col not in df.columns]
    
    if missing:
        raise KeyError(f"Telemetry missing critical headers after normalization: {missing}. Found: {list(df.columns)}")
        
    return df

@st.cache_data(show_spinner=False)
def load_and_process_data(file_bytes) -> pd.DataFrame:
    df = pd.read_csv(file_bytes)
    return normalize_telemetry(df)
