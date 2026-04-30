import streamlit as st
import pandas as pd
import numpy as np
import os

# --- 1. SYSTEM CONFIGURATION & UI ---
st.set_page_config(page_title="Universal Race Engineer v3.2", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .critical-card { background-color: #2d1b1e; border-left: 10px solid #ff3344; padding: 20px; margin-bottom: 15px; border-radius: 4px; border: 1px solid #4d1b1e; }
        .warning-card { background-color: #2d261b; border-left: 10px solid #ffcc00; padding: 20px; margin-bottom: 15px; border-radius: 4px; border: 1px solid #4d401b; }
        .success-card { background-color: #1b2d1e; border-left: 10px solid #00ff88; padding: 20px; margin-bottom: 15px; border-radius: 4px; border: 1px solid #1b4d24; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. UNIVERSAL CAR PROFILES ---
CAR_PROFILES = {
    "Porsche 992.2 Cup": {
        "abs_threshold": 0.5, "tc_available": True, "weight_dist": "Rear",
        "focus": "Platform Pitch & Trail Braking",
        "steer_ratio": 14.0, "friction_limit": 1.6
    },
    "GT4 / GT3 Class": {
        "abs_threshold": 0.8, "tc_available": True, "weight_dist": "Front/Mid",
        "focus": "Electronics Efficiency & Aero Platform",
        "steer_ratio": 16.0, "friction_limit": 2.0
    },
    "Formula 1600 / Vee": {
        "abs_threshold": 0.1, "tc_available": False, "weight_dist": "Mid",
        "focus": "Momentum Maintenance & Minimal Scrub",
        "steer_ratio": 12.0, "friction_limit": 1.2
    }
}

# --- 3. PHYSICS & INGESTION ENGINE ---

def process_telemetry(df):
    df.columns = [c.strip() for c in df.columns]
    
    # 1. Distance Detection
    dist_cols = [c for c in df.columns if 'dist' in c.lower()]
    if not dist_cols: st.stop()
    df['Dist'] = pd.to_numeric(df[dist_cols[0]], errors='coerce').fillna(0)
    
    # 2. Acceleration Normalization (Logic Fix 3: G-Scale Check)
    # Check if data is already in Gs or m/s² by checking max value
    for col in ['LatAccel', 'LongAccel', 'LonAccel']:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors='coerce').fillna(0)
            # If max absolute value > 5.0, it's likely m/s² and needs normalization to G
            if vals.abs().max() > 5.0:
                df[col.replace('Accel', 'G')] = vals / 9.81
            else:
                df[col.replace('Accel', 'G')] = vals
    
    # 3. Steering Normalization (Radians to Degrees Fix)
    if 'SteeringWheelAngle' in df.columns:
        df['SteerDeg'] = pd.to_numeric(df['SteeringWheelAngle'], errors='coerce') * (180 / np.pi)
    else:
        df['SteerDeg'] = 0.0

    # 4. ABS & Speed
    if 'ABSActive' in df.columns:
        df['ABSActive'] = df['ABSActive'].map({'true': 1, 'false': 0, 1: 1, 0: 0, True: 1, False: 0}).fillna(0)
    
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6 
        
    return df.sort_values('Dist').reset_index(drop=True)

def analyze_laps(df_d, df_b):
    max_dist = df_b['Dist'].max()
    grid = np.linspace(0, max_dist, 5000)
    
    def interp(df):
        out = pd.DataFrame({'Dist': grid})
        # Note: Ensure G names match normalized names from process_telemetry
        cols = ['Speed', 'Throttle', 'Brake', 'SteerDeg', 'LatG', 'LonG', 'ABSActive']
        for col in cols:
            if col in df.columns: out[col] = np.interp(grid, df['Dist'], df[col])
            else: out[col] = 0.0
        return out
        
    res_d = interp(df_d)
    res_b = interp(df_b)
    
    # Delta Calc
    v_d, v_b = np.maximum(res_d['Speed'].values / 3.6, 1.0), np.maximum(res_b['Speed'].values / 3.6, 1.0)
    delta = np.cumsum(np.diff(grid, prepend=0) / v_d - np.diff(grid, prepend=0) / v_b)
    
    return res_d, res_b, grid, delta

# --- 4. THE ROOT CAUSE AUDIT ---

def render_audit(res_d, res_b, grid, delta, profile):
    st.header("🏁 Universal Engineering Audit")
    st.caption(f"Strategy: {profile['focus']}")
    
    # Logic Fix 2: Rolling Mean (Window 50) to SteerDeg to kill noise
    steer_smoothed = res_d['SteerDeg'].rolling(window=50, center=True, min_periods=1).mean()
    
    is_corner = np.abs(steer_smoothed) > 15
    events = (is_corner != pd.Series(is_corner).shift()).cumsum()
    
    audit_count = 0
    for eid in events.unique():
        idx = events == eid
        
        # Logic Fix 2: Minimum Event Length (50 meters)
        event_dist = grid[idx][-1] - grid[idx][0]
        
        if is_corner[idx].iloc[0] and event_dist >= 50.0:
            audit_count += 1
            d_ev, b_ev = res_d[idx], res_b[idx]
            
            # --- PHASE DIAGNOSTICS ---
            entry_abs = (d_ev['ABSActive'] > profile['abs_threshold']).any()
            exit_saw = np.abs(np.gradient(d_ev['Throttle'])).max() > 45
            
            # Logic Fix 3: Tire Utilization Cap at 100%
            raw_util = (np.sqrt(d_ev['LatG']**2 + d_ev['LonG']**2).max() / profile['friction_limit']) * 100
            util = min(raw_util, 100.0)
            
            # Logic Fix 4: V-Min Displacement Check (Ignore < 0.5 km/h)
            vmin_delta = d_ev['Speed'].min() - b_ev['Speed'].min()
            if abs(vmin_delta) < 0.5:
                vmin_delta = 0.0
            
            with st.expander(f"📍 Event {audit_count} | Apex at {grid[idx].mean():.0f}m", expanded=True):
                c1, c2 = st.columns([2, 1])
                
                with c2:
                    st.metric("Tire Util.", f"{util:.1f}%")
                    st.metric("V-Min Delta", f"{vmin_delta:.1f} km/h")
                
                with c1:
                    # ROOT CAUSE ENGINE
                    if entry_abs and exit_saw:
                        st.markdown('<div class="critical-card"><strong>ROOT CAUSE: ENTRY INSTABILITY.</strong> You over-braked and saturated the assists. This ruined your mid-corner platform, forcing the sawtooth throttle on exit. <strong>Action: Fix entry first.</strong></div>', unsafe_allow_html=True)
                    elif entry_abs:
                        st.markdown('<div class="warning-card"><strong>ENTRY FAULT: ABS OVER-RELIANCE.</strong> Assist is fighting for longitudinal grip while you need lateral rotation. <strong>Action: Squeeze less peak pressure.</strong></div>', unsafe_allow_html=True)
                    elif exit_saw:
                        st.markdown('<div class="critical-card"><strong>EXIT FAULT: SAWTOOTH THROTTLE.</strong> Entry was clean but platform was unstable. <strong>Action: Hold a steady maintenance throttle.</strong></div>', unsafe_allow_html=True)
                    elif abs(vmin_delta) < 0.5:
                        st.markdown('<div class="success-card"><strong>CLEAN EXECUTION.</strong> Inputs are efficient and speeds are identical to benchmark. Line optimization is the only path for more time.</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="success-card"><strong>EFFICIENT INPUTS.</strong> Inputs are clean. Focus on earlier apex or higher entry speed to close the V-Min delta.</div>', unsafe_allow_html=True)

# --- 5. MAIN ---

def main():
    apply_custom_css()
    DATA_DIR = "."
    
    with st.sidebar:
        st.title("🛠️ Config")
        car_type = st.selectbox("Vehicle Profile", list(CAR_PROFILES.keys()))
        profile = CAR_PROFILES[car_type]
        st.divider()
        files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
        files.sort()
        
        d_file = st.selectbox("Driver Lap", files, index=0)
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files)-1))

        # Logic Fix 1: Force File Uniqueness
        if d_file == b_file:
            st.warning("⚠️ SELECT DIFFERENT LAPS FOR COMPARISON.")
            st.stop()

    if d_file and b_file:
        df_d = process_telemetry(pd.read_csv(os.path.join(DATA_DIR, d_file)))
        df_b = process_telemetry(pd.read_csv(os.path.join(DATA_DIR, b_file)))
        res_d, res_b, grid, delta = analyze_laps(df_d, df_b)
        
        # Display Global Metric
        st.metric("Total Lap Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
        
        render_audit(res_d, res_b, grid, delta, profile)
    else:
        st.info("Ensure CSV files are available in the directory to begin.")

if __name__ == "__main__":
    main()
