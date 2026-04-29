import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="G61 Analysis Pro", layout="wide", initial_sidebar_state="collapsed")

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

if 'focus_sector' not in st.session_state:
    st.session_state.focus_sector = "Full Track"

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛠️ G61 Engineer")
    selected_track = st.selectbox("Track", list(TRACK_DB.keys()))
    t_info = TRACK_DB[selected_track]

# --- HEADER & UPLOADS ---
st.title(f"🏁 Dashboard: {selected_track}")
u_col1, u_col2 = st.columns(2)
with u_col1:
    ref_file = st.file_uploader("🟦 Reference (Pro)", type=['csv'])
with u_col2:
    user_file = st.file_uploader("🟥 Your Lap", type=['csv'])

if ref_file and user_file:
    df_r = pd.read_csv(ref_file).sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_u = pd.read_csv(user_file).sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_r.columns = df_r.columns.str.strip()
    df_u.columns = df_u.columns.str.strip()

    def process_geometry_closed(df, length):
        dist_diff = df['LapDistPct'].diff().fillna(0) * length
        speed_ms = (df['Speed'] / 3.6).replace(0, 0.1)
        time_cum = np.cumsum(dist_diff / speed_ms)
        
        # 1. Initial Integration
        yaw = df['Yaw'].values
        # G61 Orientation: North is Up
        angle = yaw - (np.pi / 2)
        dx = dist_diff * np.cos(angle)
        dy = dist_diff * np.sin(angle)
        
        x_raw = np.cumsum(dx)
        y_raw = np.cumsum(dy)
        
        # 2. Lap Closure Correction (Linear Drift Removal)
        # Find the gap between start (0,0) and end
        err_x = x_raw.iloc[-1]
        err_y = y_raw.iloc[-1]
        
        # Distribute the error back across the lap based on distance percentage
        dist_pct = df['LapDistPct'].values
        x_corr = x_raw - (dist_pct * err_x)
        y_corr = y_raw - (dist_pct * err_y)
        
        return time_cum, x_corr.values, y_corr.values

    r_t, rx, ry = process_geometry_closed(df_r, t_info['length'])
    u_t, ux, uy = process_geometry_closed(df_u, t_info['length'])

    # Standardize
    dist_pct_grid = np.linspace(0, 1, 5000)
    dist_m = dist_pct_grid * t_info['length']
    u_ti = np.interp(dist_pct_grid, df_u['LapDistPct'], u_t)
    r_ti = np.interp(dist_pct_grid, df_r['LapDistPct'], r_t)
    delta = u_ti - r_ti

    ux_i = np.interp(dist_pct_grid, df_u['LapDistPct'], ux)
    uy_i = np.interp(dist_pct_grid, df_u['LapDistPct'], uy)
    rx_i = np.interp(dist_pct_grid, df_r['LapDistPct'], rx)
    ry_i = np.interp(dist_pct_grid, df_r['LapDistPct'], ry)

    # --- DASHBOARD LAYOUT ---
    l_col, r_col = st.columns([1, 1.2])

    with l_col:
        # A. TRACK MAP (Now with Closed Loop)
        fig_map = go.Figure()
        fig_map.add_trace(go.Scatter(x=rx_i, y=ry_i, mode='lines', line=dict(color='rgba(0,0,255,0.2)', width=10), name="Ref"))
        fig_map.add_trace(go.Scatter(x=ux_i, y=uy_i, mode='lines', line=dict(color='red', width=2), name="You"))
        
        if st.session_state.focus_sector != "Full Track":
            s_names = list(t_info['sectors'].keys())
            s_pcts = [0.0] + list(t_info['sectors'].values())
            idx = s_names.index(st.session_state.focus_sector)
            mask = (dist_pct_grid >= s_pcts[idx]) & (dist_pct_grid <= s_pcts[idx+1])
            fig_map.update_xaxes(range=[ux_i[mask].min()-60, ux_i[mask].max()+60])
            fig_map.update_yaxes(range=[uy_i[mask].min()-60, uy_i[mask].max()+60])

        fig_map.update_layout(height=450, yaxis_scaleanchor="x", template="plotly_dark", showlegend=False,
                             xaxis_visible=False, yaxis_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_map, use_container_width=True)

        # B. TIME DELTA
        fig_delta = go.Figure()
        fig_delta.add_trace(go.Scatter(x=dist_m, y=delta, fill='tozeroy', line=dict(color='white')))
        fig_delta.update_layout(height=350, title="Time Delta (Seconds)", template="plotly_dark", margin=dict(t=30))
        st.plotly_chart(fig_delta, use_container_width=True)

    with r_col:
        # C. TELEMETRY
        fig_tel = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02)
        
        # Traces
        fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct_grid, df_r['LapDistPct'], df_r['Speed']*3.6), line=dict(color='blue', width=1)), row=1, col=1)
        fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct_grid, df_u['LapDistPct'], df_u['Speed']*3.6), line=dict(color='red', width=1)), row=1, col=1)
        
        fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct_grid, df_u['LapDistPct'], df_u['Throttle']*100), line=dict(color='red', width=1)), row=2, col=1)
        fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct_grid, df_u['LapDistPct'], df_u['Brake']*100), fill='tozeroy', line=dict(color='white', width=0)), row=2, col=1)
        
        if 'Gear' in df_u.columns:
            fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct_grid, df_u['LapDistPct'], df_u['Gear']), line=dict(color='orange', shape='hv')), row=3, col=1)
        
        if 'SteeringWheelAngle' in df_u.columns:
            fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct_grid, df_u['LapDistPct'], df_u['SteeringWheelAngle']), line=dict(color='cyan', width=1)), row=4, col=1)
            
        if 'RPM' in df_u.columns:
            fig_tel.add_trace(go.Scatter(x=dist_m, y=np.interp(dist_pct_grid, df_u['LapDistPct'], df_u['RPM']), line=dict(color='purple', width=1)), row=5, col=1)

        fig_tel.update_layout(height=800, template="plotly_dark", showlegend=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig_tel, use_container_width=True)

    # --- SECTOR NAV BAR ---
    st.divider()
    s_names = list(t_info['sectors'].keys())
    s_pcts = [0.0] + list(t_info['sectors'].values())
    nav = st.columns(len(s_names) + 1)
    
    if nav[0].button("🌐 Reset View", use_container_width=True):
        st.session_state.focus_sector = "Full Track"
        st.rerun()

    for i, name in enumerate(s_names):
        s_idx, e_idx = np.searchsorted(dist_pct_grid, s_pcts[i]), np.searchsorted(dist_pct_grid, s_pcts[i+1]) - 1
        s_diff = delta[e_idx] - delta[s_idx]
        if nav[i+1].button(f"{name}\n{s_diff:+.3f}s", use_container_width=True):
            st.session_state.focus_sector = name
            st.rerun()
