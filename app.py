import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Race Engineer Pro | Final Precision", layout="wide")

def clean_df(df):
    df.columns = df.columns.str.lower().str.replace(' ', '').str.replace('_', '')
    
    # Expanded mapping for G61 CSV variations
    mapping = {
        'dist': ['dist', 'lapdist', 'distance', 'lapdistpct'],
        'time': ['time', 'sessiontime', 'laptime', 'elapsed', 'timestamp'],
        'steer': ['steer', 'steeringwheelangle'],
        'speed': ['speed', 'vel', 'velocity'],
        'throttle': ['throttle', 'thr'],
        'brake': ['brake', 'brk'],
        'latg': ['lataccel', 'latg'],
        'longg': ['longaccel', 'lonaccel'],
        'abs': ['absactive', 'abs']
    }
    
    clean_data = pd.DataFrame()
    for internal, options in mapping.items():
        match = [c for c in df.columns if any(opt == c for opt in options) or any(opt in c for opt in options)]
        if match:
            clean_data[internal] = pd.to_numeric(df[match[0]], errors='coerce').fillna(0)
        else:
            clean_data[internal] = 0.0

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
        st.title("🛠️ Engineer Console")
        files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
        files.sort()
        d_file = st.selectbox("Driver Lap", files, index=0)
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files)-1))
        if d_file == b_file: st.stop()

    df_d = clean_df(pd.read_csv(os.path.join(DATA_DIR, d_file)))
    df_b = clean_df(pd.read_csv(os.path.join(DATA_DIR, b_file)))
    
    grid = np.linspace(0, df_b['dist'].max(), 5000)
    res_d, res_b = pd.DataFrame({'dist': grid}), pd.DataFrame({'dist': grid})
    
    for col in ['time', 'speed', 'throttle', 'brake', 'steer', 'latg', 'longg', 'abs']:
        res_d[col] = np.interp(grid, df_d['dist'], df_d[col])
        res_b[col] = np.interp(grid, df_b['dist'], df_b[col])
    
    # --- PRECISION DELTA LOGIC ---
    if res_d['time'].max() > 0:
        delta = pd.Series(res_d['time'] - res_b['time'])
        st.sidebar.success("⏱️ Time-Sync: ACTIVE (Transponder Precision)")
    else:
        v_d, v_b = np.maximum(res_d['speed'].values / 3.6, 1.0), np.maximum(res_b['speed'].values / 3.6, 1.0)
        delta = pd.Series(np.cumsum(np.diff(grid, prepend=0) / v_d - np.diff(grid, prepend=0) / v_b))
        st.sidebar.warning("⚠️ Time-Sync: FAILED (Physics Integration Active)")

    st.title("🏁 Precision Engineering Audit")
    st.metric("Total Lap Delta", f"{delta.iloc[-1]:.3f}s", delta_color="inverse")
    
    # Audit Logic
    is_corner = np.abs(res_d['steer']).rolling(window=40, center=True).mean() > 15
    events = (is_corner.astype(int).diff().fillna(0) != 0).cumsum()
    
    for eid in events.unique():
        idx = (events == eid) & is_corner
        if idx.any() and (grid[idx][-1] - grid[idx][0]) > 50:
            d_ev, b_ev = res_d[idx], res_b[idx]
            with st.expander(f"📍 Corner at {grid[idx].mean():.0f}m", expanded=True):
                util = min((np.sqrt(d_ev['latg']**2 + d_ev['longg']**2).max() / 
                        np.sqrt(b_ev['latg']**2 + b_ev['longg']**2).max()) * 100, 100.0)
                vmin_diff = d_ev['speed'].min() - b_ev['speed'].min()
                
                st.write(f"**Tire Utilization:** {util:.1f}% | **V-Min Diff:** {vmin_diff:.1f} km/h")
                
                if (d_ev['abs'] > 0.5).any():
                    st.error("FAULT: ABS SATURATION. Over-braking causing rotation loss.")
                elif util < 90:
                    st.warning("FAULT: UNDER-DRIVING. Confidence/Commitment gap.")
                else:
                    st.success("CLEAN EXECUTION.")

if __name__ == "__main__":
    main()
