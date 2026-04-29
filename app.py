import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION & TRACK DATABASE ---
st.set_page_config(page_title="G61 Dashboard", layout="wide", initial_sidebar_state="collapsed")

# Precise Sector Definitions to match G61 iRacing logic
TRACK_DB = {
    "Nordschleife": {
        "length": 20832, 
        "sectors": {"Hatzenbach": 0.08, "Flugplatz": 0.17, "Aremberg": 0.26, "Adenauer Forst": 0.38, "Wehrseifen": 0.49, "Bergwerk": 0.61, "Karussell": 0.73, "Pflanzgarten": 0.85, "Döttinger Höhe": 1.00}
    },
    "Zandvoort": {
        "length": 4259, 
        "sectors": {"S1": 0.35, "S2": 0.70, "S3": 1.00}
    },
    "Spa-Francorchamps": {
        "length": 7004, 
        "sectors": {"S1": 0.15, "S2": 0.50, "S3": 1.00}
    }
}

# --- INITIAL STATE ---
if 'focus_sector' not in st.session_state:
    st.session_state.focus_sector = "Full Track"

# --- SIDEBAR & TRACK SELECT ---
st.sidebar.header("🛠️ Dashboard Controls")
selected_track = st.sidebar.selectbox("Select Track", list(TRACK_DB.keys()))
t_info = TRACK_DB[selected_track]

# --- FILE UPLOADS ---
col_u1, col_u2 = st.columns(2)
with col_u1:
    ref_file = st.file_uploader("🟦 Reference (Pro)", type=['csv'])
with col_u2:
    user_file = st.file_uploader("🟥 Your Lap", type=['csv'])

st.divider()

if ref_file and user_file:
    # 1. Load and Clean
    df_r = pd.read_csv(ref_file).sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_u = pd.read_csv(user_file).sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_r.columns = df_r.columns.str.strip()
    df_u.columns = df_u.columns.str.strip()

    # 2. Advanced Geometry Reconstruction
    def get_physics(df, length):
        dist_diff = df['LapDistPct'].diff().fillna(0) * length
        speed_ms = (df['Speed'] / 3.6).replace(0, 0.1)
        # Orientation fix: Rotate -90deg and flip to match G61 UI layout
        yaw = df['Yaw'] - (np.pi / 2)
        x = np.cumsum(dist_diff * np.cos(yaw))
        y = np.cumsum(dist_diff * np.sin(yaw))
        return np.cumsum(dist_diff / speed_ms), x, y

    r_time, rx, ry = get_physics(df_r, t_info['length'])
    u_time, ux, uy = get_physics(df_u, t_info['length'])

    # Standardize to 5000 points for comparison
    dist_pct = np.linspace(0, 1, 5000)
    dist_m = dist_pct * t_info['length']
    
    u_ti = np.interp(dist_pct, df_u['LapDistPct'], u_time)
    r_ti = np.interp(dist_pct, df_r['LapDistPct'], r_time)
    delta = u_ti - r_ti

    ux_i, uy_i = np.interp(dist_pct, df_u['LapDistPct'], ux), np.interp(dist_pct, df_u['LapDistPct'], uy)
    rx_i, ry_i = np.interp(dist_pct, df_r['LapDistPct'], rx), np.interp(dist_pct, df_r['LapDistPct'], ry)

    # --- DASHBOARD LAYOUT (2 COLUMNS) ---
    left_col, right_col = st.columns([1, 1.2])

    with left_col:
        # A. TRACK MAP (Top Left)
        fig_map = go.Figure()
        fig_map.add_trace(go.Scatter(x=rx_i, y=ry_i, mode='lines', line=dict(color='rgba(0,0,255,0.2)', width=10), name="Pro"))
        fig_map.add_trace(go.Scatter(x=ux_i, y=uy_i, mode='lines', line=dict(color='red', width=2), name="User"))
        
        # Sector Zoom Logic
        if st.session_state.focus_sector != "Full Track":
            s_names = list(t_info['sectors'].keys())
            s_pcts = [0.0] + list(t_info['sectors'].values())
            idx = s_names.index(st.session_state.focus_sector)
            mask = (dist_pct >= s_pcts[idx]) & (dist_pct <= s_pcts[idx+1])
            fig_map.update_xaxes(range=[ux_i[mask].min()-50, ux_i[mask].max()+50])
            fig_map.update_yaxes(range=[uy_i[mask].min()-50, uy_i[mask].max()+50])

        fig_map.update_layout(height=450, yaxis_scaleanchor="x", showlegend=False, template="plotly_dark", 
                             xaxis_visible=False, yaxis_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_map, use_container_width=True)

        # B. TIME DELTA (Bottom Left)
        fig_delta = go.Figure()
        fig_delta.add_trace(go.Scatter(x=dist_m, y=delta, fill='tozeroy', line=dict(color='white', width=2)))
        fig_delta.update_layout(height=350, title="Time Delta (s)", template="plotly_dark", margin=dict(t=30), xaxis_title="Distance (m)")
        st.plotly_chart(fig_delta, use_container_width=True)

    with right_col:
        # C. MULTI-TELEMETRY (Right Side)
        fig_tel = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                               row_heights=[0.3, 0.2, 0.15, 0.15, 0.2])
        
        # 1. Speed
        u_spd = np.interp(dist_pct, df_u['LapDistPct'], df_u['Speed']*3.6)
        r_spd = np.interp(dist_pct, df_r['LapDistPct'], df_r['Speed']*3.6)
        fig_tel.add_trace(go.Scatter(x=dist_m, y=r_spd, line=dict(color='blue', width=1)), row=1, col=1)
        fig_tel.add_trace(go.Scatter(x=dist_m, y=u_spd, line=dict(color='red', width=1)), row=1, col=1)
        
        # 2. Throttle & Brake
        u_thr = np.interp(dist_pct, df_u['LapDistPct'], df_u['Throttle']*100)
        u_brk = np.interp(dist_pct, df_u['LapDistPct'], df_u['Brake']*100)
        fig_tel.add_trace(go.Scatter(x=dist_m, y=u_thr, line=dict(color='red'), opacity=0.5), row=2, col=1)
        fig_tel.add_trace(go.Scatter(x=dist_m, y=u_brk, fill='tozeroy', line=dict(color='white')), row=2, col=1)
        
        # 3. Gear
        if 'Gear' in df_u.columns:
            u_gear = np.interp(dist_pct, df_u['LapDistPct'], df_u['Gear'])
            fig_tel.add_trace(go.Scatter(x=dist_m, y=u_gear, line=dict(color='orange', shape='hv')), row=3, col=1)
        
        # 4. RPM
        if 'RPM' in df_u.columns:
            u_rpm = np.interp(dist_pct, df_u['LapDistPct'], df_u['RPM'])
            fig_tel.add_trace(go.Scatter(x=dist_m, y=u_rpm, line=dict(color='purple')), row=4, col=1)

        # 5. Steering Angle
        if 'SteeringWheelAngle' in df_u.columns:
            u_steer = np.interp(dist_pct, df_u['LapDistPct'], df_u['SteeringWheelAngle'])
            fig_tel.add_trace(go.Scatter(x=dist_m, y=u_steer, line=dict(color='cyan')), row=5, col=1)

        fig_tel.update_layout(height=800, template="plotly_dark", showlegend=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_tel, use_container_width=True)

    # --- FOOTER: SECTOR SELECTOR BAR ---
    st.divider()
    s_names = list(t_info['sectors'].keys())
    s_pcts = [0.0] + list(t_info['sectors'].values())
    
    sec_cols = st.columns(len(s_names) + 1)
    with sec_cols[0]:
        if st.button("Full Track", use_container_width=True):
            st.session_state.focus_sector = "Full Track"
            st.rerun()

    for i, name in enumerate(s_names):
        with sec_cols[i+1]:
            # Calculate sector times for display
            s_idx, e_idx = np.searchsorted(dist_pct, s_pcts[i]), np.searchsorted(dist_pct, s_pcts[i+1]) - 1
            s_diff = delta[e_idx] - delta[s_idx]
            
            if st.button(f"{name}\n{s_diff:+.3f}s", use_container_width=True):
                st.session_state.focus_sector = name
                st.rerun()
