import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- ENGINE: EVENT DETECTION ---

def detect_corners(res_d, threshold=15):
    """Segments the lap into corners based on steering input."""
    is_event = np.abs(res_d['SteeringSmooth']) > threshold
    event_ids = (is_event != pd.Series(is_event).shift()).cumsum()
    events = []
    for eid in event_ids.unique():
        idx = event_ids == eid
        if is_event[idx].iloc[0] and len(res_d[idx]) > 25: # 0.5s duration gate
            events.append(res_d.index[idx])
    return events

# --- MODULE: DRIVER COACH (CLINICAL AUDIT) ---

def render_driver_coach(res_d, res_b, grid_m, delta):
    st.header("🧠 Clinical Performance Audit")
    
    corners = detect_corners(res_d)
    if not corners:
        st.info("No significant cornering events detected for audit.")
        return

    # Global Coasting Check (Warning)
    coast_mask = (res_d['Throttle'] < 5) & (res_d['Brake'] < 5)
    coast_pct = coast_mask.mean() * 100
    if coast_pct > 15:
        st.warning(f"**WHAT:** High Coasting. **WHERE:** Transition phases. **WHY:** {coast_pct:.1f}% of the lap spent with zero pedal input. **IMPACT:** You are lazy with weight transfer, resulting in a massive momentum deficit and lost pressure on the tire contact patch.")

    for i, idx in enumerate(corners, 1):
        d_ev = res_d.loc[idx]
        b_ev = res_b.loc[idx]
        g_ev = grid_m[idx]
        
        # 1. ENTRY MODULE: ABS Saturated Turn-In (Critical)
        abs_turn_in = (d_ev['Brake'] > 5) & (np.abs(d_ev['SteeringSmooth']) > 15) & (d_ev['ABSActive'] > 0.5)
        if abs_turn_in.any():
            abs_pct = abs_turn_in.mean() * 100
            st.error(f"**EVENT {i} | WHAT:** ABS Saturated Turn-In. **WHERE:** Corner Entry. **WHY:** ABS is active for {abs_pct:.1f}% of the turn-in phase while steering lock is > 15°. **IMPACT:** You are asking the front tires to do two jobs at once. This saturates the front end, kills rotation, and results in heavy mid-corner understeer.")

        # 2. MID-CORNER MODULE: Early Over-Slowing (Warning)
        d_vmin_idx = d_ev['Speed'].idxmin()
        b_vmin_idx = b_ev['Speed'].idxmin()
        # Calculate distance displacement in meters
        dist_diff = grid_m[d_vmin_idx] - grid_m[b_vmin_idx]
        
        if dist_diff < -3.0: # Driver reaches V-Min 3m or more before benchmark
            st.warning(f"**EVENT {i} | WHAT:** Early Over-Slowing. **WHERE:** Mid-Corner. **WHY:** V-Min reached {abs(dist_diff):.1f}m before the benchmark apex. **IMPACT:** You are 'parking the car' at the center. This kills rolling speed and forces you to over-rotate the car from a standstill, destroying exit momentum.")

        # 3. EXIT MODULE: Unstable Platform / Sawtooth Throttle (Critical)
        # Check exit phase: from apex to end of corner
        exit_df = d_ev.loc[d_vmin_idx:]
        if len(exit_df) > 30:
            # Count throttle "stabs" (0->100->0) using sign changes in derivative
            t_diff = np.diff(exit_df['Throttle'].values)
            # Filter for significant movements
            stabs = np.sum(np.diff(np.sign(t_diff[np.abs(t_diff) > 1.0])) != 0) // 2
            
            if stabs >= 2:
                st.error(f"**EVENT {i} | WHAT:** Unstable Platform (Sawtooth Throttle). **WHERE:** Corner Exit. **WHY:** {stabs} distinct throttle stabs detected during the exit phase. **IMPACT:** Every lift drops the nose and every stab squats the rear. These pitch oscillations prevent the rear tires from finding a stable contact patch, forcing corrective steering inputs and killing top speed.")

# --- MAIN APP REFACTOR ---

def main():
    apply_custom_css()
    with st.sidebar:
        st.title("🛠️ Config")
        track = st.selectbox("Track", list(TRACK_DB.keys()))
        st.divider()
        f_d = st.file_uploader("Driver Telemetry", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry", type=['csv'])

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d), TRACK_DB[track])
        df_b = process_telemetry(pd.read_csv(f_b), TRACK_DB[track])
        
        # Resample
        res_d, res_b, grid_m = align_and_resample(df_d, df_b)
        
        # Physics
        v_d, v_b = np.maximum(res_d['Speed'].values / 3.6, 1.0), np.maximum(res_b['Speed'].values / 3.6, 1.0)
        delta = np.cumsum(np.diff(grid_m, prepend=0) / v_d - np.diff(grid_m, prepend=0) / v_b)
        delta = delta - delta[0]

        t1, t2 = st.tabs(["📊 Analyze Laps", "🧠 Driver Coach"])

        with t1:
            # (Standard 8-row stack logic from previous build)
            st.write("Telemetry Stack Active.")
            
        with t2:
            render_driver_coach(res_d, res_b, grid_m, delta)

# (Include all previous process_telemetry and align_and_resample functions here)
