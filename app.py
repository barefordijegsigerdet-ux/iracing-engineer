import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="G61 Performance Hub", layout="wide")

# --- DATA: THE ENGINEER'S KNOWLEDGE BASE ---
CHASSIS_LOGIC = {
    "Corner Phase": {
        "Entry (Braking/Turn-in)": {
            "Understeer": "Move Brake Bias forward or soften Front Springs.",
            "Oversteer": "Move Brake Bias rearward or stiffen Front Bump/Compression."
        },
        "Mid-Corner (Apex/Coasting)": {
            "Understeer": "Soften Front Anti-Roll Bar (ARB) or increase Front Wing.",
            "Oversteer": "Soften Rear ARB or increase Rear Wing."
        },
        "Exit (Throttle Application)": {
            "Understeer": "Soften Front Rebound or increase Rear Compression.",
            "Oversteer": "Soften Rear Springs or increase Rear Toe-in."
        }
    }
}

# --- TAB NAVIGATION ---
tab_telemetry, tab_setup = st.tabs(["📊 Full Telemetry Analysis", "🔧 Setup Engineer"])

# --- TAB 1: FULL TELEMETRY (The G61 View) ---
with tab_telemetry:
    st.subheader("High-Density Telemetry")
    col_u, col_r = st.columns(2)
    with col_u: user_file = st.file_uploader("🟥 Your Lap (CSV)", type=['csv'])
    with col_r: ref_file = st.file_uploader("🟦 Reference (CSV)", type=['csv'])

    if user_file and ref_file:
        df_u = pd.read_csv(user_file).sort_values('LapDistPct')
        df_r = pd.read_csv(ref_file).sort_values('LapDistPct')
        
        # High-Density Plotting
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                            subplot_titles=("Speed", "Throttle/Brake", "Steering", "Gear"))
        
        # Speed
        fig.add_trace(go.Scatter(x=df_u['LapDistPct'], y=df_u['Speed']*3.6, name="You", line=dict(color='red')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_r['LapDistPct'], y=df_r['Speed']*3.6, name="Ref", line=dict(color='blue', dash='dot')), row=1, col=1)
        
        # Pedals
        fig.add_trace(go.Scatter(x=df_u['LapDistPct'], y=df_u['Throttle']*100, name="Thr", line=dict(color='green')), row=2, col=1)
        fig.add_trace(go.Scatter(x=df_u['LapDistPct'], y=df_u['Brake']*100, name="Brk", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        
        # Steering
        fig.add_trace(go.Scatter(x=df_u['LapDistPct'], y=df_u['SteeringWheelAngle'], name="Steer", line=dict(color='cyan')), row=3, col=1)
        
        fig.update_layout(height=800, template="plotly_dark", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# --- TAB 2: SETUP ENGINEER (The Deep Dive) ---
with tab_setup:
    st.subheader("Chassis & Aero Consultant")
    
    col_diag, col_tool = st.columns([1, 1.5])
    
    with col_diag:
        st.write("### 🩺 Diagnostic Input")
        phase = st.selectbox("Where is the car struggling?", list(CHASSIS_LOGIC["Corner Phase"].keys()))
        issue = st.radio("What is the sensation?", ["Understeer", "Oversteer"])
        
        st.write("---")
        st.write("### 🌡️ Tire Thermal Audit")
        st.caption("Input your temps (Inner - Middle - Outer) after a 5-lap stint.")
        t_left = st.text_input("Front Left (e.g., 85-82-79)", "80-80-80")
        
        if st.button("Analyze Balance"):
            st.session_state.show_fix = True

    with col_tool:
        st.write("### 🛠️ Mechanical Prescription")
        if st.session_state.get('show_fix'):
            recommendation = CHASSIS_LOGIC["Corner Phase"][phase][issue]
            st.success(f"**Recommended Change:** {recommendation}")
            
            # THE "WHY" (Learning the Setup)
            st.info("### 🧠 The Setup Logic")
            if "Springs" in recommendation:
                st.write("By softening the springs on the axle that is sliding, you increase the **Mechanical Grip** by allowing the tire to stay in contact with the track surface more effectively.")
            
            # Tire Logic
            temps = [int(t) for t in t_left.split("-")]
            if temps[0] > temps[2] + 5:
                st.warning("⚠️ **Camber Issue:** Your Inner temp is much higher. Reduce negative Camber to flatten the tire footprint.")
            elif temps[1] > (temps[0] + temps[2]) / 2:
                st.warning("⚠️ **Pressure Issue:** Middle temp is high. Lower your cold tire pressures.")

    st.divider()
    st.write("### 📝 Setup Change Log")
    st.caption("Track your changes. If you don't go faster in 3 laps, revert.")
    st.text_input("Change made:", placeholder="e.g., -2 clicks Rear ARB")
    st.text_area("Resulting Feel:")
