import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

st.set_page_config(page_title="Universal Race Engineer", layout="wide")

# --- TRACK DATABASE ---
TRACK_DATABASE = {
    "Zandvoort": 4259, "Spa-Francorchamps": 7004, "Red Bull Ring": 4318,
    "Monza": 5793, "Suzuka": 5807, "Laguna Seca": 3602,
    "Mount Panorama": 6213, "Nordschleife": 20832, "Daytona (Road)": 5730
}

# --- SIDEBAR ---
st.sidebar.header("🔧 Global Settings")
car_type = st.sidebar.selectbox("Car Type", ["Porsche 911 Cup (992.2)", "GT3 Class", "Formula 4", "LMP2", "Other"])
selected_track = st.sidebar.selectbox("Select Track", list(TRACK_DATABASE.keys()) + ["Custom"])
track_length = st.sidebar.number_input("Track Length (m)", value=TRACK_DATABASE.get(selected_track, 4259))

st.title("🏁 Universal Race Engineer")

# --- FILE UPLOADER SECTION ---
col_ref, col_user = st.columns(2)
with col_ref:
    st.subheader("🟦 Reference Lap")
    ref_file = st.file_uploader("Upload Pro CSV", type=['csv'], key="ref")
with col_user:
    st.subheader("🟥 Your Lap")
    user_file = st.file_uploader("Upload Your CSV", type=['csv'], key="user")

st.divider()
session_file = st.file_uploader("📋 Session Analysis", type=['csv'], key="session")

# --- PART 1: RACE SESSION ANALYSIS ---
if session_file:
    df_session = pd.read_csv(session_file)
    df_session.columns = df_session.columns.str.strip()
    if 'Lap time' in df_session.columns:
        st.header("📊 Race Session Report")
        c1, c2, c3 = st.columns(3)
        c1.metric("Best Lap", f"{df_session['Lap time'].min():.3f}s")
        c2.metric("Avg Fuel/Lap", f"{df_session['Fuel used'].mean():.3f} L")
        c3.metric("Total Laps", len(df_session))
        
        fig_lap = go.Figure(go.Scatter(x=df_session['Lap'], y=df_session['Lap time'], mode='lines+markers', line=dict(color='gold')))
        fig_lap.update_layout(title="Lap Consistency", xaxis_title="Lap Number", yaxis_title="Time (s)")
        st.plotly_chart(fig_lap, use_container_width=True)

# --- PART 2: TELEMETRY COMPARISON ---
if ref_file and user_file:
    df_r = pd.read_csv(ref_file)
    df_u = pd.read_csv(user_file)
    
    df_r.columns = df_r.columns.str.strip()
    df_u.columns = df_u.columns.str.strip()

    # Sort and remove duplicates to prevent interpolation crashes
    df_r = df_r.sort_values('LapDistPct').drop_duplicates('LapDistPct')
    df_u = df_u.sort_values('LapDistPct').drop_duplicates('LapDistPct')

    st.header("🏎️ Comparative Analysis")
    
    # Calculate incremental time for each driver separately
    df_u['Dist_Diff'] = df_u['LapDistPct'].diff().fillna(0) * track_length
    df_r['Dist_Diff'] = df_r['LapDistPct'].diff().fillna(0) * track_length

    u_time_seg = df_u['Dist_Diff'] / (df_u['Speed'] / 3.6).replace(0, 0.1)
    r_time_seg = df_r['Dist_Diff'] / (df_r['Speed'] / 3.6).replace(0, 0.1)

    u_total_time = np.cumsum(u_time_seg)
    r_total_time = np.cumsum(r_time_seg)

    # Standardize to 5,000 points in METERS
    dist_pct = np.linspace(0, 1, 5000)
    dist_meters = dist_pct * track_length
    
    # SAFE INTERPOLATION: Always compare user_dist to user_data, ref_dist to ref_data
    u_speed = np.interp(dist_pct, df_u['LapDistPct'], df_u['Speed'] * 3.6)
    r_speed = np.interp(dist_pct, df_r['LapDistPct'], df_r['Speed'] * 3.6)
    u_brake = np.interp(dist_pct, df_u['LapDistPct'], df_u['Brake'])
    r_brake = np.interp(dist_pct, df_r['LapDistPct'], df_r['Brake'])
    u_thr = np.interp(dist_pct, df_u['LapDistPct'], df_u['Throttle'])
    r_thr = np.interp(dist_pct, df_r['LapDistPct'], df_r['Throttle'])
    
    # This was the bug fix line:
    u_time_i = np.interp(dist_pct, df_u['LapDistPct'], u_total_time)
    r_time_i = np.interp(dist_pct, df_r['LapDistPct'], r_total_time)
    delta = u_time_i - r_time_i

    # Plotting
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.4, 0.15, 0.2, 0.2])
    fig.add_trace(go.Scatter(x=dist_meters, y=r_speed, name="Ref Speed", line=dict(color='blue')), row=1, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=u_speed, name="Your Speed", line=dict(color='red')), row=1, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=delta, name="Time Delta", fill='tozeroy', line=dict(color='gray')), row=2, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=r_brake, name="Ref Brake", line=dict(color='blue', dash='dot')), row=3, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=u_brake, name="Your Brake", line=dict(color='red', dash='dot')), row=3, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=r_thr, name="Ref Throttle", line=dict(color='rgba(0,0,255,0.2)')), row=4, col=1)
    fig.add_trace(go.Scatter(x=dist_meters, y=u_thr, name="Your Throttle", line=dict(color='rgba(255,0,0,0.2)')), row=4, col=1)

    fig.update_layout(height=900, hovermode='x unified', xaxis4_title="Distance (Meters)")
    st.plotly_chart(fig, use_container_width=True)

    # --- AI COACHING ---
    st.divider()
    st.header("🧠 AI Coach Feedback")
    if "GEMINI_API_KEY" in st.secrets:
        if st.button("Get AI Analysis"):
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                # Modern model picker for 2026
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target = next((m for m in models if "3.1-flash" in m or "2.5-flash" in m), models[0])
                
                model = genai.GenerativeModel(target)
                max_loss = delta.max()
                loss_loc = dist_meters[np.argmax(delta)] 
                
                prompt = f"Professional race engineer: Driver losing {max_loss:.3f}s at {loss_loc:.0f} meters into the lap in {car_type} at {selected_track}. Provide 2 sentences of technical advice."
                
                with st.spinner(f"Engineer is analyzing..."):
                    st.info(model.generate_content(prompt).text)
            except Exception as e:
                st.error(f"AI System Error: {e}")
