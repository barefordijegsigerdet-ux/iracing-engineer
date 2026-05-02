import pandas as pd
import difflib
import streamlit as st

def normalize_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    # 1. Clean current columns
    df.columns =[str(c).lower().strip() for c in df.columns]

    # 2. Define schema including our new G-Sum requirements
    SCHEMA = {
        'distance':['distance', 'distance (m)', 'lapdist', 'lap_distance', 'dist', 'lapdistpct'],
        'speed':['speed', 'speed (km/h)', 'speed (mph)', 'velocity', 'v'],
        'throttle':['throttle', 'throttle %', 'throttle_raw', 'gas', 'accel'],
        'brake':['brake', 'brake %', 'brake_raw', 'dec', 'brake_pedal'],
        'time':['time', 'sessiontime', 'laptime', 'current_time', 'elapsed_time'],
        'lataccel': ['lataccel', 'lateral_acceleration', 'lat_accel', 'g_lat'],
        'longaccel':['longaccel', 'longitudinal_acceleration', 'lon_accel', 'g_lon']
    }

    normalized_columns = {}
    for target, aliases in SCHEMA.items():
        found = False
        # Exact match
        for col in df.columns:
            if col in aliases:
                normalized_columns[col] = target
                found = True
                break
        # Substring match
        if not found:
            for col in df.columns:
                if target in col: 
                    normalized_columns[col] = target
                    found = True
                    break
        # Fuzzy match
        if not found:
            matches = difflib.get_close_matches(target, df.columns, n=1, cutoff=0.6)
            if matches:
                normalized_columns[matches[0]] = target

    df = df.rename(columns=normalized_columns)
    
    # 3. Missing Column Protection (Dummy Data Generation)
    essential =['distance', 'speed', 'throttle', 'brake']
    for col in essential:
        if col not in df.columns:
            raise KeyError(f"Fatal Error: CSV missing critical header '{col}'.")
            
    # Dummy Columns for missing optional data (prevents KeyErrors)
    optional = ['time', 'lataccel', 'longaccel']
    for opt in optional:
        if opt not in df.columns:
            df[opt] = 0.0  # Safe fallback

    # 4. Enforce 0-100 scales for Garage 61 UI mapping
    if df['throttle'].max() <= 1.05: df['throttle'] = df['throttle'] * 100
    if df['brake'].max() <= 1.05: df['brake'] = df['brake'] * 100

    return df

@st.cache_data(show_spinner=False)
def load_and_process_data(file_bytes) -> pd.DataFrame:
    """Safe Loader with Auto-Downsampling for performance."""
    try:
        df = pd.read_csv(file_bytes)
        
        # BIG DATA FIX: Downsample if over 5000 rows (keeps Plotly fast)
        if len(df) > 5000:
            df = df.iloc[::3].reset_index(drop=True)
            
        return normalize_telemetry(df)
    except pd.errors.EmptyDataError:
        raise ValueError("The uploaded CSV is empty or corrupted.")
    except Exception as e:
        raise ValueError(f"Failed to read CSV: {e}")
