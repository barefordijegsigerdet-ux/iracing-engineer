import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIG & UI SETUP ---
st.set_page_config(page_title="AI Race Engineer", layout="wide", initial_sidebar_state="collapsed")

TRACK_DB = {
    "Zandvoort": {"length": 4259, "sectors": {"S1": 0.35, "S2": 0.70, "S3": 1.00}},
    "Nordschleife": {"length": 20832, "sectors": {"Hatzenbach": 0.08, "Flugplatz": 0.17, "Aremberg": 0.26, "Adenauer Forst": 0.38, "Wehrseifen": 0.49, "Bergwerk": 0.61, "Karussell": 0.73, "Pflanzgarten": 0.85, "Döttinger Höhe": 1.00}}
}

st.title("🧠 AI Race Engineer")
st.markdown("Upload your Garage 61 data for an automated driving style audit.")

# --- DATA PROCESSING ENGINE ---
def process_lap(df, length):
    dist_diff = df['LapDistPct'].diff().fillna(0) * length
    speed_ms = (df['Speed'] / 3.6).replace(0, 0.1)
    time_cum = np.cumsum(dist_diff / speed_ms)
    # Closed-loop geometry correction
    yaw = df['Yaw'].values - (np.pi / 2)
    x_raw, y_raw = np.cumsum(dist_diff * np.cos(yaw)), np.cumsum(dist_diff * np.sin(yaw))
    return time_cum, x_raw - (df['LapDistPct'] * x_raw.iloc[-1]), y_raw - (df['LapDistPct'] * y_raw.iloc[-1])

# --- FILE INPUTS ---
c1, c2 = st.columns(2)
with c1: ref_file = st.file_uploader("🟦 Reference (Pro)", type=['csv'])
with c2: user_file = st.file_uploader("🟥 Your Lap", type=['csv'])

if ref_file and user_file:
    df_r = pd.read_csv(ref_file).sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_u = pd.read_csv(user_file).sort_values('LapDistPct').drop_duplicates('LapDistPct')
    
    t_info = TRACK_DB["Zandvoort"] # Defaulting to Zandvoort for this demo
    r_t, rx, ry = process_lap(df_r, t_info['length'])
    u_t, ux, uy = process_lap(df_u, t_info['length'])

    # Standardize data to 5000 points
    dist_pct = np.linspace(0, 1, 5000)
    dist_m = dist_pct * t_info['length']
    delta = np.interp(dist_pct, df_u['LapDistPct'], u_t) - np.interp(dist_pct, df_r['LapDistPct'], r_t)

    # --- AI COACHING LOGIC ---
    st.header("📋 Engineering Audit")
    
    # Identify the "Pain Point" (Where delta climbs the fastest)
    delta_slope = np.gradient(delta)
    max_loss_idx = np.argmax(delta_slope)
    loss_dist = dist_m[max_loss_idx]
    
    # Get local telemetry at loss point
    u_brk_local = np.interp(dist_pct[max_loss_idx], df_u['LapDistPct'], df_u['Brake'])
    r_brk_local = np.interp(dist_pct[max_loss_idx], df_r['LapDistPct'], df_r['Brake'])
    u_spd_local = np.interp(dist_pct[max_loss_idx], df_u['LapDistPct'], df_u['Speed']) * 3.6
    
    audit_col, chart_col = st.columns([1, 2])
    
    with audit_col:
        st.subheader("Biggest Time Loss")
        st.error(f"Loss detected at {loss_dist:.0f}m")
        
        if u_brk_local > r_brk_local + 0.1:
            st.warning("**Over-braking detected.** You are staying on the brakes too long into the apex, killing your rolling speed.")
            st.info("💡 **Fix:** Release the brake 5-10 meters earlier to let the car rotate.")
        elif u_spd_local < 80:
            st.warning("**Low Apex Speed.** Your minimum speed is lower than the reference.")
            st.info("💡 **Fix:** Trust the aero more; carry 5km/h more entry speed.")
        else:
            st.success("Your lines are good here; focus on earlier throttle application.")

    with chart_col:
        # Mini Map highlighting the error zone
        fig_map = go.Figure()
        fig_map.add_trace(go.Scatter(x=rx, y=ry, line=dict(color='gray', width=1), name="Track"))
        fig_map.add_trace(go.Scatter(x=[ux[max_loss_idx]], y=[uy[max_loss_idx]], mode='markers', marker=dict(size=15, color='yellow'), name="Critical Error"))
        fig_map.update_layout(height=300, showlegend=False, template="plotly_dark", xaxis_visible=False, yaxis_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_map, use_container_width=True)

    # --- FULL DASHBOARD ---
    st.divider()
    tel_l, tel_r = st.columns([1, 1.2])
    with tel_l:
        st.plotly_chart(go.Figure(data=[go.Scatter(x=dist_m, y=delta, fill='tozeroy', line=dict(color='white'))]).update_layout(title="Time Delta (s)", height=300, template="plotly_dark"), use_container_width=True)
    with tel_r:
        fig_tel = make_subplots(rows=2, cols=1, shared_xaxes=True)
        fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct, df_u['LapDistPct'], df_u['Speed']*3.6), name="You", line=dict(color='red')), row=1, col=1)
        fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct, df_r['LapDistPct'], df_r['Speed']*3.6), name="Pro", line=dict(color='blue')), row=1, col=1)
        fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct, df_u['LapDistPct'], df_u['Throttle']*100), name="Throttle", line=dict(color='green')), row=2, col=1)
        fig_tel.update_layout(height=400, template="plotly_dark", showlegend=False)
        st.plotly_chart(fig_tel, use_container_width=True)
