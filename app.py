import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Race Engineer Pro | Precision Audit", layout="wide")

def clean_df(df):
    df.columns = df.columns.str.lower().str.replace(' ', '').str.replace('_', '')
    
    mapping = {
        'dist': ['dist', 'lapdist', 'distance'],
        'time': ['time', 'elapsed', 'timestamp'], # Added for precision
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

    # Normalization
    if clean_data['dist'].max() <= 1.1: clean_data['dist'] *= 4259
    if clean_data['steer'].abs().max() < 6.28: clean_data['steer'] *= (180 / np.pi)
    for g in ['latg', 'longg']:
        if clean_data[g].abs().max() > 5.0: clean_data[g] /= 9.81
    if clean_data['speed'].max() < 100: clean_data['speed'] *= 3.6
    
    return clean_data.sort_values('dist').reset_index(drop=True)

def main():
    st.markdown("<style>.main { background-color: #0e1117; color: white; }</style>", unsafe_allow_html=True)
    DATA_DIR = "."
    
    with st.sidebar:
        st.title("🛠️ Precision Config")
        files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
        files.sort()
        d_file = st.selectbox("Driver Lap", files, index=0)
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files)-1))
        if d_file == b_file: st.stop()

    df_d = clean_df(pd.read_csv(os.path.join(DATA_DIR, d_file)))
    df_b = clean_df(pd.read_csv(os.path.join(DATA_DIR, b_file)))
    
    # Grid Alignment
    max_dist = df_b['dist'].max()
    grid = np.linspace(0, max_dist, 5000)
    
    res_d = pd.DataFrame({'dist': grid})
    res_b = pd.DataFrame({'dist': grid})
    
    for col in ['time', 'speed', 'throttle', 'brake', 'steer', 'latg', 'longg', 'abs']:
        res_d[col] = np.interp(grid, df_d['dist'], df_d[col])
        res_b[col] = np.interp(grid, df_b['dist'], df_b[col])
    
    # PRECISION DELTA CALCULATION
    # If time column exists, use it. Otherwise fallback to velocity integration.
    if res_d['time'].max() > 0 and res_b['time'].max() > 0:
        delta = res_d['time'] - res_b['time']
    else:
        v_d, v_b = np.maximum(res_d['speed'].values / 3.6, 1.0), np.maximum(res_b['speed'].values / 3.6, 1.0)
        delta = np.cumsum(np.diff(grid, prepend=0) / v_d - np.diff(grid, prepend=0) / v_b)

    # --- AUDIT OUTPUT ---
    st.title("🏁 Precision Engineering Audit")
    # Show the real lap time difference
    st.metric("Total Delta (Sync'd)", f"{delta.iloc[-1]:.3f}s", delta_color="inverse")
    
    # Corner Detection
    is_corner = np.abs(res_d['steer']).rolling(window=30, center=True).mean() > 12
    events = (is_corner.astype(int).diff().fillna(0) != 0).cumsum()
    
    for eid in events.unique():
        idx = (events == eid) & is_corner
        if idx.any() and (grid[idx][-1] - grid[idx][0]) > 40:
            d_ev, b_ev = res_d[idx], res_b[idx]
            
            with st.expander(f"📍 Corner at {grid[idx].mean():.0f}m", expanded=True):
                # Utilization
                util = (np.sqrt(d_ev['latg']**2 + d_ev['longg']**2).max() / 
                        np.sqrt(b_ev['latg']**2 + b_ev['longg']**2).max()) * 100
                st.write(f"**Tire Utilization:** {min(util, 100.0):.1f}%")
                
                # V-Min
                vmin_diff = d_ev['speed'].min() - b_ev['speed'].min()
                st.write(f"**V-Min Diff:** {vmin_diff:.1f} km/h")
                
                if (d_ev['abs'] > 0.5).any():
                    st.error("FAULT: ABS SATURATION. Over-braking causing rotation loss.")
                elif util < 90:
                    st.warning("FAULT: UNDER-DRIVING. Leaving grip on the table.")
                else:
                    st.success("CLEAN EXECUTION. Optimized inputs.")

if __name__ == "__main__":
    main()
