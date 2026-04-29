import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

st.set_page_config(page_title="Universal Race Engineer", layout="wide")

# --- TRACK DATABASE ---
TRACK_DATABASE = {
    "Zandvoort": 4259,
    "Spa-Francorchamps": 7004,
    "Red Bull Ring": 4318,
    "Monza": 5793,
    "Suzuka": 5807,
    "Laguna Seca": 3602,
    "Mount Panorama": 6213,
    "Nordschleife": 20832,
    "Daytona (Road)": 5730
}

# --- SIDEBAR ---
st.sidebar.header("🔧 Global Settings")
car_type = st.sidebar.selectbox("Car Type", ["Porsche 911 Cup (992.2)", "GT3 Class", "Formula 4", "LMP2", "Other"])
selected_track = st.sidebar.selectbox("Select Track", list(TRACK_DATABASE.keys()) + ["Custom"])
track_length = st.sidebar.number_input("Track Length (m)", value=TRACK_DATABASE.get(selected_track, 4000))

st.title("🏁 Universal Race Engineer")

# --- FILE UPLOADER SECTION ---
col_ref, col_user = st.columns(2)

with col_ref:
    st.subheader("🟦 Reference Lap")
    ref_file = st.file_uploader("Upload Pro/Reference CSV", type=['csv'], key="ref")

with col_user:
    st.subheader("🟥 Your Lap")
    user_file = st.file_uploader("Upload Your Telemetry CSV", type=['csv'], key="user")

st.divider()
st.subheader("📋 Session Analysis")
session_file = st.file_uploader("Upload Session/Race Export CSV", type=['csv'], key="session")

# --- PART 1: RACE SESSION ANALYSIS ---
if session_file:
    df_session = pd.read_csv(session_file)
    if 'Lap time' in df_session.columns:
        st.header("📊 Race Session Report")
        col1, col2, col3 = st.columns(3)
        best_lap = df_session['Lap time'].min()
        avg_fuel = df_session['Fuel used'].mean()
        
        col1.metric("Best Lap", f"{best_lap:.3f}s")
        col2.metric("Avg Fuel/Lap", f"{avg_fuel:.3f} L")
        col3.metric("Total Laps", len(df_session))

        fig_lap = go.Figure()
        fig_lap.add_trace(go.Scatter(x=df_session['Lap'], y=df_session['Lap time'], mode='lines+markers', name='Lap Time', line=dict(color='gold')))
        fig_lap.update_layout(title="Lap Consistency", xaxis_title="Lap Number", yaxis_title="Time (s)")
        st.plotly_chart(fig_lap, use_container_width=True)

# --- PART 2: TELEMETRY COMPARISON ---
if ref_file and user_file:
    df_r = pd.read_csv(ref_file)
    df_u = pd.read_csv(user_file)
    
    st.header("🏎️ Comparative Analysis")
    
    # Smooth Delta Math
    df_u['Dist_Diff'] = df_u['LapDistPct'].diff() * track_length
    df_r['Dist_Diff'] = df_r['LapDistPct'].diff() * track_length

    u_time_segments = df_u['Dist_Diff'] / (df_u['Speed'] / 3.6).replace(0, 0.1)
    r_time_segments = df_r['Dist_Diff'] / (df_r['Speed'] / 3.6).replace(0, 0.1)

    u_total_time = np.cumsum(u_time_segments.fillna(0))
    r_total_time = np.cumsum(r_time_segments.fillna(0))

    dist_common = np.linspace(0, 1, 5000)
    u_speed = np.interp(dist_common, df_u['LapDistPct'], df_u['Speed'] * 3.6)
    r_speed = np.interp(dist_common, df_r['LapDistPct'], df_r['Speed'] * 3.6)
    u_brake = np.interp(dist_common, df_u['LapDistPct'], df_u['Brake'])
    r_brake = np.interp(dist_common, df_r['LapDistPct'], df_r['Brake'])
    u_thr = np.interp(dist_common, df_u['LapDistPct'], df_u['Throttle'])
    r_thr = np.interp(dist_common, df_r['LapDistPct'], df_r['Throttle'])
    
    u_time_interp = np.interp(dist_common, df_u['LapDistPct'], u_total_time)
    r_time_interp = np.interp(dist_common, df_r['LapDistPct'], r_total_time)
    delta = u_time_interp - r_time_interp

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.4, 0.15, 0.2, 0.2])
    fig.add_trace(go.Scatter(x=dist_common, y=r_speed, name="Reference Speed", line=dict(color='blue')), row=1, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=u_speed, name="Your Speed", line=dict(color='red')), row=1, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=delta, name="Time Delta", fill='tozeroy', line=dict(color='gray')), row=2, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=r_brake, name="Ref Brake", line=dict(color='blue', dash='dot')), row=3, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=u_brake, name="Your Brake", line=dict(color='red', dash='dot')), row=3, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=r_thr, name="Ref Throttle", line=dict(color='rgba(0,0,255,0.2)')), row=4, col=1)
    fig.add_trace(go.Scatter(x=dist_common, y=u_thr, name="Your Throttle", line=dict(color='rgba(255,0,0,0.2)')), row=4, col=1)

    fig.update_layout(height=900, hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)

    # --- AI COACHING ---
    st.divider()
    if "GEMINI_API_KEY" in st.secrets:
        if st.button("🧠 Get AI Coaching Tip"):
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_model = next((m for m in available_models if "flash" in m), available_models[0])
                
                max_loss_val = delta.max()
                loss_pct = dist_common[np.argmax(delta)] * 100
                
                prompt = f"Professional race engineer tip: Driver losing {max_loss_val:.3f}s at {loss_pct:.1f}% lap in {car_type} at {selected_track}. 2 technical sentences."
                
                with st.spinner("Reviewing data..."):
                    model = genai.GenerativeModel(target_model)
                    response = model.generate_content(prompt)
                    st.info(response.text)
            except Exception as e:
                st.error(f"AI Error: {e}")
