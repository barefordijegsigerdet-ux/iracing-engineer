import streamlit as st
import pandas as pd
import numpy as np
import os

# --- 1. CAR PROFILES (The Universal Brain) ---
CAR_PROFILES = {
    "Porsche 992.2 Cup": {
        "abs_threshold": 0.5, "tc_available": True, "weight_dist": "Rear",
        "primary_focus": "Platform Pitch & Trail Braking",
        "logic_bias": "Entry-Priority" # Errors in entry likely cause errors in exit
    },
    "GT3 Class (General)": {
        "abs_threshold": 0.8, "tc_available": True, "weight_dist": "Front/Mid",
        "primary_focus": "Electronics Efficiency & Aero",
        "logic_bias": "Exit-Priority" # Focus on TC intervention & exit drive
    },
    "Formula 1600 / Vee": {
        "abs_threshold": 0.1, "tc_available": False, "weight_dist": "Mid",
        "primary_focus": "Momentum & Steering Scrub",
        "logic_bias": "V-Min-Priority" # Minimum speed is everything
    }
}

# --- 2. THE DIAGNOSTIC LOGIC ---

def process_telemetry(df):
    df.columns = [c.strip() for c in df.columns]
    dist_cols = [c for c in df.columns if 'dist' in c.lower()]
    if not dist_cols: st.stop()
    df['Dist'] = pd.to_numeric(df[dist_cols[0]], errors='coerce').fillna(0)
    
    # Normalize Acceleration to Gs
    for col in ['LatAccel', 'LongAccel', 'LonAccel']:
        if col in df.columns:
            df[col.replace('Accel', 'G')] = pd.to_numeric(df[col], errors='coerce').fillna(0) / 9.81
    
    # ABS & Speed
    if 'ABSActive' in df.columns:
        df['ABSActive'] = df['ABSActive'].map({'true': 1, 'false': 0, 1: 1, 0: 0, True: 1, False: 0}).fillna(0)
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6 
    return df.sort_values('Dist').reset_index(drop=True)

# --- 3. THE "UNIVERSAL ENGINEER" UI ---

def main():
    st.set_page_config(page_title="Universal Race Engineer", layout="wide")
    st.markdown("<style>.main { background-color: #0e1117; color: white; }</style>", unsafe_allow_html=True)
    
    DATA_DIR = "."
    with st.sidebar:
        st.title("🛠️ Engineer Config")
        car_type = st.selectbox("Select Car Profile", list(CAR_PROFILES.keys()))
        profile = CAR_PROFILES[car_type]
        
        st.divider()
        files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
        files.sort()
        d_file = st.selectbox("Your Lap", files, index=0)
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files)-1))

    if d_file and b_file:
        df_d = process_telemetry(pd.read_csv(d_file))
        df_b = process_telemetry(pd.read_csv(b_file))
        
        # --- ALIGNMENT & MATH ---
        grid = np.linspace(0, df_b['Dist'].max(), 5000)
        def interp(df):
            out = pd.DataFrame({'Dist': grid})
            for col in ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'ABSActive']:
                if col in df.columns: out[col] = np.interp(grid, df['Dist'], df[col])
            return out
        res_d, res_b = interp(df_d), interp(df_b)
        
        # --- THE AUDIT ---
        st.title(f"📊 {car_type} Audit")
        st.caption(f"Engineering Focus: {profile['primary_focus']}")
        
        # Segment corners
        is_corner = np.abs(res_d['SteeringWheelAngle']) > 15
        events = (is_corner != pd.Series(is_corner).shift()).cumsum()
        
        for eid in events.unique():
            idx = events == eid
            if is_corner[idx].iloc[0] and len(res_d[idx]) > 50:
                d_ev, b_ev = res_d[idx], res_b[idx]
                dist_m = grid[idx].mean()
                
                # --- ROOT CAUSE LOGIC ---
                entry_fault = (d_ev['ABSActive'] > profile['abs_threshold']).any()
                exit_fault = np.abs(np.gradient(d_ev['Throttle'])).max() > 40
                
                with st.expander(f"📍 Corner at {dist_m:.0f}m", expanded=True):
                    # Engineering Logic: Phase Correlation
                    if entry_fault and exit_fault:
                        st.error("**ROOT CAUSE: POOR ENTRY.**")
                        st.write("You are over-braking on entry, which is making the car unstable on exit. **Fix the entry first**; the exit will settle itself.")
                    elif entry_fault:
                        st.warning("**FAULT: ENTRY SATURATION.**")
                        st.write(f"You are leaning on the {car_type} assists too hard. Reduce peak pressure.")
                    elif exit_fault:
                        st.warning("**FAULT: EXIT MODULATION.**")
                        st.write("Entry was clean, but you were impatient on throttle. Linearize your squeeze.")
                    
                    # G-SUM Audit (The Commitment Score)
                    driver_g = np.sqrt(d_ev['LatG']**2 + d_ev['LonG']**2).max()
                    bench_g = np.sqrt(b_ev['LatG']**2 + b_ev['LonG']**2).max()
                    utilization = (driver_g / bench_g) * 100
                    st.progress(min(utilization/100, 1.0))
                    st.caption(f"Tire Utilization: {utilization:.1f}% (Commitment to the Limit)")

if __name__ == "__main__":
    main()
