import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Race Engineer Pro | Universal Audit", layout="wide")

# --- 1. ROBUST DATA INGESTION ---

def clean_df(df):
    # Standardize all headers: lowercase, no spaces, no underscores
    df.columns = df.columns.str.lower().str.replace(' ', '').str.replace('_', '')
    
    # Greedy Column Mapping
    mapping = {
        'dist': ['dist', 'lapdist', 'distance', 'lapdistpct'],
        'steer': ['steer', 'steeringwheelangle', 'steering', 'st'],
        'speed': ['speed', 'vel', 'velocity', 'sp'],
        'throttle': ['throttle', 'thr', 't'],
        'brake': ['brake', 'brk', 'b'],
        'latg': ['lataccel', 'latg', 'lat'],
        'longg': ['longaccel', 'lonaccel', 'longg', 'long'],
        'abs': ['absactive', 'abs']
    }
    
    clean_data = pd.DataFrame()
    for internal_name, options in mapping.items():
        found = False
        for opt in options:
            match = [c for c in df.columns if opt in c]
            if match:
                clean_data[internal_name] = pd.to_numeric(df[match[0]], errors='coerce').fillna(0)
                found = True
                break
        if not found: clean_data[internal_name] = 0.0

    # Unit Normalization
    # 1. Distance: if it's 0-1 (pct), it needs a track length. Defaulting to 4259m (Zandvoort)
    if clean_data['dist'].max() <= 1.1: clean_data['dist'] *= 4259
    
    # 2. Steering: If max is < 5, it's Radians. Convert to Degrees.
    if clean_data['steer'].abs().max() < 6.28:
        clean_data['steer'] = clean_data['steer'] * (180 / np.pi)
    
    # 3. G-Force: If max is > 5, it's m/s^2. Convert to G.
    for g_col in ['latg', 'longg']:
        if clean_data[g_col].abs().max() > 5.0:
            clean_data[g_col] /= 9.81
            
    # 4. Speed: Ensure km/h
    if clean_data['speed'].max() < 100: clean_data['speed'] *= 3.6
    
    return clean_data.sort_values('dist').reset_index(drop=True)

# --- 2. DIAGNOSTIC ENGINE ---

def main():
    st.markdown("<style>.main { background-color: #0e1117; color: white; }</style>", unsafe_allow_html=True)
    DATA_DIR = "."
    
    with st.sidebar:
        st.title("🛠️ Engineer Console")
        files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
        files.sort()
        d_file = st.selectbox("Driver Lap", files, index=0)
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files)-1))
        
        if d_file == b_file:
            st.error("⚠️ SELECT TWO DIFFERENT FILES")
            st.stop()

    df_d_raw = pd.read_csv(os.path.join(DATA_DIR, d_file))
    df_b_raw = pd.read_csv(os.path.join(DATA_DIR, b_file))
    
    df_d = clean_df(df_d_raw)
    df_b = clean_df(df_b_raw)
    
    # Align
    max_dist = df_b['dist'].max()
    grid = np.linspace(0, max_dist, 5000)
    res_d = pd.DataFrame({'dist': grid})
    res_b = pd.DataFrame({'dist': grid})
    for col in ['speed', 'throttle', 'brake', 'steer', 'latg', 'longg', 'abs']:
        res_d[col] = np.interp(grid, df_d['dist'], df_d[col])
        res_b[col] = np.interp(grid, df_b['dist'], df_b[col])
    
    # Delta
    v_d, v_b = np.maximum(res_d['speed'].values / 3.6, 1.0), np.maximum(res_b['speed'].values / 3.6, 1.0)
    delta = np.cumsum(np.diff(grid, prepend=0) / v_d - np.diff(grid, prepend=0) / v_b)

    # --- UI OUTPUT ---
    st.title("🏁 Universal Engineering Audit")
    st.metric("Total Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
    
    # CORNER DETECTION (Highly Sensitive)
    is_corner = np.abs(res_d['steer']) > 10
    # Apply Smoothing to ignore jitter
    is_corner = is_corner.rolling(window=30, center=True).max().fillna(0).astype(bool)
    events = (is_corner != is_corner.shift()).cumsum()
    
    found_any = False
    for eid in events.unique():
        idx = events == eid
        if is_corner[idx].iloc[0] and (grid[idx][-1] - grid[idx][0]) > 30:
            found_any = True
            d_ev, b_ev = res_d[idx], res_b[idx]
            
            with st.expander(f"📍 Corner at {grid[idx].mean():.0f}m", expanded=True):
                # Calculate Utilization
                util = (np.sqrt(d_ev['latg']**2 + d_ev['longg']**2).max() / 
                        np.sqrt(b_ev['latg']**2 + b_ev['longg']**2).max()) * 100
                util = min(util, 100.0)
                
                st.write(f"**Tire Utilization:** {util:.1f}%")
                st.write(f"**V-Min Diff:** {d_ev['speed'].min() - b_ev['speed'].min():.1f} km/h")
                
                # Simple logic
                if (d_ev['abs'] > 0.5).any():
                    st.error("FAULT: ABS SATURATION. You are over-braking the entry.")
                elif util < 90:
                    st.warning("FAULT: UNDER-DRIVING. You are not using the full grip of the tire.")
                else:
                    st.success("CLEAN LINE. Focus on earlier throttle.")

    if not found_any:
        st.warning("No corners detected. Check if your Steering column is correct.")
        st.write("Headers seen by app:", list(df_d_raw.columns))

if __name__ == "__main__":
    main()
