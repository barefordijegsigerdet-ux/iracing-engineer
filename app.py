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

if selected_track == "Custom":
    track_length = st.sidebar.number_input("Track Length (meters)", value=4000)
else:
    track_length = TRACK_DATABASE[selected_track]

st.sidebar.info(f"Track Length: {track_length}m")

# --- FILE UPLOADER ---
st.title("🏁 Universal Race Engineer")
st.markdown("Upload **Telemetry CSVs** for lap comparison or **Session Exports** for race strategy.")
uploaded_files = st.file_uploader("Drop Garage 61 CSVs here", accept_multiple_files=True)

if uploaded_files:
    telemetry_files = []
    summary_files = []

    for file in uploaded_files:
        df_temp = pd.read_csv(file)
        if 'Speed' in df_temp.columns:
            telemetry_files.append((file.name, df_temp))
        elif 'Lap time' in df_temp.columns:
            summary_files.append((file.name, df_temp))

    # --- PART 1: RACE SESSION ANALYSIS ---
    if summary_files:
        st.divider()
        st.header("📊 Race Session Analysis")
        for name, df in summary_files:
            with st.expander(f"Session Report: {name}", expanded=True):
                col1, col2, col3 = st.columns(3)
                best_lap = df['Lap time'].min()
                avg_fuel = df['Fuel used'].mean()
                
                col1.metric("Best Lap", f"{best_lap:.3f}s")
                col2.metric("Avg Fuel/Lap", f"{avg_fuel:.3f} L")
                col3.metric("Total Laps", len(df))

                fig_lap = go.Figure()
                fig_lap.add_trace(go.Scatter(x=df['Lap'], y=df['Lap time'], mode='lines+markers', name='Lap Time', line=dict(color='gold')))
                fig_lap.update_layout(title="Lap Consistency", xaxis_title="Lap Number", yaxis_title="Time (s)")
                st.plotly_chart(fig_lap, use_container_width=True)

    # --- PART 2: DETAILED TELEMETRY COMPARISON ---
    if len(telemetry_files) >= 2:
        st.divider()
        st.header("🏎️ Driving Line & Input Comparison")
        
        f1_name, df_u = telemetry_files[0]
        f2_name, df_r = telemetry_files[1]
        
        u_driver = f1_name.split(" - ")[1] if " - " in f1_name else "User"
        r_driver = f2_name.split(" - ")[1] if " - " in f2_name else "Reference"

        # Interpolation Logic
        dist_common = np.linspace(0, 1, 5000)
        u_speed = np.interp(dist_common, df_u['LapDistPct'], df_u['Speed'] * 3.6)
        r_speed = np.interp(dist_common, df_r['LapDistPct'], df_r['Speed'] * 3.6)
        u_brake = np.interp(dist_common, df_u['LapDistPct'], df_u['Brake'])
        r_brake = np.interp(dist_common, df_r['LapDistPct'], df_r['Brake'])
        u_thr = np.interp(dist_common, df_u['LapDistPct'], df_u['Throttle'])
        r_thr = np.interp(dist_common, df_r['LapDistPct'], df_r['Throttle'])
        
        dx = track_length / 5000 
        u_time = np.cumsum(dx / np.maximum(u_speed/3.6, 0.1))
        r_time = np.cumsum(dx / np.maximum(r_speed/3.6, 0.1))
        delta = u_time - r_time

        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.4, 0.15, 0.2, 0.2])
        fig.add_trace(go.Scatter(x=dist_common, y=r_speed, name=f"{r_driver} Speed", line=dict(color='blue')), row=1, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=u_speed, name=f"{u_driver} Speed", line=dict(color='red')), row=1, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=delta, name="Time Delta", fill='tozeroy', line=dict(color='gray')), row=2, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=r_brake, name=f"{r_driver} Brake", line=dict(color='blue', dash='dot')), row=3, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=u_brake, name=f"{u_driver} Brake", line=dict(color='red', dash='dot')), row=3, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=r_thr, name=f"{r_driver} Throttle", line=dict(color='rgba(0,0,255,0.2)')), row=4, col=1)
        fig.add_trace(go.Scatter(x=dist_common, y=u_thr, name=f"{u_driver} Throttle", line=dict(color='rgba(255,0,0,0.2)')), row=4, col=1)

        fig.update_layout(height=1000, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

# --- AI COACHING SECTION ---
        st.divider()
        st.header("🧠 AI Coach Feedback")
        
        if "GEMINI_API_KEY" in st.secrets:
            # We use a button so the AI doesn't fire on every single page refresh
            if st.button("Analyze my driving with AI"):
                try:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    
                    # Target a specific reliable model for your region
                    # gemini-1.5-flash is the most 'generous' with free limits
                    model_name = 'gemini-1.5-flash'
                    
                    max_loss_val = delta.max()
                    loss_pct = dist_common[np.argmax(delta)] * 100
                    
                    prompt = f"""
                    Act as a professional race engineer. Compare Driver {u_driver} to Reference {r_driver}.
                    Car: {car_type} at {selected_track}.
                    Data: Max time loss is {max_loss_val:.3f}s at {loss_pct:.1f}% of the lap.
                    Provide 1-2 technical sentences on how to fix this loss.
                    """
                    
                    with st.spinner(f"Engineer is reviewing your telemetry..."):
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(prompt)
                        st.info(response.text)
                        
                except Exception as e:
                    if "429" in str(e):
                        st.error("Too many requests! Wait 60 seconds and try again. The free tier has a speed limit.")
                    else:
                        st.error(f"AI System Error: {e}")
        else:
            st.warning("Missing API Key in Secrets.")
