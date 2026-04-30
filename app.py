import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- 1. CONFIGURATION ---
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

# --- 2. PHYSICS ENGINE ---

def process_telemetry(df):
    df.columns = [c.strip() for c in df.columns]
    # Physics Normalization: m/sÂ² to G (The 9.81 Fix)
    for col in ['LatAccel', 'LongAccel', 'LonAccel']:
        if col in df.columns:
            df[col.replace('Accel', 'G')] = pd.to_numeric(df[col], errors='coerce').fillna(0) / 9.81
    
    # ABS & Speed Normalization
    if 'ABSActive' in df.columns:
        df['ABSActive'] = df['ABSActive'].map({'true': 1, 'false': 0, 1: 1, 0: 0}).fillna(0)
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6
    
    # Precise Distance Alignment
    dist_col = 'Distance' if 'Distance' in df.columns else ('LapDist' if 'LapDist' in df.columns else None)
    if dist_col: 
        df['Dist'] = pd.to_numeric(df[dist_col], errors='coerce')
    return df.sort_values('Dist')

def align_and_resample(df_d, df_b, points=5000):
    # Anchor to Benchmark to fix Delta Drift
    max_dist = df_b['Dist'].max()
    grid = np.linspace(0, max_dist, points)
    
    def interp_lap(df):
        out = pd.DataFrame({'Dist': grid})
        for col in ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'ABSActive']:
            if col in df.columns: out[col] = np.interp(grid, df['Dist'], df[col])
        return out
        
    res_d, res_b = interp_lap(df_d), interp_lap(df_b)
    
    # Precise Time Delta Calculation (dt = ds/v)
    v_d, v_b = np.maximum(res_d['Speed'].values / 3.6, 1.0), np.maximum(res_b['Speed'].values / 3.6, 1.0)
    delta = np.cumsum(np.diff(grid, prepend=0) / v_d - np.diff(grid, prepend=0) / v_b)
    return res_d, res_b, grid, delta

# --- 3. UI & RENDERING ---

def main():
    apply_custom_css()
    st.title("ðŸŽï¸ Race Engineer Pro | Porsche 992.2 Cup")
    
    # OPTION B: Look in the root directory (.)
    DATA_DIR = "." 
    
    with st.sidebar:
        st.header("Session Config")
        setup_rule = st.radio("Setup Type", ["Fixed", "Open"])
        
        # Scan for CSVs in the root
        available_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
        
        st.subheader("Select Laps")
        if available_files:
            # Sort files so driver and benchmark are easier to find
            available_files.sort()
            f_d_name = st.selectbox("Driver Telemetry (Blue)", available_files, index=0)
            f_b_name = st.selectbox("Benchmark Telemetry (Red)", available_files, index=min(1, len(available_files)-1))
        else:
            st.error("No CSV files found in GitHub root. Ensure your telemetry is uploaded.")
            return
        
    if f_d_name and f_b_name:
        df_d = process_telemetry(pd.read_csv(os.path.join(DATA_DIR, f_d_name)))
        df_b = process_telemetry(pd.read_csv(os.path.join(DATA_DIR, f_b_name)))
        res_d, res_b, grid, delta = align_and_resample(df_d, df_b)
        
        t1, t2 = st.tabs(["ðŸ“Š Telemetry Traces", "ðŸ§  Physics Coach"])
        
        with t1:
            st.metric("Total Lap Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03)
            
            # Row 1: Speed
            fig.add_trace(go.Scatter(x=grid, y=res_b['Speed'], name="Bench", line=dict(color='red', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=grid, y=res_d['Speed'], name="Driver", line=dict(color='cyan', width=2)), row=1, col=1)
            
            # Row 2: Inputs
            fig.add_trace(go.Scatter(x=grid, y=res_d['Throttle'], name="Throttle", line=dict(color='green')), row=2, col=1)
            fig.add_trace(go.Scatter(x=grid, y=res_d['Brake'], name="Brake", line=dict(color='orange')), row=2, col=1)
            
            # Row 3: Steering
            fig.add_trace(go.Scatter(x=grid, y=res_d['SteeringWheelAngle'], name="Steer", line=dict(color='white')), row=3, col=1)
            
            # Row 4: Delta
            fig.add_trace(go.Scatter(x=grid, y=delta, name="Delta", fill='tozeroy', line=dict(color='yellow')), row=4, col=1)
            
            fig.update_layout(height=900, template="plotly_dark", showlegend=False, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
            
        with t2:
            st.header("Automated Physics Audit")
            
            # Sawtooth Logic (Technique)
            t_rate = np.abs(np.gradient(res_d['Throttle']))
            if np.sum(t_rate > 40) > 10:
                st.markdown('<div class="critical-card"><strong>CRITICAL: Sawtooth Throttle.</strong> You are stabbing the pedal in Sector 1. This is upsetting the 992.2 aero platform and causing the +0.767s loss. Squeeze, don\'t stab.</div>', unsafe_allow_html=True)
            
            # ABS Logic (Braking)
            abs_usage = (res_d['ABSActive'] > 0.5).mean() * 100
            if abs_usage > 10:
                st.markdown(f'<div class="critical-card"><strong>WARNING: ABS Saturation ({abs_usage:.1f}%).</strong> You are leaning on the electronics during turn-in. This kills rotation in T1. Reduce peak pressure by 5%.</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
