import streamlit as st
import pandas as pd
import numpy as np
import os

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Universal Diagnostics", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; border: 1px solid #30363d; }
        .critical-card { background-color: #2d1b1e; border-left: 10px solid #ff3344; padding: 20px; margin-bottom: 15px; border-radius: 4px; border: 1px solid #4d1b1e; }
        .warning-card { background-color: #2d261b; border-left: 10px solid #ffcc00; padding: 20px; margin-bottom: 15px; border-radius: 4px; border: 1px solid #4d401b; }
        .success-card { background-color: #1b2d1e; border-left: 10px solid #00ff88; padding: 20px; margin-bottom: 15px; border-radius: 4px; border: 1px solid #1b4d24; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. ROBUST INGESTION ENGINE ---

def clean_df(df):
    # Standardize headers: lower case, remove spaces/underscores
    df.columns = df.columns.str.lower().str.replace(' ', '').str.replace('_', '')
    
    mapping = {
        'dist': ['dist', 'lapdist', 'distance'],
        'time': ['time', 'elapsed', 'timestamp'],
        'steer': ['steer', 'steeringwheelangle'],
        'speed': ['speed', 'vel'],
        'throttle': ['throttle', 'thr'],
        'brake': ['brake', 'brk'],
        'latg': ['lataccel', 'latg'],
        'longg': ['longaccel', 'lonaccel'],
        'abs': ['absactive', 'abs']
    }
    
    clean_data = pd.DataFrame()
    for internal_name, options in mapping.items():
        match = [c for c in df.columns if any(opt == c for opt in options) or any(opt in c for opt in options)]
        if match:
            clean_data[internal_name] = pd.to_numeric(df[match[0]], errors='coerce').fillna(0)
        else:
            clean_data[internal_name] = 0.0

    # Normalization (m/s^2 to G, Rads to Degs)
    if clean_data['dist'].max() <= 1.1: clean_data['dist'] *= 4259 
    if clean_data['steer'].abs().max() < 6.28: clean_data['steer'] *= (180 / np.pi)
    for g in ['latg', 'longg']:
        if clean_data[g].abs().max() > 5.0: clean_data[g] /= 9.81
    if clean_data['speed'].max() < 100: clean_data['speed'] *= 3.6
    
    return clean_data.sort_values('dist').reset_index(drop=True)

# --- 3. MAIN DIAGNOSTIC LOOP ---

def main():
    apply_custom_css()
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

    # Load and Clean
    df_d = clean_df(pd.read_csv(os.path.join(DATA_DIR, d_file)))
    df_b = clean_df(pd.read_csv(os.path.join(DATA_DIR, b_file)))
    
    # Alignment Grid
    max_dist = df_b['dist'].max()
    grid = np.linspace(0, max_dist, 5000)
    
    res_d = pd.DataFrame({'dist': grid})
    res_b = pd.DataFrame({'dist': grid})
    
    for col in ['time', 'speed', 'throttle', 'brake', 'steer', 'latg', 'longg', 'abs']:
        res_d[col] = np.interp(grid, df_d['dist'], df_d[col])
        res_b[col] = np.interp(grid, df_b['dist'], df_b[col])
    
    # --- PRECISION DELTA LOGIC ---
    # We force 'delta' to be a Pandas Series to ensure .iloc[-1] availability
    if res_d['time'].max() > 0 and res_b['time'].max() > 0:
        delta_raw = res_d['time'] - res_b['time']
    else:
        v_d, v_b = np.maximum(res_d['speed'].values / 3.6, 1.0), np.maximum(res_b['speed'].values / 3.6, 1.0)
        ds = np.diff(grid, prepend=0)
        delta_raw = np.cumsum(ds / v_d - ds / v_b)
    
    delta = pd.Series(delta_raw)

    # --- UI OUTPUT ---
    st.title("🏁 Precision Engineering Audit")
    
    # Check if delta is valid before displaying metric
    if not delta.empty:
        total_delta = delta.iloc[-1]
        st.metric("Total Lap Delta (Sync'd)", f"{total_delta:.3f}s", delta_color="inverse")
    
    # Corner Segmentation
    is_corner = np.abs(res_d['steer']).rolling(window=40, center=True).mean() > 15
    events = (is_corner.astype(int).diff().fillna(0) != 0).cumsum()
    
    found_any = False
    for eid in events.unique():
        idx = (events == eid) & is_corner
        if idx.any() and (grid[idx][-1] - grid[idx][0]) > 50:
            found_any = True
            d_ev, b_ev = res_d[idx], res_b[idx]
            
            with st.expander(f"📍 Corner at {grid[idx].mean():.0f}m", expanded=True):
                # Tire Utilization (G-Sum)
                util = (np.sqrt(d_ev['latg']**2 + d_ev['longg']**2).max() / 
                        np.sqrt(b_ev['latg']**2 + b_ev['longg']**2).max()) * 100
                st.write(f"**Tire Utilization:** {min(util, 100.0):.1f}%")
                
                # V-Min Speed Difference
                vmin_diff = d_ev['speed'].min() - b_ev['speed'].min()
                st.write(f"**V-Min Speed Diff:** {vmin_diff:.1f} km/h")
                
                # Diagnostic Triggers
                if (d_ev['abs'] > 0.5).any():
                    st.error("FAULT: ABS SATURATION. Over-braking during turn-in phase.")
                elif util < 90:
                    st.warning("FAULT: UNDER-DRIVING. Leaving grip on the table.")
                else:
                    st.success("CLEAN EXECUTION. Maintain momentum.")

    if not found_any:
        st.info("Ingesting telemetry... If no corners appear, verify Steering column in CSV.")

if __name__ == "__main__":
    main()
