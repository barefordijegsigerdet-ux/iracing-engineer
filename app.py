import streamlit as st
import google.generativeai as genai
import pandas as pd
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_main_telemetry, create_track_map

# --- KONFIGURATION ---
st.set_page_config(page_title="RaceEngineer AI", layout="wide", page_icon="🏎️")

# --- API SETUP ---
try:
    AI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=AI_API_KEY)
except Exception:
    AI_API_KEY = None

# --- SESSION STATE ---
if "hover_dist" not in st.session_state:
    st.session_state.hover_dist = 0

# --- SIDEBAR ---
st.sidebar.title("🏁 iRacing Telemetry")
u_file = st.sidebar.file_uploader("Upload din omgang (CSV)", type="csv")
r_file = st.sidebar.file_uploader("Upload reference (CSV)", type="csv")

st.sidebar.divider()
st.sidebar.subheader("🤖 AI Status")
if AI_API_KEY:
    st.sidebar.success("Gemini API Key aktiv")
else:
    st.sidebar.error("Mangler API nøgle i Secrets")

# --- AI LOGIK FUNKTIONER ---
def get_ai_coaching(user_df, ref_df):
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    # Downsampling for at undgå token-limit
    summary = user_df[['distance', 'speed', 'gear', 'throttle', 'brake', 'delta']].iloc[::30].to_csv()
    prompt = f"Du er en Race Engineer. Analyser denne telemetri: {summary}. Sammenlign med referencen. Svar kort på dansk om tidstab, gearvalg og teknik."
    response = model.generate_content(prompt)
    return response.text

def get_setup_advice(complaint, setup_html):
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    prompt = f"Du er en iRacing Setup Specialist. Problem: {complaint}. Her er setup data (HTML): {setup_html}. Giv 3 konkrete setup-ændringer baseret på tallene i HTML-koden. Svar på dansk."
    response = model.generate_content(prompt)
    return response.text

# --- HOVED LOGIK ---
if u_file and r_file:
    # 1. Data Processing (Her fixes KeyError)
    u_df, r_df = load_and_process_data(u_file, r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    # 2. Tabs
    t1, t2, t3, t4, t5 = st.tabs(["📊 Dashboard", "🗺️ Full Map", "🏎️ Tires", "🧠 AI Coach", "🔧 Garage"])

    with t1:
        col_graphs, col_map = st.columns([3, 1])
        with col_graphs:
            fig_tele = create_main_telemetry(u_df, r_df)
            event_data = st.plotly_chart(fig_tele, use_container_width=True, on_select="rerun", key="main_tele")
            
            if event_data and "selection" in event_data and event_data["selection"]["points"]:
                st.session_state.hover_dist = event_data["selection"]["points"][0]["x"]
                st.rerun()

        with col_map:
            st.subheader("Track Position")
            fig_map = create_track_map(u_df, r_df, st.session_state.hover_dist)
            st.plotly_chart(fig_map, use_container_width=True)
            
            idx = (u_df['distance'] - st.session_state.hover_dist).abs().idxmin()
            st.metric("Delta", f"{u_df.loc[idx, 'delta']:.3f} s")
            st.metric("Gear", f"{int(u_df.loc[idx, 'gear'])}")

    with t4:
        st.header("🧠 AI Driver Coach")
        if st.button("Kør Køre-Analyse"):
            with st.spinner("Analyserer teknik..."):
                st.markdown(get_ai_coaching(u_df, r_df))

    with t5:
        st.header("🔧 Garage & Setup Engineer")
        complaint = st.selectbox("Hvad er bilens problem?", ["Understyring", "Overstyring", "Ustabil under bremsning", "Bundkører/Hopper"])
        setup_file = st.file_uploader("Upload din setup HTML-fil", type=["htm", "html"])
        
        if st.button("Få Setup Fix"):
            if setup_file:
                setup_content = setup_file.read().decode("utf-8")
                with st.spinner("Analyserer mekanisk balance..."):
                    st.markdown(get_setup_advice(complaint, setup_content))
            else:
                st.warning("Upload venligst en .htm fil fra iRacing.")

else:
    st.title("RaceEngineer AI 🏎️")
    st.info("Upload CSV-filer for at starte.")
