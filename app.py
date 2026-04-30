import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | TC/ABS Monitor", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 20px; margin-bottom: 15px; }
        .intervention-alert { background-color: #2d1b1e; border-left: 5px solid #ff4b4b; padding: 15px; margin-bottom: 10px; color: #ff4b4b; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA INGESTION & SENSOR FUSION ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    
    # 1. Core Physics Channels
    req = ['LapDistPct', 'Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatAccel', 'LongAccel']
    for col in req:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 2. TC/ABS Monitoring Logic
    # Check for native channels
    if 'TCActive' not in df.columns:
        # Fallback: Calculate Rear Wheel Slip
        # Expected columns: WheelSpeed_FL, WheelSpeed_FR, WheelSpeed_RL, WheelSpeed_RR
        ws_cols = ['WheelSpeed_FL', 'WheelSpeed_FR', 'WheelSpeed_RL', 'WheelSpeed_RR']
        if all(c in df.columns for c in ws_cols):
            avg_f = (df['WheelSpeed_FL'] + df['WheelSpeed_FR']) / 2
            avg_r = (df['WheelSpeed_RL'] + df['WheelSpeed_RR']) / 2
            # Avoid division by zero
            avg_f = np.where(avg_f < 1, 1, avg_f)
            slip = (avg_r / avg_f) - 1
            df['TCActive'] = (slip > 0.03).astype(int)
        else:
            df['TCActive'] = 0
    
    if 'ABSActive' not in df.columns: df['ABSActive'] = 0

    # 3. Unit Normalization
    if df['Speed'].max() < 100: df['Speed'] *= 3.6
    if df['LapDistPct'].max() > 1.1: df['LapDistPct'] /= 100.0
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1: df[col] *= 100.0
            
    return df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])

def align_and_resample(df_d, df_b, points=5000):
    grid = np.linspace(0, 1, points)
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'TCActive', 'ABSActive']
        for col in channels:
            out[col] = np.interp(grid, df['LapDistPct'], df[col]) if col in df.columns else 0.0
        return out
    res_d, res_b = interp_channel(df_d), interp_channel(df_b)
    res_d['SteeringSmooth'] = res_d['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    return res_d, res_b, grid

# --- MODULE: DRIVER COACH (CRUTCH DETECTOR) ---

def analyze_exit_phase(res_d, grid):
    """Analyzes TC dependency from Apex to 100% Throttle."""
    # Detect a corner (Simplified: Steering > 15)
    is_corner = np.abs(res_d['SteeringSmooth']) > 15
    if not any(is_corner): return []

    # Find Apex (Min Speed in corner)
    apex_idx = res_d['Speed'].idxmin()
    
    # Find 100% Throttle point after apex
    post_apex = res_d.iloc[apex_idx:]
    full_throttle_idx = post_apex[post_apex['Throttle'] >= 98].index
    
    if len(full_throttle_idx) > 0:
        exit_indices = res_d.loc[apex_idx : full_throttle_idx[0]]
        tc_duration = (exit_indices['TCActive'] > 0.5).mean()
        
        if tc_duration > 0.15:
            return [f"High TC Dependency ({tc_duration*100:.1f}% of exit): Your throttle application is too aggressive for the rear grip. Soften initial application to reduce intervention."]
    return []

# --- MODULE: SETUP TWEAKER (FIXED SETUP EXCEPTIONS) ---

def render_setup_tweaker(res_d, setup_type):
    st.header("🔧 Setup Tweaker")
    
    # Straight line TC Check (Steering < 10)
    straight_tc = res_d[(res_d['TCActive'] > 0.5) & (np.abs(res_d['SteeringSmooth']) < 10)]
    
    if setup_type == "Fixed":
        st.warning("Fixed Setup Mode: Mechanical changes locked. Electronic Maps available.")
        if not straight_tc.empty:
            st.error("TC MAP SUGGESTION: TC is triggering in a straight line. Reduce TC Map (Lower Intrusion) to improve longitudinal acceleration.")
        return

    st.info("Open Setup Mode: All mechanical and electronic parameters available.")

# --- MAIN APP ---

def main():
    apply_custom_css()
    
    with st.sidebar:
        st.title("🛠️ Config")
        car = st.selectbox("Car Selector", ["Porsche 992 Cup", "GT3 Class"])
        setup = st.radio("Setup Rule", ["Open", "Fixed"])
        st.divider()
        f_d = st.file_uploader("Driver Telemetry", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry", type=['csv'])

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d))
        df_b = process_telemetry(pd.read_csv(f_b))
        res_d, res_b, grid = align_and_resample(df_d, df_b)
        
        t1, t2, t3 = st.tabs(["📊 Analyze Laps", "🧠 Driver Coach", "🔧 Setup Tweaker"])
        
        with t1:
            # 8-Row Stack with Shaded Interventions
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                                subplot_titles=("Speed", "Throttle (TC Shaded)", "Brake (ABS Shaded)", "Steering"))
            x = grid * 100
            
            # Speed
            fig.add_trace(go.Scatter(x=x, y=res_d['Speed'], name="Speed", line=dict(color='cyan')), row=1, col=1)
            
            # Throttle + TC Shading
            fig.add_trace(go.Scatter(x=x, y=res_d['Throttle'], name="Throttle", line=dict(color='#00ff41')), row=2, col=1)
            tc_zone = res_d['Throttle'].where(res_d['TCActive'] > 0.5)
            fig.add_trace(go.Scatter(x=x, y=tc_zone, fill='tozeroy', fillcolor='rgba(255, 140, 0, 0.3)', line=dict(width=0), name="TC Active"), row=2, col=1)
            
            # Brake + ABS Shading
            fig.add_trace(go.Scatter(x=x, y=res_d['Brake'], name="Brake", line=dict(color='#ff4b4b')), row=3, col=1)
            abs_zone = res_d['Brake'].where(res_d['ABSActive'] > 0.5)
            fig.add_trace(go.Scatter(x=x, y=abs_zone, fill='tozeroy', fillcolor='rgba(255, 255, 0, 0.3)', line=dict(width=0), name="ABS Active"), row=3, col=1)
            
            # Steering
            fig.add_trace(go.Scatter(x=x, y=res_d['SteeringSmooth'], name="Steering", line=dict(color='white')), row=4, col=1)
            
            fig.update_layout(height=1000, template="plotly_dark", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with t2:
            st.header("🧠 Driver Coach")
            insights = analyze_exit_phase(res_d, grid)
            for insight in insights:
                st.markdown(f'<div class="coach-card">{insight}</div>', unsafe_allow_html=True)
            if not insights:
                st.success("Clean Exit: No significant TC dependency detected in corner exits.")

        with t3:
            render_setup_tweaker(res_d, setup)

if __name__ == "__main__":
    main()
