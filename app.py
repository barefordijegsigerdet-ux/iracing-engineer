import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Chassis Lab Pro", layout="wide")

# --- TAB SETUP ---
tab_comp, tab_setup = st.tabs(["📊 Comparative Analysis", "🔧 Setup Engineer"])

with tab_comp:
    st.subheader("Telemetry Comparison")
    c1, c2 = st.columns(2)
    with c1: f1 = st.file_uploader("🟦 Run A (Baseline)", type=['csv'])
    with c2: f2 = st.file_uploader("🟥 Run B (Test Setup)", type=['csv'])

    if f1 and f2:
        df1 = pd.read_csv(f1).sort_values('LapDistPct')
        df2 = pd.read_csv(f2).sort_values('LapDistPct')
        
        # Standardize for Delta Calculation
        dist = np.linspace(0, 1, 3000)
        t1 = np.cumsum(np.diff(df1['LapDistPct'], prepend=0) / (df1['Speed'].replace(0,0.1)/3.6))
        t2 = np.cumsum(np.diff(df2['LapDistPct'], prepend=0) / (df2['Speed'].replace(0,0.1)/3.6))
        delta = np.interp(dist, df2['LapDistPct'], t2) - np.interp(dist, df1['LapDistPct'], t1)

        # HIGH-DENSITY COMPARISON PLOT
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                            row_heights=[0.2, 0.4, 0.2, 0.2],
                            subplot_titles=("Time Delta (Negative = Run B is faster)", "Speed", "Brake/Throttle", "G-Sum (Total Grip)"))

        # 1. Delta (The most important line)
        fig.add_trace(go.Scatter(x=dist*100, y=delta, name="Delta", fill='tozeroy', line=dict(color='white')), row=1, col=1)
        
        # 2. Speed Overlay
        fig.add_trace(go.Scatter(x=df1['LapDistPct']*100, y=df1['Speed']*3.6, name="Run A", line=dict(color='blue', width=1)), row=2, col=1)
        fig.add_trace(go.Scatter(x=df2['LapDistPct']*100, y=df2['Speed']*3.6, name="Run B", line=dict(color='red', width=1.5)), row=2, col=1)
        
        # 3. Pedals (Run B focused)
        fig.add_trace(go.Scatter(x=df2['LapDistPct']*100, y=df2['Throttle']*100, name="Thr B", line=dict(color='green')), row=3, col=1)
        fig.add_trace(go.Scatter(x=df2['LapDistPct']*100, y=df2['Brake']*100, name="Brk B", fill='tozeroy', line=dict(color='rgba(255,255,255,0.2)')), row=3, col=1)

        # 4. G-Sum Logic (Setup Performance)
        # G-Sum = sqrt(LatG^2 + LongG^2). Higher peaks = more overall car grip.
        gsum1 = np.sqrt(df1['GForceLat']**2 + df1['GForceLong']**2)
        gsum2 = np.sqrt(df2['GForceLat']**2 + df2['GForceLong']**2)
        fig.add_trace(go.Scatter(x=df1['LapDistPct']*100, y=gsum1, name="G-Sum A", line=dict(color='blue', opacity=0.3)), row=4, col=1)
        fig.add_trace(go.Scatter(x=df2['LapDistPct']*100, y=gsum2, name="G-Sum B", line=dict(color='red')), row=4, col=1)

        fig.update_layout(height=900, template="plotly_dark", showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
