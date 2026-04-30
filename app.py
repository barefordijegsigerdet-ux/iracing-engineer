import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Race Logic Coach", layout="wide", initial_sidebar_state="collapsed")

# --- CORE LOGIC: DATA INTERPRETER ---
def analyze_driving_physics(u_slice, r_slice):
    """Interprets the delta between user and ref to provide coaching."""
    analysis = []
    
    # 1. Brake Release Analysis (The key to corner entry)
    if u_slice['Brake'].mean() > r_slice['Brake'].mean() + 0.1:
        analysis.append("🚫 **Brake Overstay:** You're holding the brake too deep into the corner. This 'overslows' the car and prevents it from rotating naturally.")
    
    # 2. Throttle Commitment (The key to corner exit)
    u_thr_max = u_slice['Throttle'].max()
    r_thr_max = r_slice['Throttle'].max()
    if u_thr_max < r_thr_max - 0.2:
        analysis.append("🐢 **Hesitant Throttle:** You're waiting too long to get back to 100%. If the car feels like it's sliding, use a wider line (late apex) to straighten the exit.")
    
    # 3. Minimum Speed (Apex Speed)
    if u_slice['Speed'].min() < r_slice['Speed'].min() - 5:
        analysis.append("📉 **Low Rolling Speed:** Your apex speed is too low. Try to carry more momentum by releasing the brake slightly earlier.")
        
    return analysis if analysis else ["✅ **Good Fundamentals:** You're matching the pro's technique here. Focus on consistency."]

# --- UI & DATA LOADING ---
st.title("🧠 Race Logic Coach")
st.markdown("This app doesn't just show data; it explains **how** to fix your lap.")

c1, c2 = st.columns(2)
with c1: ref_file = st.file_uploader("🟦 Reference (Pro)", type=['csv'])
with c2: user_file = st.file_uploader("🟥 Your Lap", type=['csv'])

if ref_file and user_file:
    df_r = pd.read_csv(ref_file).sort_values('LapDistPct')
    df_u = pd.read_csv(user_file).sort_values('LapDistPct')
    
    # Standardize and calculate Delta
    dist_pct = np.linspace(0, 1, 5000)
    u_time = np.interp(dist_pct, df_u['LapDistPct'], np.cumsum(np.diff(df_u['LapDistPct'], prepend=0) * 4259 / (df_u['Speed']/3.6)))
    r_time = np.interp(dist_pct, df_r['LapDistPct'], np.cumsum(np.diff(df_r['LapDistPct'], prepend=0) * 4259 / (df_r['Speed']/3.6)))
    delta = u_time - r_time
    
    # Find the "Coachable Moment" (Fastest climbing delta)
    delta_slope = np.gradient(delta)
    target_idx = np.argmax(delta_slope)
    target_pct = dist_pct[target_idx]
    
    # Extract slices for analysis (50m before and after the loss)
    u_slice = df_u[(df_u['LapDistPct'] > target_pct - 0.01) & (df_u['LapDistPct'] < target_pct + 0.01)]
    r_slice = df_r[(df_r['LapDistPct'] > target_pct - 0.01) & (df_r['LapDistPct'] < target_pct + 0.01)]

    # --- COACHING DASHBOARD ---
    st.header("🏁 Coaching Insights")
    
    insight_col, viz_col = st.columns([1, 1])
    
    with insight_col:
        st.subheader("What the data means:")
        feedbacks = analyze_driving_physics(u_slice, r_slice)
        for msg in feedbacks:
            st.info(msg)
            
        st.subheader("The Goal:")
        st.write("Professional drivers focus on **Brake Release** to rotate the car and **Early Full Throttle** to maximize the next straight. Your goal at this specific point is to transition from brake to throttle more smoothly.")

    with viz_col:
        # Comparison of inputs at the error point
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=u_slice['Throttle']*100, name="Your Throttle", line=dict(color='red')))
        fig.add_trace(go.Scatter(y=r_slice['Throttle']*100, name="Pro Throttle", line=dict(color='blue')))
        fig.update_layout(title="Inputs at Error Point", template="plotly_dark", height=300, yaxis_title="% Input")
        st.plotly_chart(fig, use_container_width=True)

    # --- THE DATA (For Reference) ---
    with st.expander("See Raw Telemetry (Optional)"):
        # (Standard telemetry charts go here)
        st.write("Use this only to verify the coaching above.")
