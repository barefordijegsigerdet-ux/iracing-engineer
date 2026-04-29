import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Universal Sim Engineer", layout="wide")
st.title("🏁 Universal Sim Engineer")

# Sidebar
st.sidebar.header("Global Settings")
car_type = st.sidebar.selectbox("Car Type", ["Porsche 911 Cup (992.2)", "GT3 Class", "Formula 4", "Other"])
track = st.sidebar.text_input("Track", "Zandvoort")

# File Uploaders with generic names
col1, col2 = st.columns(2)
with col1:
    u_file = st.file_uploader("Upload YOUR Lap (CSV)", type="csv")
with col2:
    r_file = st.file_uploader("Upload REFERENCE Lap (CSV)", type="csv")

if u_file and r_file:
    # Load Data
    df_u = pd.read_csv(u_file)
    df_r = pd.read_csv(r_file)

    # Detect Driver Names from filenames (strip the Garage 61 prefix)
    u_name = u_file.name.split(" - ")[1] if " - " in u_file.name else "Driver A"
    r_name = r_file.name.split(" - ")[1] if " - " in r_file.name else "Driver B"

    st.success(f"Comparing **{u_name}** vs **{r_name}**")

    # Math Logic
    dist_common = np.linspace(0, 1, 5000)
    u_speed = np.interp(dist_common, df_u['LapDistPct'], df_u['Speed'] * 3.6)
    r_speed = np.interp(dist_common, df_r['LapDistPct'], df_r['Speed'] * 3.6)
    u_brake = np.interp(dist_common, df_u['LapDistPct'], df_u['Brake'])
    r_brake = np.interp(dist_common, df_r['LapDistPct'], df_r['Brake'])
    
    # Calculate Time Delta (assuming ~4200m track if not known)
    dx = 4259 / 5000 
    u_time = np.cumsum(dx / np.maximum(u_speed/3.6, 0.1))
    r_time = np.cumsum(dx / np.maximum(r_speed/3.6, 0.1))
    delta = u_time - r_time

    # Create Charts
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05)

    # Speed
    fig.add_trace(go.Scatter(x=dist_common, y=r_speed, name=f"{r_name} (Ref)", line=dict(color='blue')), row=1, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=u_speed, name=f"{u_name} (You)", line=dict(color='red')), row=1, col=1)
    
    # Delta
    fig.add_trace(go.Scatter(x=dist_common, y=delta, name="Time Delta", fill='tozeroy', line=dict(color='gray')), row=2, col=1)
    
    # Brake
    fig.add_trace(go.Scatter(x=dist_common, y=r_brake, name=f"{r_name} Brake", line=dict(color='blue', dash='dot')), row=3, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=u_brake, name=f"{u_name} Brake", line=dict(color='red', dash='dot')), row=3, col=1)

    fig.update_layout(height=800, hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)

    # Summary Insight
    st.subheader("📋 Engineer's Summary")
    max_loss_idx = np.argmax(delta)
    st.info(f"The largest gap is {delta.max():.3f}s. {u_name} is losing the most time at {dist_common[max_loss_idx]*100:.1f}% of the lap.")
