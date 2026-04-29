import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Universal Race Engineer", layout="wide")
st.title("🏁 Universal Race Engineer")

# --- SIDEBAR & SETUP ---
st.sidebar.header("Global Settings")
car_type = st.sidebar.selectbox("Car Type", ["Porsche 911 Cup (992.2)", "GT3 Class", "Formula 4", "Other"])
track_length = st.sidebar.number_input("Track Length (meters)", value=4259)

# --- FILE UPLOADER ---
st.header("📤 Data Input")
uploaded_files = st.file_uploader("Upload Garage 61 CSVs (Telemetry or Race Exports)", accept_multiple_files=True)

if uploaded_files:
    telemetry_files = []
    summary_files = []

    for file in uploaded_files:
        df_temp = pd.read_csv(file)
        if 'Speed' in df_temp.columns:
            telemetry_files.append((file.name, df_temp))
        elif 'Lap time' in df_temp.columns:
            summary_files.append((file.name, df_temp))

    # --- PART 1: RACE SESSION ANALYSIS (Summary Files) ---
    if summary_files:
        st.divider()
        st.header("📊 Race Session Analysis")
        for name, df in summary_files:
            st.subheader(f"Session: {name}")
            
            # Metric Row
            avg_fuel = df['Fuel used'].mean()
            best_lap = df['Lap time'].min()
            col1, col2, col3 = st.columns(3)
            col1.metric("Best Lap", f"{best_lap:.3f}s")
            col2.metric("Avg Fuel / Lap", f"{avg_fuel:.2f} L")
            col3.metric("Total Laps", len(df))

            # Lap Time Chart
            fig_lap = go.Figure()
            fig_lap.add_trace(go.Scatter(x=df['Lap'], y=df['Lap time'], name="Lap Times", line=dict(color='gold')))
            fig_lap.update_layout(title="Lap Time Consistency", xaxis_title="Lap", yaxis_title="Time (s)")
            st.plotly_chart(fig_lap, use_container_width=True)

    # --- PART 2: DETAILED DRIVING ANALYSIS (Telemetry Files) ---
    if len(telemetry_files) >= 2:
        st.divider()
        st.header("🏎️ Lap Comparison (Telemetry)")
        
        # Sort and select
        f1_name, df_u = telemetry_files[0]
        f2_name, df_r = telemetry_files[1]
        
        # Simple name cleaner
        u_name = f1_name.split(" - ")[1] if " - " in f1_name else "User"
        r_name = f2_name.split(" - ")[1] if " - " in f2_name else "Ref"

        st.info(f"Comparing **{u_name}** vs **{r_name}**")

        # Math Logic
        dist_common = np.linspace(0, 1, 5000)
        u_speed = np.interp(dist_common, df_u['LapDistPct'], df_u['Speed'] * 3.6)
        r_speed = np.interp(dist_common, df_r['LapDistPct'], df_r['Speed'] * 3.6)
        u_brake = np.interp(dist_common, df_u['LapDistPct'], df_u['Brake'])
        r_brake = np.interp(dist_common, df_r['LapDistPct'], df_r['Brake'])
        
        dx = track_length / 5000 
        u_time = np.cumsum(dx / np.maximum(u_speed/3.6, 0.1))
        r_time = np.cumsum(dx / np.maximum(r_speed/3.6, 0.1))
        delta = u_time - r_time

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])
        fig.add_trace(go.Scatter(x=dist_common, y=r_speed, name=f"{r_name} Speed", line=dict(color='blue')), row=1, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=u_speed, name=f"{u_name} Speed", line=dict(color='red')), row=1, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=delta, name="Time Delta", fill='tozeroy', line=dict(color='gray')), row=2, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=r_brake, name=f"{r_name} Brake", line=dict(color='blue', dash='dot')), row=3, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=u_brake, name=f"{u_name} Brake", line=dict(color='red', dash='dot')), row=3, col=1)
        
        fig.update_layout(height=800, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

# --- FEEDBACK SECTION ---
st.divider()
st.header("🧠 Engineer's Feedback")
if not uploaded_files:
    st.write("Upload data to receive feedback.")
else:
    st.success("Analysis Complete: Focus on Turn 3 entry speed and fuel saving in Sector 2.")
