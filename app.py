import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

# --- CONFIGURATION & TRACK DATABASE ---
st.set_page_config(page_title="G61 Pro Race Engineer", layout="wide", initial_sidebar_state="expanded")

TRACK_DB = {
    "Nordschleife": {
        "length": 20832, 
        "sectors": {"Hatzenbach": 0.08, "Flugplatz": 0.17, "Aremberg": 0.26, "Adenauer Forst": 0.38, "Wehrseifen": 0.49, "Bergwerk": 0.61, "Karussell": 0.73, "Pflanzgarten": 0.85, "Döttinger Höhe": 1.00}
    },
    "Zandvoort": {
        "length": 4259, 
        "sectors": {"Sector 1": 0.33, "Sector 2": 0.66, "Sector 3": 1.00}
    },
    "Spa-Francorchamps": {
        "length": 7004, 
        "sectors": {"La Source": 0.15, "Kemmel": 0.35, "Bruxelles": 0.50, "Pouhon": 0.70, "Stavelot": 0.85, "Blanchimont": 1.00}
    }
}

# --- SIDEBAR SETTINGS ---
st.sidebar.header("🔧 Global Settings")
car_type = st.sidebar.selectbox("Car Type", ["Porsche 911 Cup", "GT3 Class", "F4", "LMP2", "Other"])
selected_track = st.sidebar.selectbox("Select Track", list(TRACK_DB.keys()))
track_info = TRACK_DB[selected_track]
track_length = track_info["length"]
track_sectors = track_info["sectors"]

st.title("🏁 Universal Race Engineer")

# --- FILE UPLOADS ---
col_ref, col_user = st.columns(2)
with col_ref:
    ref_file = st.file_uploader("🟦 Reference CSV (Pro)", type=['csv'], key="ref")
with col_user:
    user_file = st.file_uploader("🟥 Your CSV", type=['csv'], key="user")

st.divider()

# --- DATA PROCESSING ENGINE ---
if ref_file and user_file:
    # 1. Load and Pre-process
    df_r = pd.read_csv(ref_file).sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_u = pd.read_csv(user_file).sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_r.columns = df_r.columns.str.strip()
    df_u.columns = df_u.columns.str.strip()

    # 2. Geometry & Physics Reconstruction
    def process_telemetry(df, length):
        # Time Calculation
        dist_diff = df['LapDistPct'].diff().fillna(0) * length
        speed_ms = (df['Speed'] / 3.6).replace(0, 0.1)
        cumulative_time = np.cumsum(dist_diff / speed_ms)
        
        # Track Shape Reconstruction (Using Yaw)
        # We use a -90 deg rotation offset to align 'Up' with North usually
        yaw_rad = df['Yaw']
        dx = dist_diff * np.cos(yaw_rad)
        dy = dist_diff * np.sin(yaw_rad)
        return cumulative_time, np.cumsum(dx), np.cumsum(dy)

    r_time, rx, ry = process_telemetry(df_r, track_length)
    u_time, ux, uy = process_telemetry(df_u, track_length)

    # 3. Standardization (5000 Samples)
    dist_pct = np.linspace(0, 1, 5000)
    dist_meters = dist_pct * track_length
    
    u_time_i = np.interp(dist_pct, df_u['LapDistPct'], u_time)
    r_time_i = np.interp(dist_pct, df_r['LapDistPct'], r_time)
    ux_i, uy_i = np.interp(dist_pct, df_u['LapDistPct'], ux), np.interp(dist_pct, df_u['LapDistPct'], uy)
    rx_i, ry_i = np.interp(dist_pct, df_r['LapDistPct'], rx), np.interp(dist_pct, df_r['LapDistPct'], ry)
    
    delta = u_time_i - r_time_i
    u_speed = np.interp(dist_pct, df_u['LapDistPct'], df_u['Speed'] * 3.6)
    r_speed = np.interp(dist_pct, df_r['LapDistPct'], df_r['Speed'] * 3.6)

    # --- 4. SECTOR PERFORMANCE WIDGETS ---
    st.subheader("⏱️ Sector Performance")
    sec_names = list(track_sectors.keys())
    sec_pcts = [0.0] + list(track_sectors.values())
    
    if 'focus_sector' not in st.session_state:
        st.session_state.focus_sector = "Full Track"

    # Create UI buttons and metrics for sectors
    cols = st.columns(len(sec_names))
    sector_summary_text = []
    
    for i in range(len(sec_names)):
        s_pct, e_pct = sec_pcts[i], sec_pcts[i+1]
        u_val = u_time_i[np.searchsorted(dist_pct, e_pct)] - u_time_i[np.searchsorted(dist_pct, s_pct)]
        r_val = r_time_i[np.searchsorted(dist_pct, e_pct)] - r_time_i[np.searchsorted(dist_pct, s_pct)]
        diff = u_val - r_val
        sector_summary_text.append(f"{sec_names[i]}: {diff:+.3f}s")
        
        with cols[i]:
            if st.button(sec_names[i], use_container_width=True):
                st.session_state.focus_sector = sec_names[i]
            st.write(f"Ref: **{r_val:.2f}s**")
            st.write(f"You: **{u_val:.2f}s**")
            st.metric("Delta", f"{diff:+.3f}s", delta_color="inverse")

    if st.button("🗺️ Reset Track View"):
        st.session_state.focus_sector = "Full Track"

    # --- 5. DYNAMIC TRACK MAP ---
    st.subheader(f"📍 Track View: {st.session_state.focus_sector}")
    fig_map = go.Figure()
    
    # Reference Line
    fig_map.add_trace(go.Scatter(x=rx_i, y=ry_i, mode='lines', line=dict(color='blue', width=8, dash='dot'), name="Reference"))
    # Your Line
    fig_map.add_trace(go.Scatter(x=ux_i, y=uy_i, mode='lines', line=dict(color='red', width=3), name="Your Line"))

    # Apply Focus Zoom
    if st.session_state.focus_sector != "Full Track":
        s_idx = sec_names.index(st.session_state.focus_sector)
        start_p, end_p = sec_pcts[s_idx], sec_pcts[s_idx+1]
        mask = (dist_pct >= start_p) & (dist_pct <= end_p)
        # Crop coordinates to sector with padding
        x_min, x_max = ux_i[mask].min(), ux_i[mask].max()
        y_min, y_max = uy_i[mask].min(), uy_i[mask].max()
        fig_map.update_xaxes(range=[x_min - 60, x_max + 60])
        fig_map.update_yaxes(range=[y_min - 60, y_max + 60])

    fig_map.update_layout(height=600, yaxis_scaleanchor="x", xaxis_visible=False, yaxis_visible=False, template="plotly_dark", margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig_map, use_container_width=True)

    # --- 6. TELEMETRY CHARTS ---
    st.subheader("🏎️ Comparative Telemetry")
    fig_tel = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.3, 0.2, 0.25, 0.25])
    
    # Speed
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=r_speed, name="Ref Speed", line=dict(color='blue')), row=1, col=1)
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=u_speed, name="Your Speed", line=dict(color='red')), row=1, col=1)
    # Time Delta
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=delta, name="Delta (s)", fill='tozeroy', line=dict(color='white')), row=2, col=1)
    # Brake
    u_brake = np.interp(dist_pct, df_u['LapDistPct'], df_u['Brake']) * 100
    r_brake = np.interp(dist_pct, df_r['LapDistPct'], df_r['Brake']) * 100
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=r_brake, name="Ref Brake %", line=dict(color='blue', dash='dot')), row=3, col=1)
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=u_brake, name="Your Brake %", line=dict(color='red', dash='dot')), row=3, col=1)
    # Throttle
    u_thr = np.interp(dist_pct, df_u['LapDistPct'], df_u['Throttle']) * 100
    r_thr = np.interp(dist_pct, df_r['LapDistPct'], df_r['Throttle']) * 100
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=r_thr, name="Ref Throttle %", line=dict(color='rgba(0,0,255,0.2)')), row=4, col=1)
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=u_thr, name="Your Throttle %", line=dict(color='rgba(255,0,0,0.2)')), row=4, col=1)

    fig_tel.update_layout(height=800, hovermode='x unified', template="plotly_dark")
    fig_tel.update_yaxes(range=[-5, 105], row=3, col=1)
    fig_tel.update_yaxes(range=[-5, 105], row=4, col=1)
    st.plotly_chart(fig_tel, use_container_width=True)

    # --- 7. AI COACHING ---
    st.divider()
    if "GEMINI_API_KEY" in st.secrets:
        if st.button("🧠 Generate AI Analysis"):
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target = next((m for m in models if "flash" in m), models[0])
                model = genai.GenerativeModel(target)
                
                prompt = f"Professional race engineer at {selected_track} in {car_type}. Analyze these sector time losses (User vs Ref):\n" + "\n".join(sector_summary_text) + "\nProvide 2 specific technical tips for the worst sector."
                
                with st.spinner("Reviewing your lines..."):
                    response = model.generate_content(prompt)
                    st.info(response.text)
            except Exception as e:
                st.error(f"AI Error: {e}")
