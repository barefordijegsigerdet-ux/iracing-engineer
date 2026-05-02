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
        st.write("Få hjælp til dit bil-setup baseret på din kørsel og HTML-eksport.")
        
        complaint = st.selectbox(
            "Hvad driller bilen?", 
            ["Understyring (Mid-corner)", "Overstyring (Exit)", "Ustabil under bremsning", "For stiv over curbs"]
        )
        
        setup_text = st.text_area("Indsæt Setup HTML her (f.eks. indholdet af nurburgring_combined.htm):", height=250)
        
        if st.button("Analyser Setup"):
            if setup_text:
                with st.spinner("Beregner mekanisk balance..."):
                    advice = get_setup_advice(complaint, setup_text)
                    st.markdown("### Setup Anbefalinger")
                    st.write(advice)
            else:
                st.warning("Indsæt venligst setup-data først.")

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
