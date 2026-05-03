import streamlit as st
import google.generativeai as genai
from PIL import Image
import streamlit.components.v1 as components
from engine.setup_logic import get_vehicle_advice
from engine.coaching_tips import get_track_data
from streamlit_paste_button import paste_image_button 

# --- 1. SIKKERHED & AI KONFIGURATION ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except KeyError:
    st.error("Fejl: Kunne ikke finde 'GEMINI_API_KEY'. Tjek dine Streamlit Secrets!")
    st.stop()

# Vi bruger Lite-modellen for at få 15 RPM (Requests Per Minute) på Free Tier
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

# --- 2. UI DESIGN & LAYOUT ---
st.set_page_config(page_title="iRacing Pro Engineer", page_icon="🏎️", layout="wide")

st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏎️ iRacing Pro Engineer & Driver Coach")
st.sidebar.caption("Version 2.6 | Hobby Tier")

tab1, tab2 = st.tabs(["🛠️ Setup Advisor", "🏁 Driver Coach"])

# --- TAB 1: SETUP ADVISOR ---
with tab1:
    st.header("Setup Management")
    col_config, col_advice = st.columns([1, 1])
    
    with col_config:
        st.subheader("Aktuelt Setup")
        selected_car = st.selectbox("Vælg Bil:", ["Porsche 911 Cup (992)", "GT3 Class"])
        setup_file = st.file_uploader("Upload din Garage HTML setup-fil", type=["html"])
        
        if setup_file:
            st.success("Setup-fil indlæst!")
            setup_file.seek(0)
            raw_data = setup_file.read()
            try:
                setup_html = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                setup_html = raw_data.decode("iso-8859-1")
            
            with st.expander("Se indlæst setup"):
                components.html(setup_html, height=400, scrolling=True)

    with col_advice:
        st.subheader("Troubleshooting")
        problem = st.selectbox("Hvilket symptom har bilen?", [
            "Understyring (Indgang)", "Understyring (Mid-corner)", 
            "Overstyring (Exit)", "Bumpy / Ustabil over curbs"
        ])
        advice = get_vehicle_advice(selected_car, problem)
        st.info(f"**Ingeniørens anbefaling:**\n\n{advice}")
        st.download_button(
            label="📥 Eksporter Rettelses-guide",
            data=f"Setup rettelse for {selected_car}:\nProblem: {problem}\nLøsning: {advice}",
            file_name="setup_fix.txt"
        )

# --- TAB 2: DRIVER COACH ---
with tab2:
    st.header("Telemetri Analyse & Coaching")
    col_img, col_ai = st.columns([1, 1])
    
    with col_img:
        st.subheader("Garage 61 Data")
        telemetry_img = st.file_uploader("Upload screenshot", type=["png", "jpg", "jpeg"])
        st.write("--- ELLER ---")
        pasted_output = paste_image_button(label="📋 Paste fra Clipboard", background_color="#FF4B4B")
        
        final_img = None
        if telemetry_img:
            final_img = Image.open(telemetry_img)
        elif pasted_output.image_data is not None:
            final_img = pasted_output.image_data
            
        if final_img:
            st.image(final_img, caption="Session Telemetri", use_container_width=True)
            # Nulstil gammel analyse hvis et nyt billede er fundet
            if 'last_img_id' not in st.session_state or st.session_state.last_img_id != id(final_img):
                if 'last_analysis' in st.session_state: del st.session_state.last_analysis
                st.session_state.last_img_id = id(final_img)

    with col_ai:
        st.subheader("🤖 AI Engineer Feedback")
        prompt = "Du er en iRacing Coach. Analysér telemetrien. Sammenlign blå (mig) mod rød (reference). Hvor taber jeg tid? Giv 3 konkrete råd."

        if final_img:
            if st.button("🚀 Analysér min kørsel nu"):
                with st.spinner("AI Engineer analyserer grafer... (Husk 15 RPM limit)"):
                    try:
                        response = model.generate_content([prompt, final_img])
                        st.markdown(response.text)
                        st.session_state['last_analysis'] = response.text
                    except Exception as e:
                        if "429" in str(e):
                            st.error("⚠️ Kvote nået! Vent 30-60 sekunder før næste analyse.")
                        else:
                            st.error(f"AI fejl: {e}")
        else:
            st.info("Indlæs et billede til venstre for at starte.")

        if 'last_analysis' in st.session_state:
            st.download_button(label="📥 Download Coaching Rapport", data=st.session_state['last_analysis'], file_name="coach_report.txt")

st.sidebar.write("---")
st.sidebar.info("Husk: Du har ~15 analyser i minuttet. Tag gerne små screenshots af specifikke sving for bedre præcision.")
