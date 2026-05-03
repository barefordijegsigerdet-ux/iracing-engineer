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
    st.header("Setup Management & Engineer Analysis")
    
    col_config, col_advice = st.columns([1, 1])
    
    with col_config:
        st.subheader("Konfiguration")
        selected_car = st.selectbox("Bil:", ["Porsche 911 Cup (992)", "GT3 Class", "F4"])
        selected_track = st.text_input("Bane (f.eks. Nürburgring):", "Nürburgring Nordschleife")
        
        setup_file = st.file_uploader("Upload Garage HTML setup", type=["html"], key="setup_uploader")
        
        setup_text_content = ""
        if setup_file:
            # Læs HTML ind som tekst så AI'en kan forstå tallene
            setup_bytes = setup_file.read()
            try:
                setup_text_content = setup_bytes.decode("utf-8")
            except:
                setup_text_content = setup_bytes.decode("iso-8859-1")
            st.success("Setup data udtrukket!")

    with col_advice:
        st.subheader("🛠️ AI Setup Engineer")
        problem_desc = st.text_area("Beskriv bilens opførsel eller dine problemer:", 
                                   placeholder="Bilen føles meget nervøs over curbs på Nordschleife...")

        if st.button("🔧 Analysér Setup"):
            if setup_text_content and problem_desc:
                with st.spinner("Ingeniøren gennemgår dine tal..."):
                    # Prompt der kombinerer setup-data med brugerens problem
                    setup_prompt = f"""
                    Du er en Race Engineer. Her er et iRacing setup i HTML format: {setup_text_content[:2000]}...
                    Brugeren kører på {selected_track} i en {selected_car}.
                    Brugeren oplever følgende problem: {problem_desc}
                    
                    Kig på de faktiske værdier i settet (fjedre, vinger, dæktryk) og giv 3 konkrete ændringer.
                    Forklar HVORFOR disse ændringer vil hjælpe på netop denne bane.
                    """
                    try:
                        response = model.generate_content(setup_prompt)
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Kunne ikke analysere setup: {e}")
            else:
                st.warning("Upload venligst en fil og beskriv problemet først.")

    st.write("---")
    st.subheader("Quick Reference: Setup Matrix")
    # En lille tabel til hurtig selvhjælp
    st.table({
        "Problem": ["Understeer (Entry)", "Oversteer (Exit)", "Bouncing over bumps"],
        "Adjustment": ["Softer Front Springs / More Wing", "Softer Rear Springs / Less Diff Preload", "Lower Slow Compression (Dampers)"]
    })

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
        # Prompten er optimeret til at kigge efter "Coast time" og "Pedal overlap"
        prompt = """
        Du er en professionel iRacing Coach. Analysér dette screenshot fra Garage 61.
        Fokusér på:
        1. Bremsetryk (Peak pressure og Trail-braking).
        2. Throttle application (Hvor tidligt og hvor jævnt).
        3. Coast time (Tid hvor hverken bremse eller gas er aktiveret).
        Giv 3 konkrete øvelser baseret på de visuelle data.
        """

        if final_img:
            if st.button("🚀 Analysér min kørsel nu"):
                with st.spinner("AI Engineer analyserer grafer..."):
                    try:
                        response = model.generate_content([prompt, final_img])
                        analysis_text = response.text
                        
                        # Gem i session loggen
                        import datetime
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                        st.session_state.session_log.append({
                            "time": timestamp,
                            "content": analysis_text
                        })
                        
                        st.markdown(analysis_text)
                    except Exception as e:
                        if "429" in str(e):
                            st.error("⚠️ Rate limit nået. Vent 30 sekunder.")
                        else:
                            st.error(f"AI fejl: {e}")
        else:
            st.info("Indlæs telemetri for at modtage coaching.")

    # --- SESSION LOGGER SEKTION ---
    if st.session_state.session_log:
        st.write("---")
        col_log_header, col_clear = st.columns([3, 1])
        with col_log_header:
            st.subheader("📋 Session Log")
        with col_clear:
            if st.button("🗑️ Slet Log"):
                st.session_state.session_log = []
                st.rerun() # Genindlæser appen så loggen forsvinder med det samme
        
        for i, entry in enumerate(reversed(st.session_state.session_log)):
            with st.expander(f"Analyse kl. {entry['time']} (Forsøg {len(st.session_state.session_log) - i})"):
                st.write(entry['content'])
        
        # Download log
        full_log = "\n\n".join([f"--- KL. {e['time']} ---\n{e['content']}" for e in st.session_state.session_log])
        st.download_button(
            label="📥 Download Fuld Session Log",
            data=full_log,
            file_name=f"iracing_log_{datetime.date.today()}.txt",
            mime="text/plain"
        )
st.sidebar.write("---")
st.sidebar.info("Husk: Du har ~15 analyser i minuttet. Tag gerne små screenshots af specifikke sving for bedre præcision.")
