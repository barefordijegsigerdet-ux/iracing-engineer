import streamlit as st
import pandas as pd
import numpy as np
import os

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro v3.3", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .critical-card { background-color: #2d1b1e; border-left: 10px solid #ff3344; padding: 20px; margin-bottom: 15px; border-radius: 4px; }
        .warning-card { background-color: #2d261b; border-left: 10px solid #ffcc00; padding: 20px; margin-bottom: 15px; border-radius: 4px; }
        .success-card { background-color: #1b2d1e; border-left: 100px solid #00ff88; padding: 20px; margin-bottom: 15px; border-radius: 4px; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. FUZZY COLUMN MATCHER ---
def find_col(df, keywords):
    for k in keywords:
        for c in df.columns:
            if k.lower() in c.lower(): return c
    return None

# --- 3. INGESTION ENGINE (HIGH TOLERANCE) ---
def process_telemetry(df):
    df.columns = [c.strip() for c in df.columns]
    new_df = pd.DataFrame()
    
    # Distance
    c_dist = find_col(df, ['dist', 'mous', 'pos'])
    new_df['Dist'] = pd.to_numeric(df[c_dist], errors='coerce').fillna(0) if c_dist else np.arange(len(df))
    
    # Speed (Convert to km/h)
    c_spd = find_col(df, ['speed', 'vel', 'v_'])
    if c_spd:
        spd = pd.to_numeric(df[c_spd], errors='coerce').fillna(0)
        new_df['Speed'] = spd * 3.6 if spd.max() < 100 else spd
    else:
        new_df['Speed'] = 0

    # Steering (Degrees)
    c_str = find_col(df, ['steer', 'wheel', 'angle', 'str'])
    if c_str:
        str_val = pd.to_numeric(df[c_str], errors='coerce').fillna(0)
        new_df['Steer'] = str_val * (180/np.pi) if str_val.abs().max() < 10 else str_val
    else:
        new_df['Steer'] = 0

    # G-Forces
    c_lat = find_col(df, ['lat', 'g_x'])
    c_lon = find_col(df, ['lon', 'g_y', 'accel'])
    new_df['LatG'] = pd.to_numeric(df[c_lat], errors='coerce').fillna(0) if c_lat else 0
    new_df['LonG'] = pd.to_numeric(df[c_lon], errors='coerce').fillna(0) if c_lon else 0
    # Normalize if in m/s^2
    if new_df['LatG'].abs().max() > 5: new_df['LatG'] /= 9.81
    if new_df['LonG'].abs().max() > 5: new_df['LonG'] /= 9.81

    # Throttle/Brake
    c_thr = find_col(df, ['throt', 'gas', 'accel_p'])
    c_brk = find_col(df, ['brake', 'brk', 'press'])
    new_df['Throttle'] = pd.to_numeric(df[c_thr], errors='coerce').fillna(0) if c_thr else 0
    new_df['Brake'] = pd.to_numeric(df[c_brk], errors='coerce').fillna(0) if c_brk else 0
    
    return new_df.sort_values('Dist').reset_index(drop=True)

# --- 4. AUDIT ENGINE ---
def render_audit(df_d, df_b):
    # Interpolation to match distances
    max_dist = min(df_d['Dist'].max(), df_b['Dist'].max())
    grid = np.linspace(0, max_dist, 2000)
    
    def sync(df):
        return pd.DataFrame({
            'Speed': np.interp(grid, df['Dist'], df['Speed']),
            'Steer': np.interp(grid, df['Dist'], df['Steer']),
            'Throttle': np.interp(grid, df['Dist'], df['Throttle']),
            'LatG': np.interp(grid, df['Dist'], df['LatG']),
            'LonG': np.interp(grid, df['Dist'], df['LonG']),
        })
    
    d, b = sync(df_d), sync(df_b)
    
    # Delta
    v_d, v_b = np.maximum(d['Speed']/3.6, 1.0), np.maximum(b['Speed']/3.6, 1.0)
    delta = np.cumsum(np.diff(grid, prepend=0)/v_d - np.diff(grid, prepend=0)/v_b)
    
    st.metric("Total Lap Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
    st.header("🏁 Universal Engineering Audit")

    # DETECT EVENTS (Steering > 5 deg, length > 20m)
    d['SteerSmooth'] = d['Steer'].rolling(window=20, center=True).mean().fillna(0)
    is_corner = d['SteerSmooth'].abs() > 5
    events = (is_corner != is_corner.shift()).cumsum()
    
    found_events = 0
    for eid in events.unique():
        idx = events == eid
        if not is_corner[idx].iloc[0] or (grid[idx][-1] - grid[idx][0] < 20): continue
        
        found_events += 1
        with st.expander(f"📍 Event {found_events} | Apex at {grid[idx].mean():.0f}m", expanded=True):
            v_delta = d[idx]['Speed'].min() - b[idx]['Speed'].min()
            util = min((np.sqrt(d[idx]['LatG']**2 + d[idx]['LonG']**2).max() / 1.8) * 100, 100.0)
            
            c1, c2 = st.columns([2,1])
            c2.metric("Tire Util.", f"{util:.1f}%")
            c2.metric("V-Min Delta", f"{v_delta:.1f} km/h")
            
            if v_delta < -1.0:
                c1.markdown('<div class="critical-card"><strong>LOW APEX SPEED.</strong> You are over-slowing. Release brake earlier.</div>', unsafe_allow_html=True)
            else:
                c1.markdown('<div class="success-card"><strong>GOOD PACE.</strong> Speed is maintained through apex.</div>', unsafe_allow_html=True)

    if found_events == 0:
        st.warning("⚠️ No distinct corners detected. Showing full lap aggregate data below.")
        st.metric("Avg Speed Delta", f"{d['Speed'].mean() - b['Speed'].mean():.1f} km/h")

# --- 5. APP MAIN ---
def main():
    apply_custom_css()
    files = [f for f in os.listdir('.') if f.endswith('.csv')]
    
    with st.sidebar:
        st.title("🛠️ Settings")
        if len(files) < 2:
            st.error("Please upload at least 2 CSV files.")
            return
        d_name = st.selectbox("Driver Lap", files, index=0)
        b_name = st.selectbox("Benchmark Lap", files, index=1)
        
        if d_name == b_name:
            st.error("Select two different files!")
            st.stop()

    df_d = process_telemetry(pd.read_csv(d_name))
    df_b = process_telemetry(pd.read_csv(b_name))
    render_audit(df_d, df_b)

if __name__ == "__main__":
    main()
