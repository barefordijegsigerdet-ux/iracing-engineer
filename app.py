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
    
    # Initialiser session log hvis den ikke findes
    if 'session_log' not in st.session_state:
        st.session_state.session_log = []

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

    with col_ai:
        st.subheader("🤖 AI Engineer Feedback")
        prompt = "Du er en iRacing Coach. Analysér telemetrien. Sammenlign blå (mig) mod rød (reference). Hvor taber jeg tid? Giv 3 konkrete råd."

        if final_img:
            if st.button("🚀 Analysér min kørsel nu"):
                with st.spinner("AI Engineer analyserer grafer..."):
                    try:
                        response = model.generate_content([prompt, final_img])
                        analysis_text = response.text
                        
                        # Gem i session loggen med tidsstempel
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                        st.session_state.session_log.append({
                            "time": timestamp,
                            "content": analysis_text
                        })
                        
                        st.markdown(analysis_text)
                    except Exception as e:
                        st.error(f"AI fejl: {e}")
        else:
            st.info("Indlæs et billede for at starte analysen.")

    # --- SESSION LOGGER SEKTION (Nederst på Tab 2) ---
    if st.session_state.session_log:
        st.write("---")
        st.subheader("📋 Session Log")
        
        # Vis alle tidligere analyser i expandere
        for i, entry in enumerate(reversed(st.session_state.session_log)):
            with st.expander(f"Analyse kl. {entry['time']} (Forsøg {len(st.session_state.session_log) - i})"):
                st.write(entry['content'])
        
        # Download hele loggen som én fil
        full_log = "\n\n".join([f"--- KL. {e['time']} ---\n{e['content']}" for e in st.session_state.session_log])
        st.download_button(
            label="📥 Download Fuld Session Log",
            data=full_log,
            file_name=f"iracing_session_{datetime.date.today()}.txt",
            mime="text/plain"
        )
st.sidebar.write("---")
st.sidebar.info("Husk: Du har ~15 analyser i minuttet. Tag gerne små screenshots af specifikke sving for bedre præcision.")
