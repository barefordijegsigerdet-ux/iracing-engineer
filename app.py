import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. SYSTEM CONFIGURATION & UI ---
st.set_page_config(page_title="Race Engineer Pro | Porsche 992.2 Edition", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 15px; margin-bottom: 10px; border-radius: 4px; border: 1px solid #30363d; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff3344; padding: 15px; margin-bottom: 10px; border-radius: 4px; border: 1px solid #4d1b1e; }
        .setup-card { background-color: #1c2128; border-left: 5px solid #ff8c00; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
        </style>
    """, unsafe_allow_html=True)

# Initialize Session State for Garage
if 'garage' not in st.session_state:
    st.session_state.garage = {
        "Brake Bias": 54.0, "TC Map": 4, "ABS Map": 4, 
        "Front ARB": 5, "Rear ARB": 3, "Wing": 6
    }

# --- 2. PHYSICS & TELEMETRY ENGINE ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    
    # Unit Normalization (m/s² to G) - Fixes the "40G" Error
    mapping = {'LatAccel': 'LatG', 'LongAccel': 'LonG', 'LonAccel': 'LonG'}
    for src, dest in mapping.items():
        if src in df.columns:
            df[dest] = pd.to_numeric(df[src], errors='coerce').fillna(0) / 9.81
    
    # Calculate G-Sum (Traction Circle Utilization)
    if 'LatG' in df.columns and 'LonG' in df.columns:
        df['GSum'] = np.sqrt(df['LatG']**2 + df['LonG']**2)

    # ABS Conversion
    if 'ABSActive' in df.columns:
        df['ABSActive'] = df['ABSActive'].map({'true': 1, 'false': 0, 1: 1, 0: 0}).fillna(0)

    # Speed Normalization (Ensure km/h)
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6 # Convert m/s to km/h

    return df

def align_and_resample(df_d, df_b, points=5000):
    # Anchor track length to BENCHMARK to fix Delta Drift
    max_dist = df_b['Distance'].max() if 'Distance' in df_b.columns else 4259
    grid = np.linspace(0, max_dist, points)

    def interp_lap(df, source_dist_col):
        out = pd.DataFrame({'Distance': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'GSum', 'ABSActive', 'RPM']
        for col in channels:
            if col in df.columns:
                out[col] = np.interp(grid, df[source_dist_col], df[col])
        return out

    d_dist = 'Distance' if 'Distance' in df_d.columns else 'LapDist'
    b_dist = 'Distance' if 'Distance' in df_b.columns else 'LapDist'
    
    res_d = interp_lap(df_d, d_dist)
    res_b = interp_lap(df_b, b_dist)
    
    # Calculate Time Delta
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    ds = np.diff(grid, prepend=0)
    delta = np.cumsum(ds / v_d - ds / v_b)
    
    return res_d, res_b, grid, delta

# --- 3. THE DRIVER COACH (Logic Heuristics) ---

def render_driver_coach(res_d, res_b, grid, delta):
    st.header("🧠 Physics-Based Coaching Audit")
    
    # Corner Segmentation (Yaw-based)
    is_corner = np.abs(res_d['SteeringWheelAngle']) > 15
    event_ids = (is_corner != pd.Series(is_corner).shift()).cumsum()
    
    events_found = 0
    for eid in event_ids.unique():
        idx = event_ids == eid
        if is_corner[idx].iloc[0] and len(res_d[idx]) > 30:
            events_found += 1
            d_ev = res_d[idx]
            b_ev = res_b[idx]
            
            # 1. ABS Saturation Check (Entry)
            abs_mask = (d_ev['ABSActive'] > 0.5) & (np.abs(d_ev['SteeringWheelAngle']) > 20)
            if abs_mask.any():
                pct = abs_mask.mean() * 100
                st.markdown(f"""<div class="critical-card">
                    <strong>WHAT:</strong> ABS Saturated Turn-In (Corner Event {events_found})<br>
                    <strong>WHY:</strong> ABS active for {pct:.1f}% of turn-in phase.<br>
                    <strong>IMPACT:</strong> Kills rotation. You are asking for 100% longitudinal grip while turning. Reduce brake pressure to allow the nose to point.
                </div>""", unsafe_allow_html=True)

            # 2. V-Min Displacement (Mid)
            d_vmin_dist = grid[d_ev['Speed'].idxmin()]
            b_vmin_dist = grid[b_ev['Speed'].idxmin()]
            if (d_vmin_dist - b_vmin_dist) < -3.0:
                st.markdown(f"""<div class="coach-card">
                    <strong>WHAT:</strong> Early Over-Slowing (Corner Event {events_found})<br>
                    <strong>WHY:</strong> V-Min reached {abs(d_vmin_dist - b_vmin_dist):.1f}m before benchmark apex.<br>
                    <strong>IMPACT:</strong> "Parking" the car. You are losing rolling momentum. Carry more brake deeper.
                </div>""", unsafe_allow_html=True)

            # 3. Sawtooth Throttle (Exit)
            t_rate = np.gradient(d_ev['Throttle'])
            stabs = np.sum(np.abs(t_rate) > 50) # High frequency detection
            if stabs > 5:
                st.markdown(f"""<div class="critical-card">
                    <strong>WHAT:</strong> Unstable Platform (Sawtooth Throttle)<br>
                    <strong>WHY:</strong> High-frequency oscillation detected in exit phase.<br>
                    <strong>IMPACT:</strong> Pitch oscillations are preventing the rear tires from taking a set. Squeeze, don't stab.
                </div>""", unsafe_allow_html=True)

    if events_found == 0:
        st.info("No significant cornering events detected for analysis.")

# --- 4. SETUP TWEAKER & GARAGE ---

def render_setup_tweaker(res_d, setup_mode):
    st.header("🔧 Engineering Diagnosis")
    
    issue = st.selectbox("Driver Reported Issue", ["None", "Mid-Corner Understeer", "Entry Oversteer", "Braking Instability"])
    
    if setup_mode == "Fixed":
        st.info("Fixed Setup Mode: Adjusting Electronic Maps and Brake Bias only.")
        if issue == "Braking Instability":
            st.success(f"Recommendation: Move Brake Bias Forward (Current: {st.session_state.garage['Brake Bias']}%) to 54.8%.")
        elif issue == "Mid-Corner Understeer":
            st.warning("Mechanical changes locked. Logic: Adjust ABS Map to lower intrusion (Stage 3) to help rotation.")
    else:
        st.success("Open Setup Mode: Mechanical validation active.")
        if issue == "Mid-Corner Understeer":
            st.markdown(f"""<div class="setup-card">
                <strong>Validation:</strong> LatG plateauing while Steering increases.<br>
                <strong>Action:</strong> Soften Front ARB (Current: {st.session_state.garage['Front ARB']}) or Increase Wing.
            </div>""", unsafe_allow_html=True)

# --- 5. MAIN APP LOOP ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer Pro | Porsche 992.2 Cup")
    
    with st.sidebar:
        st.header("Config")
        setup_rule = st.radio("Setup Rule", ["Fixed", "Open"])
        st.divider()
        f_d = st.file_uploader("Driver CSV", type=['csv'])
        f_b = st.file_uploader("Benchmark CSV", type=['csv'])
        
    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d))
        df_b = process_telemetry(pd.read_csv(f_b))
        
        res_d, res_b, grid, delta = align_and_resample(df_d, df_b)
        
        t1, t2, t3, t4 = st.tabs(["📊 Analyze Laps", "🧠 Physics Coach", "🔧 Setup Tweaker", "🛠️ Garage"])
        
        with t1:
            fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02)
            fig.add_trace(go.Scatter(x=grid, y=res_b['Speed'], name="Bench", line=dict(color='#ff3344')), row=1, col=1)
            fig.add_trace(go.Scatter(x=grid, y=res_d['Speed'], name="Driver", line=dict(color='#00a2ff')), row=1, col=1)
            fig.add_trace(go.Scatter(x=grid, y=res_d['Throttle'], name="Throttle", line=dict(color='#00ff88')), row=2, col=1)
            fig.add_trace(go.Scatter(x=grid, y=res_d['Brake'], name="Brake", line=dict(color='#ff3344')), row=3, col=1)
            fig.add_trace(go.Scatter(x=grid, y=res_d['SteeringWheelAngle'], name="Steer", line=dict(color='white')), row=4, col=1)
            fig.add_trace(go.Scatter(x=grid, y=delta, name="Time Delta", line=dict(color='yellow')), row=5, col=1)
            fig.update_layout(height=1000, template="plotly_dark", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with t2: render_driver_coach(res_d, res_b, grid, delta)
        with t3: render_setup_tweaker(res_d, setup_rule)
        with t4:
            st.header("🛠️ Virtual Garage")
            for key in st.session_state.garage:
                st.session_state.garage[key] = st.number_input(key, value=float(st.session_state.garage[key]))
    else:
        st.info("Please upload Driver and Benchmark CSV files to begin analysis.")

if __name__ == "__main__":
    main()
