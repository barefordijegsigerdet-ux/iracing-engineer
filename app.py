import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

# --- CONFIGURATION & TRACK DATABASE ---
st.set_page_config(page_title="G61 Pro Race Engineer", layout="wide")

# Garage 61 Style Track Definitions
TRACK_DB = {
    "Nordschleife": {
        "length": 20832,
        "sectors": {
            "S1: Hatzenbach": 0.08, "S2: Flugplatz": 0.17, "S3: Aremberg": 0.26,
            "S4: Adenauer Forst": 0.38, "S5: Wehrseifen": 0.49, "S6: Bergwerk": 0.61,
            "S7: Karussell": 0.73, "S8: Pflanzgarten": 0.85, "S9: Döttinger Höhe": 1.00
        }
    },
    "Zandvoort": {
        "length": 4259,
        "sectors": {"Sector 1": 0.33, "Sector 2": 0.66, "Sector 3": 1.00}
    },
    "Spa-Francorchamps": {
        "length": 7004,
        "sectors": {
            "S1: La Source": 0.15, "S2: Kemmel": 0.35, "S3: Bruxelles": 0.50,
            "S4: Pouhon": 0.70, "S5: Stavelot": 0.85, "S6: Blanchimont": 1.00
        }
    }
}

# --- SIDEBAR SETTINGS ---
st.sidebar.header("🔧 Global Settings")
car_type = st.sidebar.selectbox("Car Type", ["Porsche 911 Cup", "GT3 Class", "F4", "LMP2", "Other"])
selected_track = st.sidebar.selectbox("Select Track", list(TRACK_DB.keys()) + ["Custom"])

if selected_track == "Custom":
    track_length = st.sidebar.number_input("Track Length (m)", value=4000)
    num_s = st.sidebar.slider("Number of Sectors", 2, 12, 3)
    track_sectors = {f"Sector {i+1}": (i+1)/num_s for i in range(num_s)}
else:
    track_length = TRACK_DB[selected_track]["length"]
    track_sectors = TRACK_DB[selected_track]["sectors"]

st.title("🏁 Universal Race Engineer")

# --- FILE UPLOADS ---
col_ref, col_user = st.columns(2)
with col_ref:
    st.subheader("🟦 Reference Lap (Pro)")
    ref_file = st.file_uploader("Upload G61 CSV (Ref)", type=['csv'], key="ref")
with col_user:
    st.subheader("🟥 Your Lap")
    user_file = st.file_uploader("Upload G61 CSV (User)", type=['csv'], key="user")

st.divider()

# --- DATA PROCESSING ---
if ref_file and user_file:
    df_r = pd.read_csv(ref_file)
    df_u = pd.read_csv(user_file)
    df_r.columns = df_r.columns.str.strip()
    df_u.columns = df_u.columns.str.strip()
    
    # Clean and Sort
    df_r = df_r.sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_u = df_u.sort_values('LapDistPct').drop_duplicates('LapDistPct')

    # Time Calculation Function
    def calc_lap_time(df, length):
        dist_diff = df['LapDistPct'].diff().fillna(0) * length
        speed_ms = (df['Speed'] / 3.6).replace(0, 0.1)
        return np.cumsum(dist_diff / speed_ms)

    u_total_time = calc_lap_time(df_u, track_length)
    r_total_time = calc_lap_time(df_r, track_length)

    # Standard Interpolation (5000 points)
    dist_pct = np.linspace(0, 1, 5000)
    dist_meters = dist_pct * track_length
    
    u_speed = np.interp(dist_pct, df_u['LapDistPct'], df_u['Speed'] * 3.6)
    r_speed = np.interp(dist_pct, df_r['LapDistPct'], df_r['Speed'] * 3.6)
    u_brake = np.interp(dist_pct, df_u['LapDistPct'], df_u['Brake']) * 100
    r_brake = np.interp(dist_pct, df_r['LapDistPct'], df_r['Brake']) * 100
    u_thr = np.interp(dist_pct, df_u['LapDistPct'], df_u['Throttle']) * 100
    r_thr = np.interp(dist_pct, df_r['LapDistPct'], df_r['Throttle']) * 100
    
    u_time_i = np.interp(dist_pct, df_u['LapDistPct'], u_total_time)
    r_time_i = np.interp(dist_pct, df_r['LapDistPct'], r_total_time)
    delta = u_time_i - r_time_i

    # --- 1. PRO TRACK MAP (Dual Line + Sector Markers) ---
    st.subheader("📍 Track Map & Line Analysis")
    
    def get_coords(df, length):
        if 'PosX' in df.columns and 'PosY' in df.columns:
            return df['PosX'], df['PosY']
        # Yaw Reconstruction if PosX/Y missing
        dt = df['LapDistPct'].diff().fillna(0) * length
        return np.cumsum(dt * np.cos(df['Yaw'])), np.cumsum(dt * np.sin(df['Yaw']))

    ux, uy = get_coords(df_u, track_length)
    rx, ry = get_coords(df_r, track_length)
    ux_i, uy_i = np.interp(dist_pct, df_u['LapDistPct'], ux), np.interp(dist_pct, df_u['LapDistPct'], uy)
    rx_i, ry_i = np.interp(dist_pct, df_r['LapDistPct'], rx), np.interp(dist_pct, df_r['LapDistPct'], ry)

    # Build Sector Color Array
    sector_map_colors = np.zeros(5000)
    last_p = 0
    for i, (name, p) in enumerate(track_sectors.items()):
        sector_map_colors[np.searchsorted(dist_pct, last_p):np.searchsorted(dist_pct, p)] = i
        last_p = p

    fig_map = go.Figure()
    # Reference Line (Thick Blue)
    fig_map.add_trace(go.Scatter(x=rx_i, y=ry_i, mode='lines', line=dict(color='rgba(0, 0, 255, 0.3)', width=10), name="Reference Line"))
    # Your Line (Thin Red)
    fig_map.add_trace(go.Scatter(x=ux_i, y=uy_i, mode='lines', line=dict(color='rgba(255, 0, 0, 0.9)', width=3), name="Your Line"))
    # Sector Background Dots
    fig_map.add_trace(go.Scatter(x=rx_i, y=ry_i, mode='markers', marker=dict(size=4, color=sector_map_colors, colorscale='Turbo'), name="Sectors", hoverinfo='skip'))

    fig_map.update_layout(height=600, xaxis_visible=False, yaxis_visible=False, yaxis_scaleanchor="x", margin=dict(l=0,r=0,t=0,b=0), legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
    st.plotly_chart(fig_map, use_container_width=True)

    # --- 2. SECTOR SPLITS ---
    st.subheader("⏱️ Sector Metrics")
    s_cols = st.columns(3)
    sector_summary = []
    last_p = 0
    for i, (name, p) in enumerate(track_sectors.items()):
        s_idx = np.searchsorted(dist_pct, last_p)
        e_idx = np.searchsorted(dist_pct, p) - 1
        s_loss = delta[e_idx] - delta[s_idx]
        sector_summary.append(f"{name}: {s_loss:.3f}s")
        with s_cols[i % 3]:
            st.metric(name, f"{s_loss:.3f}s", delta_color="inverse")
        last_p = p

    # --- 3. TELEMETRY GRAPHS ---
    st.subheader("🏎️ Comparative Analysis")
    fig_tel = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.4, 0.15, 0.2, 0.2])
    
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=r_speed, name="Ref Speed", line=dict(color='blue')), row=1, col=1)
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=u_speed, name="Your Speed", line=dict(color='red')), row=1, col=1)
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=delta, name="Delta", fill='tozeroy', line=dict(color='gray')), row=2, col=1)
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=r_brake, name="Ref Brake %", line=dict(color='blue', dash='dot')), row=3, col=1)
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=u_brake, name="Your Brake %", line=dict(color='red', dash='dot')), row=3, col=1)
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=r_thr, name="Ref Throttle %", line=dict(color='rgba(0,0,255,0.2)')), row=4, col=1)
    fig_tel.add_trace(go.Scatter(x=dist_meters, y=u_thr, name="Your Throttle %", line=dict(color='rgba(255,0,0,0.2)')), row=4, col=1)

    fig_tel.update_layout(height=800, hovermode='x unified', xaxis4_title="Distance (m)")
    fig_tel.update_yaxes(range=[-5, 105], row=3, col=1)
    fig_tel.update_yaxes(range=[-5, 105], row=4, col=1)
    st.plotly_chart(fig_tel, use_container_width=True)

    # --- 4. AI COACH ---
    if "GEMINI_API_KEY" in st.secrets:
        if st.button("🧠 Get AI Coaching"):
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target = next((m for m in models if "flash" in m), models[0])
                prompt = f"Pro Race Engineer: Analyze sector deltas for {car_type} at {selected_track}:\n" + "\n".join(sector_summary) + "\nGive 2 sentences of tactical advice."
                with st.spinner("Analyzing..."):
                    st.info(genai.GenerativeModel(target).generate_content(prompt).text)
            except Exception as e:
                st.error(f"AI System Error: {e}")
