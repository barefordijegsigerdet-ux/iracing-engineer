import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Sim Engineering", layout="wide")
st.title("🏁 Race Engineering Dashboard")

# Sidebar for Inputs
st.sidebar.header("Session Settings")
car_type = st.sidebar.selectbox("Select Car", ["Porsche 911 Cup (992.2)", "GT3 Class", "Formula 4"])
track_name = st.sidebar.text_input("Track Name", "Zandvoort")
setup_type = st.sidebar.radio("Setup", ["Fixed", "Open"])

# File Uploaders
col1, col2 = st.columns(2)
with col1:
    u_file = st.file_uploader("Upload YOUR Lap (Jonas)", type="csv")
with col2:
    b_file = st.file_uploader("Upload REFERENCE Lap (Leeroy)", type="csv")

if u_file and b_file:
    # 1. Load Data
    df_u = pd.read_csv(u_file)
    df_b = pd.read_csv(b_file)

    # 2. Distance Interpolation (Crucial for Accuracy)
    # We use 5000 points to represent the track
    dist_common = np.linspace(0, 1, 5000)
    
    u_speed = np.interp(dist_common, df_u['LapDistPct'], df_u['Speed'] * 3.6)
    b_speed = np.interp(dist_common, df_b['LapDistPct'], df_b['Speed'] * 3.6)
    u_brake = np.interp(dist_common, df_u['LapDistPct'], df_u['Brake'])
    b_brake = np.interp(dist_common, df_b['LapDistPct'], df_b['Brake'])
    
    # 3. Calculate Time Delta
    # Approximation: dt = dx/v. 
    # For a 4000m track, each step is 0.8m.
    dx = 4259 / 5000 
    u_time = np.cumsum(dx / np.maximum(u_speed/3.6, 0.1))
    b_time = np.cumsum(dx / np.maximum(b_speed/3.6, 0.1))
    delta = u_time - b_time

    # 4. Interactive Plotly Charts
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.5, 0.2, 0.3])

    # Speed Trace
    fig.add_trace(go.Scatter(x=dist_common, y=b_speed, name="Pro Speed", line=dict(color='blue')), row=1, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=u_speed, name="User Speed", line=dict(color='red')), row=1, col=1)
    
    # Delta Trace
    fig.add_trace(go.Scatter(x=dist_common, y=delta, name="Time Delta", fill='tozeroy', line=dict(color='black')), row=2, col=1)
    
    # Brake Trace
    fig.add_trace(go.Scatter(x=dist_common, y=b_brake, name="Pro Brake", line=dict(color='blue', dash='dash')), row=3, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=u_brake, name="User Brake", line=dict(color='red', dash='dash')), row=3, col=1)

    fig.update_layout(height=800, hovermode='x unified', title_text=f"Analysis: {track_name}")
    st.plotly_chart(fig, use_container_width=True)

    # 5. Summary Insights
    st.subheader("📋 Key Insights")
    max_loss_idx = np.argmax(delta)
    st.warning(f"Maximum time loss of {delta.max():.3f}s occurs at {dist_common[max_loss_idx]*100:.1f}% of the lap.")
