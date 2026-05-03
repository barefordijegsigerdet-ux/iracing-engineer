import streamlit as st
import google.generativeai as genai
from PIL import Image
import streamlit.components.v1 as components
from engine.setup_logic import get_vehicle_advice
from engine.coaching_tips import get_track_data
from streamlit_paste_button import paste_image_button # Importér den nye knap

# --- 1. SIKKERHED & AI KONFIGURATION ---
try:
    # Henter nøglen fra Streamlit Cloud Secrets eller .streamlit/secrets.toml
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except KeyError:
    st.error("Fejl: Kunne ikke finde 'GEMINI_API_KEY'. Tjek dine Streamlit Secrets!")
    st.stop()

# Vi bruger Gemini 3.1 Flash Image til visuel telemetri-analyse
model = genai.GenerativeModel('gemini-3.1-flash-image-preview')

# --- 2. UI DESIGN & LAYOUT ---
st.set_page_config(page_title="iRacing Pro Engineer", page_icon="🏎️", layout="wide")

# Custom CSS for at matche iRacing/Garage 61 viben
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏎️ iRacing Pro Engineer & Driver Coach")
st.sidebar.caption("Version 2.5 | Hostet Live")

# Opdeling i de to ønskede faner
tab1, tab2 = st.tabs(["🛠️ Setup Advisor", "🏁 Driver Coach"])

# --- TAB 1: SETUP ADVISOR (Håndtering af Garage Setup HTML) ---
# --- TAB 1: SETUP ADVISOR ---
with tab1:
    st.header("Setup Management")
    
    col_config, col_advice = st.columns([1, 1])
    
    with col_config:
        st.subheader("Aktuelt Setup")
        selected_car = st.selectbox("Vælg Bil:", ["Porsche 911 Cup (992)", "GT3 Class"])
        
        # Upload af HTML-filen
        setup_file = st.file_uploader("Upload din Garage HTML setup-fil", type=["html"])
        
        if setup_file:
            st.success("Setup-fil indlæst!")
            
            # Reset fil-markøren og læs rå data
            setup_file.seek(0)
            raw_data = setup_file.read()
            
            try:
                # Prøv standard UTF-8 først
                setup_html = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                # Hvis det fejler (iRacing HTML), brug Latin-1
                setup_html = raw_data.decode("iso-8859-1")
            
            with st.expander("Se indlæst setup"):
                st.components.v1.html(setup_html, height=400, scrolling=True)

    with col_advice:
        st.subheader("Troubleshooting")
        # Resten af din troubleshooting kode her...
        problem = st.selectbox("Hvilket symptom har bilen?", [
            "Understyring (Indgang)", 
            "Understyring (Mid-corner)", 
            "Overstyring (Exit)", 
            "Bumpy / Ustabil over curbs"
        ])
        
        # Henter råd fra din engine/setup_logic.py
        advice = get_vehicle_advice(selected_car, problem)
        st.info(f"**Ingeniørens anbefaling:**\n\n{advice}")
        
        # Eksport-mulighed for setup-rettelser
        st.download_button(
            label="📥 Eksporter Rettelses-guide",
            data=f"Setup rettelse for {selected_car}:\nProblem: {problem}\nLøsning: {advice}",
            file_name="setup_fix.txt"
        )

# --- TAB 2: DRIVER COACH (Telemetri AI Analyse) ---
with tab2:
    st.header("Telemetri Analyse & Coaching")
    
    col_img, col_ai = st.columns([1, 1])
    
    with col_img:
        st.subheader("Garage 61 Data")
        # Mulighed 1: Traditionel upload
        telemetry_img = st.file_uploader("Upload screenshot", type=["png", "jpg", "jpeg"])
        
        st.write("ELLER")
        
        # Mulighed 2: Paste-knap
        pasted_output = paste_image_button(
            label="📋 Paste fra Clipboard",
            background_color="#FF4B4B",
            hover_background_color="#333",
            errors="ignore"
        )
        
        # Logik til at vælge billede
        final_img = None
        if telemetry_img:
            final_img = Image.open(telemetry_img)
        elif pasted_output.image_data is not None:
            final_img = pasted_output.image_data
            
        if final_img:
            st.image(final_img, caption="Session Telemetri", use_container_width=True)

    with col_ai:
        st.subheader("🤖 AI Engineer Feedback")
        
        # VIGTIGT: Definer prompten HER så den er tilgængelig for modellen
        prompt = "Analysér dette Garage 61 telemetri screenshot. Sammenlign den blå linje med den røde. Hvor taber jeg tid, og hvad kan jeg gøre ved min køreteknik?"

        if final_img and st.button("🚀 Analysér min kørsel nu"):
            with st.spinner("AI'en kigger på dine grafer..."):
                try:
                    # Nu er både 'prompt' og 'final_img' defineret
                    response = model.generate_content([prompt, final_img])
                    st.markdown(response.text)
                    st.session_state['last_analysis'] = response.text
                except Exception as e:
                    st.error(f"AI fejl: {e}")
        
        # Eksport af AI analysen
        if 'last_analysis' in st.session_state:
            st.download_button(
                label="📥 Download Coaching Rapport",
                data=st.session_state['last_analysis'],
                file_name="driver_coach_report.txt",
                mime="text/plain"
            )

# --- SIDEBAR INFO ---
st.sidebar.write("---")
st.sidebar.info("""
**Tip:** 
1. Upload dit setup på første fane.
2. Tag et screenshot af din dårligste sektor i Garage 61.
3. Upload det på fane 2 for at få AI feedback.
""")
