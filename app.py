import streamlit as st
import pandas as pd
import numpy as np
import os

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro v3.3.2", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .critical-card { background-color: #2d1b1e; border-left: 10px solid #ff3344; padding: 20px; margin-bottom: 15px; border-radius: 4px; }
        .warning-card { background-color: #2d261b; border-left: 10px solid #ffcc00; padding: 20px; margin-bottom: 15px; border-radius: 4px; }
        .success-card { background-color: #1b2d1e; border-left: 10px solid #00ff88; padding: 20px; margin-bottom: 15px; border-radius: 4px; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. SMART COLUMN DETECTOR ---
def find_col(df, keywords):
    """Fuzzy search for columns even if they have units like 'Speed (km/h)'"""
    for k in keywords:
        for c in df.columns:
            if k.lower() in str(c).lower():
                return c
    return None

# --- 3. TELEMETRY INGESTION ---
def process_telemetry(df):
    # Clean column names (remove spaces/quotes)
    df.columns = [str(c).strip().replace('"', '').replace("'", "") for c in df.columns]
    
    clean = pd.DataFrame()
    
    # 1. Distance (The X-Axis)
    c_dist = find_col(df, ['dist', 'mous', 'pos', 'track'])
    clean['Dist'] = pd.to_numeric(df[c_dist], errors='coerce').fillna(0) if c_dist else np.arange(len(df))
    
    # 2. Speed (Normalize to km/h)
    c_spd = find_col(df, ['speed', 'vel', 'v_', 'gps_speed'])
    if c_spd:
        s = pd.to_numeric(df[c_spd], errors='coerce').fillna(0)
        # If max speed is low (e.g. 50 m/s), convert to km/h
        clean['Speed'] = s * 3.6 if s.max() < 100 else s
    else:
        clean['Speed'] = 0.0

    # 3. Steering (Normalize to Degrees)
    c_str = find_col(df, ['steer', 'wheel', 'angle', 'str'])
    if c_str:
        sv = pd.to_numeric(df[c_str], errors='coerce').fillna(0)
        # If values are tiny (radians), convert to degrees
        clean['Steer'] = sv * (180/np.pi) if sv.abs().max() < 10 else sv
    else:
        clean['Steer'] = 0.0

    # 4. G-Forces (Normalize to Gs)
    c_lat = find_col(df, ['lat', 'g_x', 'accel_x'])
    c_lon = find_col(df, ['lon', 'g_y', 'accel_y'])
    clean['LatG'] = pd.to_numeric(df[c_lat], errors='coerce').fillna(0) if c_lat else 0.0
    clean['LonG'] = pd.to_numeric(df[c_lon], errors='coerce').fillna(0) if c_lon else 0.0
    if clean['LatG'].abs().max() > 5.0: clean['LatG'] /= 9.81
    if clean['LonG'].abs().max() > 5.0: clean['LonG'] /= 9.81

    # 5. Driver Inputs
    c_thr = find_col(df, ['throt', 'gas', 'accel_p'])
    c_brk = find_col(df, ['brake', 'brk', 'press'])
    clean['Throttle'] = pd.to_numeric(df[c_thr], errors='coerce').fillna(0) if c_thr else 0.0
    clean['Brake'] = pd.to_numeric(df[c_brk], errors='coerce').fillna(0) if c_brk else 0.0
    
    return clean.sort_values('Dist').reset_index(drop=True)

# --- 4. AUDIT ENGINE ---
def render_audit(df_d, df_b):
    # Setup interpolation grid
    max_dist = min(df_d['Dist'].max(), df_b['Dist'].max())
    if max_dist <= 0:
        st.error("Invalid distance data detected.")
        return
        
    grid = np.linspace(0, max_dist, 2500)
    
    def resample(df):
        return pd.DataFrame({
            'Speed': np.interp(grid, df['Dist'], df['Speed']),
            'Steer': np.interp(grid, df['Dist'], df['Steer']),
            'LatG': np.interp(grid, df['Dist'], df['LatG']),
            'LonG': np.interp(grid, df['Dist'], df['LonG']),
            'Throttle': np.interp(grid, df['Dist'], df['Throttle']),
            'Brake': np.interp(grid, df['Dist'], df['Brake']),
        })
    
    d, b = resample(df_d), resample(df_b)
    
    # Delta Calculation (Time = Distance / Velocity)
    v_d_ms = np.maximum(d['Speed'].values / 3.6, 1.0)
    v_b_ms = np.maximum(b['Speed'].values / 3.6, 1.0)
    dist_delta = np.diff(grid, prepend=0)
    
    # Use numpy for the cumulative sum to avoid Pandas indexing errors
    delta_series = np.cumsum(dist_delta / v_d_ms - dist_delta / v_b_ms)
    
    # Display Total Delta
    st.metric("Total Lap Delta", f"{delta_series[-1]:.3f}s", delta_color="inverse")
    st.header("🏁 Universal Engineering Audit")

    # Corner Detection (Steer > 10 deg, Length > 30m)
    d['SteerSmooth'] = d['Steer'].rolling(window=40, center=True).mean().fillna(0)
    is_corner = d['SteerSmooth'].abs() > 10
    events = (is_corner != is_corner.shift()).cumsum()
    
    found_any = False
    audit_idx = 1
    
    for eid in events.unique():
        idx = events == eid
        if not is_corner[idx].iloc[0]: continue
        
        # Filter out noise (shorter than 30 meters)
        if (grid[idx][-1] - grid[idx][0]) < 30: continue
        
        found_any = True
        with st.expander(f"📍 Event {audit_idx} | Apex at {grid[idx].mean():.0f}m", expanded=True):
            v_min_d = d[idx]['Speed'].min()
            v_min_b = b[idx]['Speed'].min()
            v_diff = v_min_d - v_min_b
            
            # Utilization (Assuming 1.8G limit)
            g_max = np.sqrt(d[idx]['LatG']**2 + d[idx]['LonG']**2).max()
            util = min((g_max / 1.8) * 100, 100.0)
            
            col1, col2 = st.columns([2,1])
            col2.metric("Tire Util.", f"{util:.1f}%")
            col2.metric("V-Min Delta", f"{v_diff:.1f} km/h")
            
            if v_diff < -0.5:
                col1.markdown('<div class="critical-card"><strong>LOW APEX SPEED.</strong> You are over-slowing. Try to release the brake 5m earlier.</div>', unsafe_allow_html=True)
            elif util < 85:
                col1.markdown('<div class="warning-card"><strong>UNDER-DRIVING.</strong> You have grip left on the table. Increase entry speed.</div>', unsafe_allow_html=True)
            else:
                col1.markdown('<div class="success-card"><strong>CLEAN PHASE.</strong> Inputs are optimized. Focus on line geometry.</div>', unsafe_allow_html=True)
        audit_idx += 1

    if not found_any:
        st.info("No significant corners detected. Check your steering data or compare different laps.")

# --- 5. MAIN APP ---
def main():
    apply_custom_css()
    
    # Get CSVs from current directory
    files = [f for f in os.listdir('.') if f.endswith('.csv')]
    
    if not files:
        st.title("🏎️ Race Engineer Pro")
        st.warning("No CSV files found. Please upload telemetry files to the repository.")
        return

    with st.sidebar:
        st.title("🛠️ Analysis Config")
        d_file = st.selectbox("Driver Lap", files, index=0)
        b_file = st.selectbox("Benchmark Lap", files, index=min(1, len(files)-1))
        
        if d_file == b_file:
            st.error("Select two different laps!")
            st.stop()
            
        st.divider()
        with st.expander("🔍 Data Diagnostics"):
            st.write("Checking columns for:", d_file)
            temp_df = pd.read_csv(d_file, nrows=5)
            st.write(list(temp_df.columns))

    try:
        df_d = process_telemetry(pd.read_csv(d_file))
        df_b = process_telemetry(pd.read_csv(b_file))
        render_audit(df_d, df_b)
    except Exception as e:
        st.error(f"Critical Error: {e}")

if __name__ == "__main__":
    main()
