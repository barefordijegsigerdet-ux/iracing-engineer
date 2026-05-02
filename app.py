import streamlit as st
import google.generativeai as genai
import pandas as pd
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_main_telemetry, create_track_map

# Konfiguration af siden
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
st.sidebar.subheader("🤖 AI Coach Status")
if AI_API_KEY:
    st.sidebar.success("Gemini API Key indlæst fra Secrets")
else:
    st.sidebar.error("Mangler GEMINI_API_KEY i Secrets")

# --- AI COACH LOGIK ---
def get_ai_coaching(user_df, ref_df):
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    
    # Vi reducerer data-mængden (downsampling) for at holde os inden for AI grænser
    # Vi inkluderer GEAR nu
    summary = user_df[['distance', 'speed', 'gear', 'throttle', 'brake', 'delta']].iloc[::30].to_csv()
    
    prompt = f"""
    Du er en professionel Race Engineer. Analyser denne iRacing telemetri.
    Sammenlign køreren (Dig) med referencen.
    
    Fokusér på:
    1. Tidstab: Hvor tabes der mest tid?
    2. Gear: Er der steder hvor gearvalget adskiller sig markant?
    3. Teknik: Bremsespots og throttle-pedal kontrol.
    
    Hold svaret kort, konstruktivt og på dansk.
    
    Data:
    {summary}
    """
    response = model.generate_content(prompt)
    return response.text

# --- HOVED INDHOLD ---
if u_file and r_file:
    # Data Processing
    u_df, r_df = load_and_process_data(u_file, r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    # Tabs
   t1, t2, t3, t4, t5 = st.tabs(["📊 Dashboard", "🗺️ Full Map", "🏎️ Tires", "🧠 AI Coach", "🔧 Garage"])
    with t1:
        col_graphs, col_map = st.columns([3, 1])

        with t5:
    st.header("🔧 Garage & Setup Engineer")
    st.write("Indsæt dit setup (HTML tekst) eller beskriv bilens opførsel.")
    
    complaint = st.text_area("Hvad driller? (f.eks. 'Bilen er løs ved exit' eller 'For meget understyring i T1')")
    setup_data = st.text_area("Indsæt Setup HTML/Tekst her (valgfrit)")
    
    if st.button("Få Setup Tips"):
        if AI_API_KEY:
            with st.spinner("Analyserer setup-ændringer..."):
                # Kald til AI med fokus på mekanisk balance
                prompt = f"Jeg kører i iRacing. Mit problem er: {complaint}. Mit setup er: {setup_data}. Hvad skal jeg ændre i setuppet (f.eks. Springs, ARB, Wing) for at fikse det?"
                # (Genbrug din AI-logik her)
                feedback = model.generate_content(prompt)
                st.markdown(feedback.text)

        with col_graphs:
            # Lav hovedtelemetri med Gear-graf indbygget
            fig_tele = create_main_telemetry(u_df, r_df)
            
            # Plotly chart med on_select synkronisering
            event_data = st.plotly_chart(
                fig_tele, 
                use_container_width=True, 
                on_select="rerun", 
                key="main_tele"
            )
            
            # Opdater global position ved klik/valg
            if event_data and "selection" in event_data and event_data["selection"]["points"]:
                new_dist = event_data["selection"]["points"][0]["x"]
                if new_dist != st.session_state.hover_dist:
                    st.session_state.hover_dist = new_dist
                    st.rerun()

        with col_map:
            st.subheader("Track Position")
            # Tegn kortet med den opdaterede hover_dist
            fig_map = create_track_map(u_df, r_df, st.session_state.hover_dist)
            st.plotly_chart(fig_map, use_container_width=True, key="track_map")
            
            # Live Metrics i højre side (som i image_7b7e98.png)
            idx = (u_df['distance'] - st.session_state.hover_dist).abs().idxmin()
            st.metric("Distance", f"{st.session_state.hover_dist:.0f} m")
            st.metric("Delta", f"{u_df.loc[idx, 'delta']:.3f} s")
            st.metric("Gear", f"{int(u_df.loc[idx, 'gear'])}")

    with t4:
        st.header("🧠 AI Driver Coach")
        if not AI_API_KEY:
            st.warning("Indtast din API-nøgle i Streamlit Secrets for at aktivere denne fane.")
        else:
            if st.button("Generér AI Analyse"):
                with st.spinner("AI'en tygger på din telemetri..."):
                    try:
                        feedback = get_ai_coaching(u_df, r_df)
                        st.markdown("### Coach Feedback")
                        st.write(feedback)
                    except Exception as e:
                        st.error(f"Der skete en fejl i AI-analysen: {e}")

else:
    st.title("RaceEngineer AI")
    st.info("👋 Upload to CSV-filer i sidebaren for at starte din analyse.")
    st.markdown("""
    ### Sådan gør du:
    1. Upload din egen hurtigste omgang.
    2. Upload en reference-omgang (f.eks. fra en hurtigere ven eller Garage 61).
    3. Brug Dashboardet til at se, hvor du taber tid.
    4. Spørg AI Coachen om tips til at køre hurtigere.
    """)
