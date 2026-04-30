import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | 992.2 Cup", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; border: 1px solid #30363d; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff3344; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. ROBUST PHYSICS ENGINE ---

def process_telemetry(df):
    # Clean up whitespace in headers
    df.columns = [c.strip() for c in df.columns]
    
    # ADVANCED DISTANCE DETECTION: Detect any column containing "dist"
    dist_cols = [c for c in df.columns if 'dist' in c.lower()]
    if not dist_cols:
        st.error(f"Data Error: No distance column found. Available: {list(df.columns)}")
        st.stop()
    
    # Standardize distance column name to 'Dist'
    target_dist = dist_cols[0]
    df['Dist'] = pd.to_numeric(df[target_dist], errors='coerce').fillna(0)
    
    # Normalization: m/s² to G-force
    for col in ['LatAccel', 'LongAccel', 'LonAccel']:
        if col in df.columns:
            df[col.replace('Accel', 'G')] = pd.to_numeric(df[col], errors='coerce').fillna(0) / 9.81
    
    # ABS: Convert string/boolean to float
    if 'ABSActive' in df.columns:
        df['ABSActive'] = df['ABSActive'].map({'true': 1, 'false': 0, 1: 1, 0: 0, True: 1, False: 0}).fillna(0)
    
    # Speed: Ensure km/h
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6 
        
    return df.sort_values('Dist').reset_index(drop=True)

def align_and_resample(df_d, df_b, points=5000):
    # Use Benchmark as the master distance grid
    max_dist = df_b['Dist'].max()
    grid = np.linspace(0, max_dist, points)
    
    def interp_lap(df):
        out = pd.DataFrame({'Dist': grid})
        # Essential channels for analysis
        channels = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'ABSActive']
        for col in channels:
            if col in df.columns:
                out[col] = np.interp(grid, df['Dist'], df[col])
            else:
                out[col] = 0.0
        return out
        
    res_d = interp_lap(df_d)
    res_b = interp_lap(df_b)
    
    # Time Delta: sum of (ds / v_driver - ds / v_bench)
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0) # avoid division by zero
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    ds = np.diff(grid, prepend=0)
    delta = np.cumsum(ds / v_d - ds / v_b)
    
    return res_d, res_b, grid, delta

# --- 3. PERFORMANCE AUDIT (Driver Coach) ---

def render_driver_coach(res_d, res_b, grid):
    st.header("🧠 Clinical Performance Audit")
    
    # Segment by Steering Load
    is_corner = np.abs(res_d['SteeringWheelAngle']) > 15
    events = (is_corner != pd.Series(is_corner).shift()).cumsum()
    corner_idx = 0

    for eid in events.unique():
        idx = events == eid
        if is_corner[idx].iloc[0] and len(res_d[idx]) > 40:
            corner_idx += 1
            d_ev = res_d[idx]
            
            # Sawtooth Check (Pedal Stabbing)
            t_rate = np.abs(np.gradient(d_ev['Throttle']))
            if np.sum(t_rate > 40) > 10:
                st.markdown(f'<div class="critical-card"><strong>EVENT {corner_idx}: Sawtooth Throttle.</strong> You are stabbing the pedal. This upsets the 992.2 Cup aero platform. Impact: Lost rear traction.</div>', unsafe_allow_html=True)
            
            # ABS Check (Rotation Killer)
            if (d_ev['ABSActive'] > 0.5).any():
                st.markdown(f'<div class="critical-card"><strong>EVENT {corner_idx}: ABS Saturation.</strong> You are leaning on ABS during turn-in. Impact: Killing front-end rotation.</div>', unsafe_allow_html=True)

# --- 4. MAIN INTERFACE ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer Pro | Porsche 992.2 Cup")
    
    # GitHub Root Directory
    DATA_DIR = "." 
    
    with st.sidebar:
        st.header("Session Config")
        available_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
        
        if available_files:
            available_files.sort()
            f_d_name = st.selectbox("Driver Lap (Blue)", available_files, index=0)
            f_b_name = st.selectbox("Benchmark Lap (Red)", available_files, index=min(1, len(available_files)-1))
        else:
            st.error("No CSV files found in GitHub root.")
            return

    if f_d_name and f_b_name:
        try:
            df_d = process_telemetry(pd.read_csv(f_d_name))
            df_b = process_telemetry(pd.read_csv(f_b_name))
            
            res_d, res_b, grid, delta = align_and_resample(df_d, df_b)
            
            tab1, tab2 = st.tabs(["📊 Telemetry Traces", "🧠 Driver Coach"])
            
            with tab1:
                st.metric("Lap Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
                
                fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03)
                
                # Speed Overlay
                fig.add_trace(go.Scatter(x=grid, y=res_b['Speed'], name="Benchmark", line=dict(color='red', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=grid, y=res_d['Speed'], name="Driver", line=dict(color='cyan', width=2)), row=1, col=1)
                
                # Input Modulation
                fig.add_trace(go.Scatter(x=grid, y=res_d['Throttle'], name="Throttle", line=dict(color='green')), row=2, col=1)
                fig.add_trace(go.Scatter(x=grid, y=res_d['Brake'], name="Brake", line=dict(color='orange')), row=2, col=1)
                
                # Steering Load
                fig.add_trace(go.Scatter(x=grid, y=res_d['SteeringWheelAngle'], name="Steer", line=dict(color='white')), row=3, col=1)
                
                # Time Delta
                fig.add_trace(go.Scatter(x=grid, y=delta, name="Delta", fill='tozeroy', line=dict(color='yellow')), row=4, col=1)
                
                fig.update_layout(height=1000, template="plotly_dark", showlegend=False, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
                
            with tab2:
                render_driver_coach(res_d, res_b, grid)
                
        except Exception as e:
            st.error(f"Engineering Logic Failure: {e}")
            # If it fails, print headers to help us diagnose
            st.write("Headers found in your file:", list(pd.read_csv(f_d_name).columns))

if __name__ == "__main__":
    main()
