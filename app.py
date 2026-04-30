import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Smoothness Heuristics", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 20px; margin-bottom: 15px; }
        .warning-card { background-color: #2d2616; border-left: 5px solid #ffcc00; padding: 20px; margin-bottom: 15px; color: #ffcc00; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff4b4b; padding: 20px; margin-bottom: 15px; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    req = ['LapDistPct', 'Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'ABSActive', 'TCActive']
    for col in req:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Normalization
    if df['Speed'].max() < 100: df['Speed'] *= 3.6
    if df['LapDistPct'].max() > 1.1: df['LapDistPct'] /= 100.0
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1: df[col] *= 100.0
            
    return df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])

def align_and_resample(df_d, df_b, points=5000):
    grid = np.linspace(0, 1, points)
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'ABSActive', 'TCActive']
        for col in channels:
            out[col] = np.interp(grid, df['LapDistPct'], df[col]) if col in df.columns else 0.0
        return out
    res_d, res_b = interp_channel(df_d), interp_channel(df_b)
    return res_d, res_b, grid

# --- MODULE: DRIVER COACH (SMOOTHNESS HEURISTICS) ---

def analyze_smoothness(df):
    insights = []
    
    # 1. Throttle Modulation (Stabbing Detector)
    # Window of 50 samples approx 1 second at 50Hz
    roll_max = df['Throttle'].rolling(window=50, center=True).max()
    roll_min = df['Throttle'].rolling(window=50, center=True).min()
    # Detect if throttle swings > 60% within that 1s window
    stabbing_mask = (roll_max > 80) & (roll_min < 20)
    
    if stabbing_mask.any():
        insights.append({
            "level": "warning",
            "msg": "Unstable Platform: Stop stabbing the throttle. The 992 Cup requires a linear squeeze to load the rear tires. Your current input is upsetting the car's pitch and causing mid-corner oscillations."
        })

    # 2. ABS Threshold Logic (Trail Braking Overshoot)
    # ABS active while brake pressure is low (< 30%) suggests over-driving the turn-in grip
    trail_abs = (df['ABSActive'] > 0.5) & (df['Brake'] < 30) & (df['Brake'] > 5)
    
    if trail_abs.sum() > 50: # Significant duration
        insights.append({
            "level": "critical",
            "msg": "ABS Over-reliance: You are triggering ABS deep into the corner. This is locking the front end and preventing rotation. Reduce your brake pressure by 10-15% during the turn-in phase."
        })
        
    return insights

# --- MODULE: SETUP TWEAKER (FIXED SETUP BIAS CONSULTANT) ---

def render_setup_tweaker(df, setup_type):
    st.header("🔧 Setup Tweaker")
    
    # Calculate ABS Duty Cycle
    braking_points = df[df['Brake'] > 5]
    if len(braking_points) > 0:
        abs_duty_cycle = (braking_points['ABSActive'] > 0.5).sum() / len(braking_points)
    else:
        abs_duty_cycle = 0

    if setup_type == "Fixed":
        st.markdown('<div class="warning-card"><strong>Fixed Setup Mode:</strong> Mechanical changes locked. Analyzing Brake Bias requirements...</div>', unsafe_allow_html=True)
        
        if abs_duty_cycle > 0.50:
            st.error(f"BRAKE BIAS ADVICE: ABS is active for {abs_duty_cycle*100:.1f}% of your braking phase. Suggest migrating Brake Bias Forward (0.4% - 0.8%) to stabilize the platform and reduce front-end locking.")
        else:
            st.success(f"Brake Bias is within acceptable duty cycle ({abs_duty_cycle*100:.1f}% ABS usage).")
        return

    st.info("Open Setup Mode: Full mechanical access enabled.")

# --- MAIN APP ---

def main():
    apply_custom_css()
    
    with st.sidebar:
        st.title("🛠️ Config")
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
            # Telemetry Stack
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                                subplot_titles=("Speed", "Throttle (Smoothness Check)", "Brake (ABS Threshold)"))
            x = grid * 100
            
            fig.add_trace(go.Scatter(x=x, y=res_d['Speed'], name="Speed", line=dict(color='cyan')), row=1, col=1)
            
            # Throttle
            fig.add_trace(go.Scatter(x=x, y=res_d['Throttle'], name="Throttle", line=dict(color='#00ff41')), row=2, col=1)
            # Highlight Stabbing areas in red
            roll_max = res_d['Throttle'].rolling(window=50, center=True).max()
            roll_min = res_d['Throttle'].rolling(window=50, center=True).min()
            stabbing = res_d['Throttle'].where((roll_max > 80) & (roll_min < 20))
            fig.add_trace(go.Scatter(x=x, y=stabbing, name="Stabbing Detected", mode='markers', marker=dict(color='red', size=4)), row=2, col=1)
            
            # Brake
            fig.add_trace(go.Scatter(x=x, y=res_d['Brake'], name="Brake", line=dict(color='#ff4b4b')), row=3, col=1)
            # Highlight ABS Trail Braking Overshoot
            trail_abs_pts = res_d['Brake'].where((res_d['ABSActive'] > 0.5) & (res_d['Brake'] < 30))
            fig.add_trace(go.Scatter(x=x, y=trail_abs_pts, name="ABS Overshoot", mode='markers', marker=dict(color='yellow', size=5)), row=3, col=1)
            
            fig.update_layout(height=900, template="plotly_dark", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with t2:
            st.header("🧠 Driver Coach")
            insights = analyze_smoothness(res_d)
            for insight in insights:
                card_class = "warning-card" if insight['level'] == "warning" else "critical-card"
                st.markdown(f'<div class="{card_class}">{insight["msg"]}</div>', unsafe_allow_html=True)
            if not insights:
                st.success("Input Smoothness: Excellent. No stabbing or ABS over-reliance detected.")

        with t3:
            render_setup_tweaker(res_d, setup)

if __name__ == "__main__":
    main()
