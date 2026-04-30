import streamlit as st
import pandas as pd
import numpy as np
import os

# --- 1. CORE CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Master v4.0", layout="wide")

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

# --- 2. THE UNIVERSAL INGESTION ENGINE ---

def clean_df(df):
    # Standardize all headers to lower case and remove noise
    df.columns = df.columns.str.lower().str.replace(' ', '').str.replace('_', '')
    
    mapping = {
        'dist': ['dist', 'lapdist', 'distance', 'lapdistpct'],
        'time': ['time', 'sessiontime', 'laptime', 'elapsed', 'timestamp', 'sample', 't'],
        'steer': ['steer', 'steeringwheelangle', 'st'],
        'speed': ['speed', 'vel', 'velocity', 'v'],
        'throttle': ['throttle', 'thr', 'throt'],
        'brake': ['brake', 'brk'],
        'latg': ['lataccel', 'latg', 'lat'],
        'longg': ['longaccel', 'lonaccel', 'longg', 'lon'],
        'abs': ['absactive', 'abs', 'abs_active']
    }
    
    clean_data = pd.DataFrame()
    for internal, options in mapping.items():
        # Greedy search for columns
        match = [c for c in df.columns if any(opt == c for opt in options) or any(opt in c for opt in options)]
        if match:
            clean_data[internal] = pd.to_numeric(df[match[0]], errors='coerce').fillna(0)
        else:
            clean_data[internal] = 0.0

    # Handle Time Calculation from Samples if necessary
    if clean_data['time'].max() == 0:
        # Fallback: Many G61 exports are 60Hz. 
        clean_data['time'] = np.arange(len(clean_data)) * (1.0 / 60.0)

    # Unit Normalization
    if clean_data['dist'].max() <= 1.1: clean_data['dist'] *= 4259 
    if clean_data['steer'].abs().max() < 6.28: clean_data['steer'] *= (180 / np.pi)
    for g in ['latg', 'longg']:
        if clean_data[g].abs().max() > 5.0: clean_data[g] /= 9.81
    if clean_data['speed'].max() < 100: clean_data['speed'] *= 3.6
    
    return clean_data.sort_values('dist').reset_index(drop=True)

# --- 3. DIAGNOSTIC & AUDIT LOGIC ---

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
            st.error("⚠️ ERROR: SELECT UNIQUE LAPS")
            st.stop()

    # Load Data
    df_d = clean_df(pd.read_csv(os.path.join(DATA_DIR, d_file)))
    df_b = clean_df(pd.read_csv(os.path.join(DATA_DIR, b_file)))
    
    # 5000 Point Spatial Alignment
    grid = np.linspace(0, df_b['dist'].max(), 5000)
    res_d, res_b = pd.DataFrame({'dist': grid}), pd.DataFrame({'dist': grid})
    
    for col in ['time', 'speed', 'throttle', 'brake', 'steer', 'latg', 'longg', 'abs']:
        res_d[col] = np.interp(grid, df_d['dist'], df_d[col])
        res_b[col] = np.interp(grid, df_b['dist'], df_b[col])
    
    # --- PRECISION TIME-SYNC ---
    if res_d['time'].max() > 0 and (res_d['time'].max() != res_b['time'].max()):
        delta_raw = res_d['time'] - res_b['time']
        st.sidebar.success("⏱️ Time-Sync: ACTIVE (Precision)")
    else:
        # Fallback to Physics Integration
        v_d, v_b = np.maximum(res_d['speed'].values / 3.6, 1.0), np.maximum(res_b['speed'].values / 3.6, 1.0)
        ds = np.diff(grid, prepend=0)
        delta_raw = np.cumsum(ds / v_d - ds / v_b)
        st.sidebar.warning("⚠️ Time-Sync: FALLBACK (Physics)")

    delta = pd.Series(delta_raw)
    st.title("🏁 Precision Performance Audit")
    
    if not delta.empty:
        st.metric("Total Lap Delta", f"{delta.iloc[-1]:.3f}s", delta_color="inverse")

    # --- AUDIT MODULE ---
    # Noise-filtered corner detection
    is_corner = np.abs(res_d['steer']).rolling(window=40, center=True).mean() > 15
    events = (is_corner.astype(int).diff().fillna(0) != 0).cumsum()
    
    found_any = False
    for eid in events.unique():
        idx = (events == eid) & is_corner
        if idx.any() and (grid[idx.values][-1] - grid[idx.values][0]) > 50:
            found_any = True
            d_ev, b_ev = res_d[idx], res_b[idx]
            
            with st.expander(f"📍 Corner at {grid[idx.values].mean():.0f}m", expanded=True):
                # Utilization
                util = min((np.sqrt(d_ev['latg']**2 + d_ev['longg']**2).max() / 
                        np.sqrt(b_ev['latg']**2 + b_ev['longg']**2).max()) * 100, 100.0)
                
                # Speed Delta
                vmin_diff = d_ev['speed'].min() - b_ev['speed'].min()
                
                st.write(f"**Tire Utilization:** {util:.1f}% | **V-Min Diff:** {vmin_diff:.1f} km/h")
                
                # Diagnostic Triggers
                if (d_ev['abs'] > 0.5).any():
                    st.error("PHASE: ENTRY | FAULT: ABS SATURATION. Rotation killed via over-braking.")
                elif util < 90:
                    st.warning("PHASE: MID | FAULT: UNDER-DRIVING. Confidence/Commitment gap.")
                else:
                    st.success("PHASE: EXIT | CLEAN EXECUTION. Line geometry is the priority.")

if __name__ == "__main__":
    main()
