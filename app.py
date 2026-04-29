import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

# --- CONFIGURATION & DATABASE ---
st.set_page_config(page_title="G61 Style Race Engineer", layout="wide")

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

# --- SIDEBAR ---
st.sidebar.header("🔧 Settings")
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
    ref_file = st.file_uploader("Upload G61 CSV", type=['csv'], key="ref")
with col_user:
    st.subheader("🟥 Your Lap")
    user_file = st.file_uploader("Upload G61 CSV", type=['csv'], key="user")

st.divider()

# --- PROCESSING & VISUALIZATION ---
if ref_file and user_file:
    # Load and Clean
    df_r = pd.read_csv(ref_file)
    df_u = pd.read_csv(user_file)
    df_r.columns = df_r.columns.str.strip()
    df_u.columns = df_u.columns.str.strip()
    
    # Sort and Deduplicate to prevent "Flatline" errors
    df_r = df_r.sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_u = df_u.sort_values('LapDistPct').drop_duplicates('LapDistPct')

    # Calculate Time Delta
    def calc_time(df, length):
        dist_diff = df['LapDistPct'].diff().fillna(0) * length
        # Ensure speed is in m/s and not zero
        speed_ms = (df['Speed'] / 3.6).replace(0, 0.1)
        return np.cumsum(dist_diff / speed_ms)

    u_total_time = calc_time(df_u, track_length)
    r_total_time = calc_time(df_r, track_length)

    # Standardize to 5000 points
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

    # 1. TRACK MAP (G61 Style Speed Map)
    st.subheader("📍 Track Map Analysis")
    # If PosX/PosY exist in CSV, use them. Else, use a projection.
    if 'PosX' in df_u.columns and 'PosY' in df_u.columns:
        map_x, map_y = df_u['PosX'], df_u['PosY']
    else:
        map_x = np.cos(dist_pct * 2 * np.pi) * (u_speed + 500)
        map_y = np.sin(dist_pct * 2 * np.pi) * (u_speed + 500)

    fig_map = go.Figure(data=go.Scatter(
        x=map_x, y=map_y, mode='lines',
        line=dict(color=u_speed, colorscale='Turbo', width=5),
        hovertemplate="Speed: %{marker.color:.1f} km/h<extra></extra>"
    ))
    fig_map.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False)
    st.plotly_chart(fig_map, use_container_width=True)

    # 2. SECTOR METRICS (G61 Names)
    st.subheader("⏱️ Sector Splits")
    s_cols = st.columns(3)
    sector_results = []
    last_pct = 0
    for i, (name, pct) in enumerate(track_sectors.items()):
        start_idx = np.searchsorted(dist_pct, last_pct)
        end_idx = np.searchsorted(dist_pct, pct) - 1
        s_loss = delta[end_idx] - delta[start_idx]
        sector_results.append(f"{name}: {s_loss:.3f}s")
        with s_cols[i % 3]:
            st.metric(name, f"{s_loss:.3f}s", delta_color="inverse")
        last_pct = pct

    # 3. TELEMETRY GRAPHS
    st.subheader("🏎️ Comparative Analysis")
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.4, 0.15, 0.2, 0.2])
    
    fig.add_trace(go.Scatter(x=dist_meters, y=r_speed, name="Ref Speed", line=dict(color='blue')), row=1, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=u_speed, name="Your Speed", line=dict(color='red')), row=1, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=delta, name="Delta", fill='tozeroy', line=dict(color='gray')), row=2, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=r_brake, name="Ref Brake %", line=dict(color='blue', dash='dot')), row=3, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=u_brake, name="Your Brake %", line=dict(color='red', dash='dot')), row=3, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=r_thr, name="Ref Throttle %", line=dict(color='rgba(0,0,255,0.3)')), row=4, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=u_thr, name="Your Throttle %", line=dict(color='rgba(255,0,0,0.3)')), row=4, col=1)

    fig.update_layout(height=800, hovermode='x unified', xaxis4_title="Distance (m)")
    fig.update_yaxes(range=[-5, 105], row=3, col=1)
    fig.update_yaxes(range=[-5, 105], row=4, col=1)
    st.plotly_chart(fig, use_container_width=True)

    # 4. AI COACH
    if "GEMINI_API_KEY" in st.secrets:
        if st.button("🧠 Get AI Coaching"):
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            # Auto-picker for 2026 models
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            target = next((m for m in models if "flash" in m), models[0])
            
            prompt = f"Pro Race Engineer: Analyze these sector deltas for {car_type} at {selected_track}:\n" + \
                     "\n".join(sector_results) + "\nGive 2 sentences of tactical advice."
            
            with st.spinner("Engineer is reviewing..."):
                st.info(genai.GenerativeModel(target).generate_content(prompt).text)
