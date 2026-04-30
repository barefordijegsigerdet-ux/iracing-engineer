import streamlit as st
import pandas as pd
import numpy as np
import os

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Diagnostics", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; border: 1px solid #30363d; }
        .critical-card { background-color: #2d1b1e; border-left: 10px solid #ff3344; padding: 20px; margin-bottom: 15px; border-radius: 4px; border: 1px solid #4d1b1e; }
        .warning-card { background-color: #2d261b; border-left: 10px solid #ffcc00; padding: 20px; margin-bottom: 15px; border-radius: 4px; border: 1px solid #4d401b; }
        .success-card { background-color: #1b2d1e; border-left: 10px solid #00ff88; padding: 20px; margin-bottom: 15px; border-radius: 4px; border: 1px solid #1b4d24; }
        .stat-label { font-size: 0.8rem; color: #8b949e; text-transform: uppercase; }
        .stat-value { font-size: 1.2rem; font-weight: bold; color: #ffffff; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. THE DIAGNOSTIC ENGINE ---

def process_telemetry(df):
    df.columns = [c.strip() for c in df.columns]
    dist_cols = [c for c in df.columns if 'dist' in c.lower()]
    if not dist_cols: st.stop()
    df['Dist'] = pd.to_numeric(df[dist_cols[0]], errors='coerce').fillna(0)
    
    # Physics Normalization
    for col in ['LatAccel', 'LongAccel', 'LonAccel']:
        if col in df.columns:
            df[col.replace('Accel', 'G')] = pd.to_numeric(df[col], errors='coerce').fillna(0) / 9.81
    
    if 'ABSActive' in df.columns:
        df['ABSActive'] = df['ABSActive'].map({'true': 1, 'false': 0, 1: 1, 0: 0, True: 1, False: 0}).fillna(0)
    
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6 
        
    return df.sort_values('Dist').reset_index(drop=True)

def analyze_performance(df_d, df_b):
    # Anchor to Benchmark
    max_dist = df_b['Dist'].max()
    grid = np.linspace(0, max_dist, 5000)
    
    def interp_lap(df):
        out = pd.DataFrame({'Dist': grid})
        for col in ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'ABSActive']:
            if col in df.columns: out[col] = np.interp(grid, df['Dist'], df[col])
            else: out[col] = 0.0
        return out
        
    res_d = interp_lap(df_d)
    res_b = interp_lap(df_b)
    
    # Delta Calculation
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    ds = np.diff(grid, prepend=0)
    delta = np.cumsum(ds / v_d - ds / v_b)
    
    return res_d, res_b, grid, delta

# --- 3. AUDIT RENDERING ---

def render_audit(res_d, res_b, grid, delta):
    st.header("🏁 Driver Performance Audit")
    
    # Identify Top 3 Time Thieves
    delta_slope = np.gradient(delta)
    is_corner = np.abs(res_d['SteeringWheelAngle']) > 15
    events = (is_corner != pd.Series(is_corner).shift()).cumsum()
    
    audit_data = []
    for eid in events.unique():
        idx = events == eid
        if is_corner[idx].iloc[0] and len(res_d[idx]) > 40:
            time_lost = delta[idx.values].max() - delta[idx.values].min()
            audit_data.append({
                'id': eid,
                'idx': idx,
                'lost': time_lost,
                'dist': grid[idx].mean()
            })
    
    # Sort by most time lost
    top_thieves = sorted(audit_data, key=lambda x: x['lost'], reverse=True)[:3]
    
    for i, thief in enumerate(top_thieves, 1):
        d_ev = res_d[thief['idx']]
        b_ev = res_b[thief['idx']]
        
        with st.container():
            st.subheader(f"Time Thief #{i}: Corner at {thief['dist']:.0f}m")
            col1, col2, col3 = st.columns(3)
            col1.metric("Time Lost", f"{thief['lost']:.3f}s")
            col2.metric("V-Min Deficit", f"{b_ev['Speed'].min() - d_ev['Speed'].min():.1f} km/h")
            
            # --- DIAGNOSTIC LOGIC ---
            
            # 1. Entry Phase (Braking)
            abs_usage = (d_ev['ABSActive'] > 0.5).mean() * 100
            if abs_usage > 15:
                st.markdown(f"""<div class="critical-card">
                    <strong>PHASE: ENTRY | FAULT: ABS SATURATION ({abs_usage:.1f}%)</strong><br>
                    <strong>ENGINEER NOTE:</strong> You are over-braking while turning. This saturates the front tires and kills rotation.<br>
                    <strong>ACTION:</strong> Reduce peak brake pressure by 5-10% and release the pedal 2 meters earlier.
                </div>""", unsafe_allow_html=True)
            
            # 2. Mid Phase (Overslowing)
            d_vmin_dist = grid[d_ev['Speed'].idxmin()]
            b_vmin_dist = grid[b_ev['Speed'].idxmin()]
            if (d_vmin_dist - b_vmin_dist) < -3.0:
                st.markdown(f"""<div class="warning-card">
                    <strong>PHASE: MID | FAULT: EARLY V-MIN</strong><br>
                    <strong>ENGINEER NOTE:</strong> You are reaching minimum speed {abs(d_vmin_dist - b_vmin_dist):.1f}m before the apex.<br>
                    <strong>ACTION:</strong> This is "parking the car." Carry more rolling speed deeper into the corner.
                </div>""", unsafe_allow_html=True)
            
            # 3. Exit Phase (Modulation)
            t_rate = np.abs(np.gradient(d_ev['Throttle']))
            if np.sum(t_rate > 40) > 10:
                st.markdown(f"""<div class="critical-card">
                    <strong>PHASE: EXIT | FAULT: SAWTOOTH THROTTLE</strong><br>
                    <strong>ENGINEER NOTE:</strong> Erratic throttle stabs detected. You are upsetting the 992.2 aero platform.<br>
                    <strong>ACTION:</strong> Commit to a single linear squeeze. If you have to lift, your entry line was too shallow.
                </div>""", unsafe_allow_html=True)

# --- 4. MAIN ---

def main():
    apply_custom_css()
    DATA_DIR = "."
    
    with st.sidebar:
        st.header("Diagnostic Settings")
        setup_mode = st.radio("Series Type", ["Fixed Setup", "Open Setup"])
        files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
        files.sort()
        d_file = st.selectbox("Your Lap", files, index=0)
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files)-1))

    if d_file and b_file:
        df_d = process_telemetry(pd.read_csv(d_file))
        df_b = process_telemetry(pd.read_csv(b_file))
        res_d, res_b, grid, delta = analyze_performance(df_d, df_b)
        
        render_audit(res_d, res_b, grid, delta)
        
        st.divider()
        st.header("🔧 Mechanical Adjustments")
        if setup_mode == "Fixed Setup":
            st.info("CONSTRAINT: Fixed Setup. Recommendations limited to Brake Bias.")
            abs_total = (res_d['ABSActive'] > 0.5).mean() * 100
            if abs_total > 10:
                st.success(f"ADJUSTMENT: Move Brake Bias BACKWARD (try 53.2% or 52.8%) to reduce front-end ABS saturation.")
        else:
            st.info("CONSTRAINT: Open Setup. Suggesting aero/spring changes.")
            # Add open setup logic here

if __name__ == "__main__":
    main()
