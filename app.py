import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Physics Lab", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 20px; margin-bottom: 15px; border-radius: 4px; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff4b4b; padding: 20px; margin-bottom: 15px; border-radius: 4px; }
        .setup-card { background-color: #1c2128; border-left: 5px solid #ff8c00; padding: 20px; margin-bottom: 15px; border-radius: 4px; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING & MATH CHANNELS ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    req = ['LapDistPct', 'Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatAccel', 'LongAccel', 'ABSActive', 'Lat', 'Lon']
    for col in req:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Normalization
    if df['Speed'].max() < 100: df['Speed'] *= 3.6
    if df['LapDistPct'].max() > 1.1: df['LapDistPct'] /= 100.0
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1: df[col] *= 100.0
    
    # Math Channel: G-Sum
    df['GSum'] = np.sqrt(df['LatAccel']**2 + df['LongAccel']**2)
    
    return df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])

def align_and_resample(df_d, df_b, points=5000):
    # Dynamic Track Length Calculation
    # We treat LapDistPct as the master. If LapDist (meters) is missing, 
    # we assume a 4000m proxy for "2 meter" logic.
    grid = np.linspace(0, 1, points)
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatAccel', 'LongAccel', 'ABSActive', 'GSum', 'Lat', 'Lon']
        for col in channels: out[col] = np.interp(grid, df['LapDistPct'], df[col])
        return out
    return interp_channel(df_d), interp_channel(df_b), grid

# --- ENGINE: EVENT SEGMENTATION ---

def detect_events(res_d, steering_threshold=10):
    """Segments the lap into corners based on steering angle."""
    is_event = np.abs(res_d['SteeringWheelAngle']) > steering_threshold
    event_ids = (is_event != pd.Series(is_event).shift()).cumsum()
    events = []
    for eid in event_ids.unique():
        idx = event_ids == eid
        if is_event[idx].iloc[0]: # Only keep 'True' events (corners)
            events.append(res_d.index[idx])
    return events

# --- MODULE: DRIVER COACH (PHYSICS LOGIC) ---

def analyze_driver_coach(res_d, res_b, grid, delta):
    events = detect_events(res_d)
    event_diagnostics = []
    
    # Track Length Proxy (for meter-based logic)
    track_length = 4000 # Default proxy
    
    for event_idx in events:
        # Slice data for this corner
        d_ev = res_d.loc[event_idx]
        b_ev = res_b.loc[event_idx]
        g_ev = grid[event_idx]
        
        # 1. Time Loss in this event
        loss = delta[event_idx[-1]] - delta[event_idx[0]]
        
        diag = {"indices": event_idx, "loss": loss, "flags": []}
        
        # TASK 1: THREE-PHASE LOGIC
        # Entry: Brake Release Derivative
        d_brake_release = np.gradient(d_ev['Brake'], g_ev).min() # Steepest negative slope
        b_brake_release = np.gradient(b_ev['Brake'], g_ev).min()
        if d_brake_release < b_brake_release * 1.2:
            diag['flags'].append("Rapid Pitch Recovery: Releasing brake too fast; nose lifting, losing front grip.")
            
        # Mid: V-Min Displacement
        d_vmin_dist = g_ev[np.argmin(d_ev['Speed'])] * track_length
        b_vmin_dist = g_ev[np.argmin(b_ev['Speed'])] * track_length
        if d_vmin_dist < (b_vmin_dist - 2):
            diag['flags'].append("Early Over-slowing: Reaching V-Min too early. Carry more entry speed.")
            
        # Exit: Traction Circle Conflict
        # Check if Throttle increases while Steering is not decreasing
        steer_delta = np.gradient(np.abs(d_ev['SteeringWheelAngle']))
        throttle_delta = np.gradient(d_ev['Throttle'])
        if np.any((throttle_delta > 2) & (steer_delta >= 0)):
            diag['flags'].append("Understeer Inducement: Applying power before unwinding the wheel.")
            
        # TASK 2: G-SUM TRANSITION
        # Gap between peak braking and peak cornering
        peak_b_idx = d_ev['Brake'].idxmax()
        peak_l_idx = d_ev['LatAccel'].abs().idxmax()
        if peak_l_idx > peak_b_idx:
            transition_gsum = d_ev.loc[peak_b_idx:peak_l_idx, 'GSum'].mean()
            bench_transition_gsum = b_ev.loc[peak_b_idx:peak_l_idx, 'GSum'].mean()
            if transition_gsum < bench_transition_gsum * 0.85:
                diag['flags'].append("Inefficient Transition: Not blending braking and turning effectively (G-Sum drop).")

        # TASK 4: PORSCHE 992 CUP ABS
        if np.any((d_ev['ABSActive'] > 0.5) & (np.abs(d_ev['SteeringWheelAngle']) > 15)):
            diag['flags'].append("CRITICAL: ABS-Induced Understeer. Turning while on ABS is locking the platform.")

        event_diagnostics.append(diag)
        
    # Sort by loss and take Top 3
    top_3 = sorted(event_diagnostics, key=lambda x: x['loss'], reverse=True)[:3]
    return top_3

# --- MODULE: SETUP TWEAKER (VALIDATION LOGIC) ---

def render_setup_tweaker(res_d, driver_report):
    st.header("🔧 Setup Tweaker | Validation Logic")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Balance Signature Check")
        # TASK 3: SIGNATURE CHECK
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=res_d['LatAccel'].abs(), y=res_d['SteeringWheelAngle'].abs(), 
                                 mode='markers', marker=dict(color=res_d['Speed'], colorscale='Viridis')))
        fig.update_layout(template="plotly_dark", xaxis_title="Lateral G", yaxis_title="Steering Angle", height=400)
        st.plotly_chart(fig, use_container_width=True)
        
    with col2:
        st.subheader("Engineering Override")
        # Logic to detect plateau
        # We check if Steering increases significantly while LatAccel stays flat at high Gs
        high_g = res_d[res_d['LatAccel'].abs() > 1.5]
        if not high_g.empty:
            lat_std = high_g['LatAccel'].std()
            steer_range = high_g['SteeringWheelAngle'].max() - high_g['SteeringWheelAngle'].min()
            
            if driver_report == "Understeer":
                if lat_std < 0.1 and steer_range > 20:
                    st.error("VALIDATED: Mechanical Understeer detected. LatAccel plateaued while Steering increased.")
                    st.markdown("- **Action:** Soften Front ARB or Increase Front Wing.")
                else:
                    st.warning("OVERRIDE: Mechanical balance is fine. You are turning beyond the slip angle limit (Scrubbing).")
                    st.markdown("- **Action:** Reduce steering input; wait for the nose to hook.")
            else:
                st.info("Select a handling issue to begin validation.")

# --- MAIN APP ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer Pro | Porsche 992 Cup Edition")
    
    with st.sidebar:
        st.header("Data Ingestion")
        f_d = st.file_uploader("Driver Telemetry", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry", type=['csv'])
        st.divider()
        driver_issue = st.selectbox("Driver Reported Issue", ["None", "Understeer", "Oversteer"])

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d))
        df_b = process_telemetry(pd.read_csv(f_b))
        res_d, res_b, grid = align_and_resample(df_d, df_b)
        
        # Physics Math
        v_d, v_b = res_d['Speed'].values / 3.6, res_b['Speed'].values / 3.6
        delta = np.cumsum(np.diff(grid, prepend=0) * 4000 / np.maximum(v_d, 1.0) - np.diff(grid, prepend=0) * 4000 / np.maximum(v_b, 1.0))

        tab_analyze, tab_coach, tab_setup = st.tabs(["📊 Analyze Laps", "🧠 Physics Coach", "🔧 Setup Tweaker"])

        with tab_analyze:
            # Standard 8-row stack (Simplified for this view)
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02)
            fig.add_trace(go.Scatter(x=grid*100, y=delta, name="Delta", line=dict(color='red')), row=1, col=1)
            fig.add_trace(go.Scatter(x=grid*100, y=res_d['Speed'], name="Speed", line=dict(color='cyan')), row=2, col=1)
            fig.add_trace(go.Scatter(x=grid*100, y=res_d['GSum'], name="G-Sum", line=dict(color='magenta')), row=3, col=1)
            fig.add_trace(go.Scatter(x=grid*100, y=res_d['SteeringWheelAngle'], name="Steering", line=dict(color='white')), row=4, col=1)
            fig.update_layout(height=800, template="plotly_dark", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with tab_coach:
            st.header("Top 3 Time-Loss Events")
            top_events = analyze_driver_coach(res_d, res_b, grid, delta)
            for i, ev in enumerate(top_events, 1):
                dist_start = grid[ev['indices'][0]] * 100
                with st.container():
                    st.markdown(f"### Event {i} (at {dist_start:.1f}% of lap) | Loss: {ev['loss']:.3f}s")
                    for flag in ev['flags']:
                        if "CRITICAL" in flag:
                            st.markdown(f'<div class="critical-card">{flag}</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="coach-card">{flag}</div>', unsafe_allow_html=True)

        with tab_setup:
            render_setup_tweaker(res_d, driver_issue)

    else:
        st.info("Awaiting telemetry files for physics-based audit.")

if __name__ == "__main__":
    main()
