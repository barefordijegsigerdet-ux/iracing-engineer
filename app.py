import streamlit as st
import google.generativeai as genai
import pandas as pd
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_main_telemetry, create_track_map

# --- KONFIGURATION ---
st.set_page_config(page_title="RaceEngineer AI", layout="wide", page_icon="🏎️")

# --- API SETUP (STREAMLIT SECRETS) ---
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
    """Analyserer kørselsteknik baseret på telemetri-data."""
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    # Downsampling for at overholde token-limits
    summary = user_df[['distance', 'speed', 'gear', 'throttle', 'brake', 'delta']].iloc[::30].to_csv()
    
    prompt = f"""
    Du er en professionel Race Engineer. Analyser denne telemetri:
    {summary}
    Sammenlign brugeren med referencen. Svar kort og præcist på dansk om:
    1. Hvor tabes der tid?
    2. Er gearvalget optimalt?
    3. Specifikke råd til bremsning og throttle.
    """
    response = model.generate_content(prompt)
    return response.text

def get_setup_advice(complaint, setup_html):
    """Analyserer bilens setup (f.eks. nurburgring_combined.htm) og giver fix."""
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    prompt = f"""
    Du er en Setup Specialist. Brugeren kører Porsche 992 GT3 R.
    Problem: {complaint}
    Setup Data (HTML): {setup_html}
    
    Giv 3 konkrete ændringer til setuppet (f.eks. ARB, fjedre eller vinge) for at løse problemet. 
    Forklar hvorfor baseret på værdierne i HTML-filen. Svar på dansk.
    """
    response = model.generate_content(prompt)
    return response.text

# --- HOVED LOGIK ---
if u_file and r_file:
    # 1. Data Processing
    u_df, r_df = load_and_process_data(u_file, r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    # 2. Opret Tabs
    t1, t2, t3, t4, t5 = st.tabs(["📊 Dashboard", "🗺️ Full Map", "🏎️ Tires", "🧠 AI Coach", "🔧 Garage"])

    # --- TAB 1: DASHBOARD ---
    with t1:
        col_graphs, col_map = st.columns([3, 1])

        with col_graphs:
            fig_tele = create_main_telemetry(u_df, r_df)
            event_data = st.plotly_chart(fig_tele, use_container_width=True, on_select="rerun", key="main_tele")
            
            # Synkronisering ved klik på graf
            if event_data and "selection" in event_data and event_data["selection"]["points"]:
                new_dist = event_data["selection"]["points"][0]["x"]
                if new_dist != st.session_state.hover_dist:
                    st.session_state.hover_dist = new_dist
                    st.rerun()

        with col_map:
            st.subheader("Track Position")
            fig_map = create_track_map(u_df, r_df, st.session_state.hover_dist)
            st.plotly_chart(fig_map, use_container_width=True, key="map")
            
            # Live Metrics
            idx = (u_df['distance'] - st.session_state.hover_dist).abs().idxmin()
            st.metric("Distance", f"{st.session_state.hover_dist:.0f} m")
            st.metric("Delta", f"{u_df.loc[idx, 'delta']:.3f} s")
            st.metric("Gear", f"{int(u_df.loc[idx, 'gear'])}")

    # --- TAB 4: AI COACH ---
    with t4:
        st.header("🧠 AI Driver Coach")
        if st.button("Kør Køre-Analyse"):
            with st.spinner("Gemini analyserer din omgang..."):
                try:
                    feedback = get_ai_coaching(u_df, r_df)
                    st.markdown(feedback)
                except Exception as e:
                    st.error(f"Fejl: {e}")

    # --- TAB 5: GARAGE ---
    with t5:
        st.header("🔧 Garage & Setup Engineer")
        st.write("Få hjælp til dit bil-setup. Upload din iRacing HTML-eksport eller beskriv problemet.")
        
        col_setup_input, col_setup_info = st.columns([2, 1])
        
        with col_setup_input:
            complaint = st.selectbox(
                "Hvad driller bilen mest?", 
                [
                    "Understyring (Mid-corner/Exit)", 
                    "Overstyring (Entry/Mid)", 
                    "Overstyring (Power-on exit)",
                    "Ustabil under bremsning", 
                    "Bilen er for stiv over curbs/bumps",
                    "Bilen 'bundkører' (bottoming out)"
                ]
            )
            
            # Dynamisk upload af setup-fil
            setup_file = st.file_uploader("Upload setup (.htm)", type=["htm", "html"])
            
            # Backup: Manuel tekst-indtastning
            setup_text_manual = st.text_area("Eller indsæt setup-tekst her:", height=150, placeholder="<html>...")

        with col_setup_info:
            st.info("""
            **Sådan gør du:**
            1. I iRacing Garage, klik på 'Share' eller 'Export'.
            2. Gem filen som .htm.
            3. Upload den her for at lade AI'en analysere dine fjedre, ARB og aero.
            """)

        if st.button("Analyser Setup & Giv Fix"):
            setup_to_analyze = ""
            
            # Prioritér den uploadede fil
            if setup_file is not None:
                setup_to_analyze = setup_file.read().decode("utf-8")
            elif setup_text_manual:
                setup_to_analyze = setup_text_manual
            
            if setup_to_analyze:
                with st.spinner("Læser setup-værdier og beregner løsning..."):
                    try:
                        # Vi sender dataen til AI'en
                        advice = get_setup_advice(complaint, setup_to_analyze)
                        st.markdown("---")
                        st.markdown("### 🛠️ Ingeniørens Anbefalinger")
                        st.write(advice)
                    except Exception as e:
                        st.error(f"Kunne ikke analysere setup: {e}")
            else:
                st.warning("Upload venligst en setup-fil eller indsæt tekst for at få hjælp.")

else:
    # Velkomstskærm hvis ingen filer er uploadet
    st.title("RaceEngineer AI 🏎️")
    st.info("👋 Upload dine iRacing CSV-filer i sidebaren for at starte analysen.")
    st.markdown("""
    ### Funktioner:
    *   **Dashboard:** Sammenlign Speed, Gear og Delta synkroniseret med banekortet.
    *   **AI Coach:** Få direkte feedback på din teknik via Gemini 3.1 Flash.
    *   **Garage:** Indsæt din setup-fil (HTML) og få konkrete forslag til ændringer.
    """)
