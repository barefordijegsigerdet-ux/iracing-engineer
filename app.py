import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Race Engineer Pro | Sector Audit", layout="wide")

def clean_df(df):
    df.columns = df.columns.str.lower().str.replace(' ', '').str.replace('_', '')
    mapping = {
        'dist': ['dist', 'lapdist', 'distance', 'lapdistpct'],
        'steer': ['steer', 'steeringwheelangle', 'st'],
        'speed': ['speed', 'vel', 'velocity', 'v'],
        'throttle': ['throttle', 'thr', 'throt'],
        'brake': ['brake', 'brk'],
        'latg': ['lataccel', 'latg'],
        'longg': ['longaccel', 'lonaccel'],
        'abs': ['absactive', 'abs']
    }
    clean_data = pd.DataFrame()
    for internal, options in mapping.items():
        match = [c for c in df.columns if any(opt == c for opt in options) or any(opt in c for opt in options)]
        if match: clean_data[internal] = pd.to_numeric(df[match[0]], errors='coerce').fillna(0)
        else: clean_data[internal] = 0.0
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
        st.title("🛠️ Sector Analysis Config")
        files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
        files.sort()
        d_file = st.selectbox("Driver Lap", files, index=0)
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files)-1))
        if d_file == b_file: st.stop()

    df_d = clean_df(pd.read_csv(os.path.join(DATA_DIR, f_d_name if 'f_d_name' in locals() else d_file)))
    df_b = clean_df(pd.read_csv(os.path.join(DATA_DIR, b_file)))
    
    grid = np.linspace(0, df_b['dist'].max(), 5000)
    res_d, res_b = pd.DataFrame({'dist': grid}), pd.DataFrame({'dist': grid})
    for col in ['speed', 'throttle', 'brake', 'steer', 'latg', 'longg', 'abs']:
        res_d[col] = np.interp(grid, df_d['dist'], df_d[col])
        res_b[col] = np.interp(grid, df_b['dist'], df_b[col])
    
    # Delta Calculation
    v_d, v_b = np.maximum(res_d['speed'].values / 3.6, 1.0), np.maximum(res_b['speed'].values / 3.6, 1.0)
    ds = np.diff(grid, prepend=0)
    delta = pd.Series(np.cumsum(ds / v_d - ds / v_b))

    st.title("🏁 Sector-By-Sector Audit")
    
    # Define Zandvoort Sectors
    sectors = [
        {"name": "Sector 1 (Start - T3)", "start": 0, "end": 1050},
        {"name": "Sector 2 (T4 - T10)", "start": 1050, "end": 2750},
        {"name": "Sector 3 (Chicane - Finish)", "start": 2750, "end": grid[-1]}
    ]

    for sec in sectors:
        mask = (grid >= sec['start']) & (grid <= sec['end'])
        sec_delta = delta[mask].iloc[-1] - delta[mask].iloc[0]
        
        with st.expander(f"📌 {sec['name']} | Delta: {sec_delta:+.3f}s", expanded=True):
            # Find the "Time Thief" (point of maximum delta increase within the sector)
            sec_slopes = np.gradient(delta[mask])
            thief_idx = np.argmax(sec_slopes)
            thief_dist = grid[mask][thief_idx]
            
            d_pt = res_d.iloc[thief_idx]
            b_pt = res_b.iloc[thief_idx]
            
            st.write(f"**Biggest Loss Point:** {thief_dist:.0f}m")
            c1, c2, c3 = st.columns(3)
            c1.metric("V-Diff", f"{d_pt['speed'] - b_pt['speed']:.1f} km/h")
            c2.metric("Driver Throttle", f"{d_pt['throttle']:.0f}%")
            c3.metric("Brake/ABS", f"{d_pt['brake']:.0f}% {'(ABS)' if d_pt['abs'] > 0.5 else ''}")
            
            # Diagnostic
            if d_pt['abs'] > 0.5:
                st.error("FAULT: ABS Saturation at high-load point. Over-braking is the primary cause.")
            elif d_pt['throttle'] < b_pt['throttle'] - 20:
                st.warning("FAULT: Hesitation. You are lifting where the benchmark is committed.")

if __name__ == "__main__":
    main()
