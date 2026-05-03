import streamlit as st
import google.generativeai as genai
from PIL import Image
import streamlit.components.v1 as components
from engine.setup_logic import get_vehicle_advice
from engine.coaching_tips import get_track_data

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
with tab1:
    st.header("Setup Management")
    
    col_config, col_advice = st.columns([1, 1])
    
    with col_config:
        st.subheader("Aktuelt Setup")
        selected_car = st.selectbox("Vælg Bil:", ["Porsche 911 Cup (992)", "GT3 Class"])
        
        # Upload af HTML-filen med dit setup fra iRacing/Garage
        setup_file = st.file_uploader("Upload din Garage HTML setup-fil", type=["html"])
        
       if setup_file:
            st.success("Setup-fil indlæst!")
            
            # Vi prøver at dekode filen med ISO-8859-1, som er standard for mange HTML-exports
            try:
                raw_data = setup_file.read()
                setup_html = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                # Hvis UTF-8 fejler, bruger vi Latin-1 (ISO-8859-1)
                setup_html = raw_data.decode("iso-8859-1")
            
            with st.expander("Se indlæst setup"):
                st.components.v1.html(setup_html, height=400, scrolling=True)

    with col_advice:
        st.subheader("Troubleshooting")
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
        # Her uploader du dine screenshots som f.eks. image_7aa89e.png
        telemetry_img = st.file_uploader("Upload screenshot af din telemetri (Speed/Throttle)", type=["png", "jpg", "jpeg"])
        
        if telemetry_img:
            st.image(telemetry_img, caption="Session Telemetri", use_container_width=True)
        else:
            st.info("Upload et billede (f.eks. din kørsel vs. referencen) for at starte analysen.")

    with col_ai:
        st.subheader("🤖 AI Engineer Feedback")
        # AI kører KUN når brugeren klikker på knappen
        if telemetry_img and st.button("🚀 Analysér min kørsel nu"):
            img = Image.open(telemetry_img)
            
            # Skræddersyet prompt til racing telemetri
            prompt = f"""
            Du er en professionel Driver Coach. Analysér dette Garage 61 screenshot for en {selected_car}.
            Kig på den blå linje (brugeren) vs. den røde (referencen). 
            Identificér præcis hvor der tabes tid (Braking point, Apex speed eller Exit).
            Giv 3 konkrete tips til at forbedre omgangstiden.
            """
            
            with st.spinner("AI'en tygger på dine data..."):
                try:
                    response = model.generate_content([prompt, img])
                    st.markdown(response.text)
                    
                    # Gem resultatet i session_state til eksport
                    st.session_state['last_analysis'] = response.text
                except Exception as e:
                    st.error(f"Der opstod en fejl: {e}")
        
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
