import streamlit as st
import google.generativeai as genai
from PIL import Image
import streamlit.components.v1 as components
import datetime

# --- 1. SIKKERHED & AI KONFIGURATION ---
try:
    # Henter nøglen fra Streamlit Cloud Secrets
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except KeyError:
    st.error("Fejl: Kunne ikke finde 'GEMINI_API_KEY'. Tjek dine Streamlit Secrets!")
    st.stop()

# Vi bruger Gemini 3.1 Flash Lite Preview for at maksimere kvoten (15 RPM)
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

# --- 2. UI DESIGN & LAYOUT ---
st.set_page_config(page_title="iRacing Pro Engineer", page_icon="🏎️", layout="wide")

# Custom CSS for at give appen et professionelt iRacing/Garage 61 look
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: bold; }
    .stActionButton { background-color: #FF4B4B !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏎️ iRacing Pro Engineer & Driver Coach")

# --- 3. SIDEBAR: GUIDE, CONDITIONS & OM ---
with st.sidebar:
    st.header("📖 Session Management")
    
    # Sektion for vejrforhold (Vigtigt for både setup og kørsel)
    with st.expander("🌤️ Track Conditions", expanded=True):
        air_temp = st.number_input("Lufttemperatur (°C)", value=22)
        track_temp = st.number_input("Banetemperatur (°C)", value=30)
        usage = st.select_slider("Bane-gummi (Usage)", options=["Clean", "Light", "Moderate", "Heavy", "Greasy"], value="Moderate")
        weather_notes = st.text_input("Vind/Andet:", placeholder="F.eks. Kraftig sidevind...")
    
    # Samler forholdene til AI'en
    current_conditions = f"Vejr: Luft {air_temp}°C, Bane {track_temp}°C, Gummi: {usage}. Noter: {weather_notes}"

    st.write("---")
    
    with st.expander("🚀 Hurtig Guide"):
        st.write("""
        1. **Setup:** Upload Garage HTML og beskriv dit problem.
        2. **Coach:** Tag screenshot i Garage 61 og tryk 'Paste' (Ctrl+V).
        3. **Log:** Se din historik og download din session rapport i bunden.
        """)

    st.write("---")

    with st.expander("ℹ️ Om dette projekt"):
        st.markdown(f"""
        **Udviklet af Jonas Hauerbach**
        
        Dette projekt er skabt for at gøre avanceret data-analyse tilgængelig for alle iRacere, uanset om du kører på Spa, Monza eller Sebring.
        
        Appen bruger **Google Gemini 3.1** vision-teknologi til at analysere dine pedal-inputs og setup-valg i realtid.
        
        *Kører på Hobby Tier (Gratis kvote). Ved fejl, vent 30 sekunder.*
        """)
    
    st.sidebar.caption(f"© {datetime.date.today().year} | Version 2.9")

# --- 4. TABS ---
tab1, tab2 = st.tabs(["🛠️ Setup Advisor", "🏁 Driver Coach"])

# --- TAB 1: SETUP ADVISOR (Garage Engineer) ---
with tab1:
    st.header("Setup Management & Engineer Analysis")
    
    col_setup, col_engineer = st.columns([1, 1])
    
    with col_setup:
        st.subheader("Indlæs Setup Data")
        car_model = st.selectbox("Vælg Bil:", ["Porsche 911 Cup (992)", "GT3 Class", "F4", "LMP2", "GTP"])
        track_name = st.text_input("Bane:", placeholder="Hvilken bane kører du på?")
        
        setup_file = st.file_uploader("Upload din Garage HTML setup-fil", type=["html"])
        
        setup_content = ""
        if setup_file:
            raw_data = setup_file.read()
            try:
                setup_content = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                setup_content = raw_data.decode("iso-8859-1")
            st.success("✅ Setup-fil indlæst og scannet!")

    with col_engineer:
        st.subheader("🔧 AI Race Engineer")
        user_issue = st.text_area("Beskriv hvad bilen gør forkert:", 
                                   placeholder="F.eks.: Bilen føles løs i bagvognen under acceleration ud af langsomme sving...")
        
        if st.button("🔧 Analysér Setup & Forhold"):
            if setup_content and user_issue:
                with st.spinner("Ingeniøren gennemgår dine tal og baneforhold..."):
                    setup_prompt = f"""
                    Du er en professionel iRacing Engineer.
                    Bane: {track_name} | Bil: {car_model}
                    FORHOLD: {current_conditions}
                    BRUGERENS PROBLEM: {user_issue}
                    
                    HER ER SETUP DATA (HTML):
                    {setup_content[:3000]}
                    
                    Giv 3 præcise ændringer i setup'et. Forklar hvor mange 'kliks' eller hvilken retning, 
                    og hvorfor det løser problemet under de givne vejrforhold.
                    """
                    try:
                        response = model.generate_content(setup_prompt)
                        st.info(response.text)
                    except Exception as e:
                        st.error(f"Ingeniør-fejl: {e}")
            else:
                st.warning("Husk at uploade en setup-fil og beskrive dit problem.")

# --- TAB 2: DRIVER COACH (Telemetri AI) ---
with tab2:
    st.header("Telemetri Analyse & Coaching")
    
    if 'session_log' not in st.session_state:
        st.session_state.session_log = []

    col_img, col_ai = st.columns([1, 1])
    
    with col_img:
        st.subheader("Garage 61 Data")
        from streamlit_paste_button import paste_image_button
        
        # Mulighed for at paste direkte fra udklipsholder (Meget hurtigere for brugeren)
        pasted_output = paste_image_button(
            label="📋 Paste fra Clipboard (Ctrl+V)", 
            background_color="#FF4B4B",
            hover_background_color="#333"
        )
        
        tele_file = st.file_uploader("Eller upload screenshot manuelt", type=["png", "jpg", "jpeg"])
        
        final_img = None
        if tele_file:
            final_img = Image.open(tele_file)
        elif pasted_output.image_data is not None:
            final_img = pasted_output.image_data
            
        if final_img:
            st.image(final_img, caption="Session Telemetri", use_container_width=True)

    with col_ai:
        st.subheader("🤖 AI Driver Coach")
        if final_img:
            if st.button("🚀 Analysér min kørsel nu"):
                with st.spinner("Coachen analyserer dine pedaler..."):
                    coach_prompt = f"""
                    Du er en iRacing Coach. Analysér dette Garage 61 screenshot.
                    INFO: {current_conditions}
                    Fokusér på:
                    1. Bremsetryk og Trail-braking (Blå vs Rød).
                    2. Throttle application (Jævnhed og timing).
                    3. Coast time (Hvor hverken gas eller bremse bruges).
                    
                    Giv 3 konkrete øvelser til næste stint.
                    """
                    try:
                        response = model.generate_content([coach_prompt, final_img])
                        analysis_text = response.text
                        
                        # Log resultatet
                        timestamp = datetime.datetime.now().strftime("%H:%M")
                        st.session_state.session_log.append({
                            "time": timestamp,
                            "content": analysis_text
                        })
                        
                        st.markdown(analysis_text)
                    except Exception as e:
                        st.error(f"Coach fejl: {e}")
        else:
            st.info("Tag et screenshot i Garage 61 og paste det herover for at få feedback.")

    # --- SESSION LOGGER (Bund) ---
    if st.session_state.session_log:
        st.write("---")
        col_log_h, col_log_c = st.columns([3, 1])
        col_log_h.subheader("📋 Session Log")
        if col_log_c.button("🗑️ Slet Log"):
            st.session_state.session_log = []
            st.rerun()
        
        for entry in reversed(st.session_state.session_log):
            with st.expander(f"Analyse kl. {entry['time']}"):
                st.write(entry['content'])
        
        # Download samlet rapport
        full_report = "\n\n".join([f"--- KL. {e['time']} ---\n{e['content']}" for e in st.session_state.session_log])
        st.download_button("📥 Download Fuld Rapport", data=full_report, file_name="session_coaching.txt")
