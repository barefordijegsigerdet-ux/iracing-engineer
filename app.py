import streamlit as st
import google.generativeai as genai
from PIL import Image
import streamlit.components.v1 as components
import datetime

# --- 1. SIKKERHED & AI KONFIGURATION ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except KeyError:
    st.error("Fejl: Kunne ikke finde 'GEMINI_API_KEY'. Tjek dine Streamlit Secrets!")
    st.stop()

# Vi bruger Gemini 3.1 Flash Lite Preview for bedste kvote (15 RPM)
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

# --- 2. UI DESIGN & LAYOUT ---
st.set_page_config(page_title="iRacing Pro Engineer", page_icon="🏎️", layout="wide")

# Custom CSS for et professionelt look
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: bold; }
    .main { background-color: #f5f5f5; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏎️ iRacing Pro Engineer & Driver Coach")

# --- SIDEBAR: GUIDE & OM PROJEKTET ---
with st.sidebar:
    st.header("📖 Guide & Info")
    
    with st.expander("🚀 Hurtig Start Guide"):
        st.write("""
        1. **Setup Advisor:** Upload din HTML-fil og beskriv bilens opførsel for at få konkrete ændringer.
        2. **Driver Coach:** Tag et screenshot i Garage 61 (Brake/Throttle/Speed) og paste det ind.
        3. **Analyse:** Tryk på knappen og få 3 konkrete øvelser til din kørsel.
        """)
    
    st.write("---")
    
    with st.expander("ℹ️ Om dette projekt"):
        st.markdown(f"""
        **Udviklet af Jonas Hauerbach**
        
        Dette projekt er skabt for at gøre avanceret data-analyse tilgængelig for alle iRacere, uanset om man jagter tiendedele på Spa, Monza eller de tekniske sving på Sebring.
        
        Appen bruger **Google Gemini 3.1** til at "se" dine grafer og give dig feedback som en rigtig Race Engineer.
        
        *Bemærk: Appen kører på en gratis kvote. Hvis den melder fejl, så vent 30-60 sekunder og prøv igen.*
        """)
    
    st.sidebar.caption(f"© {datetime.date.today().year} | Version 2.8")

# --- TABS ---
tab1, tab2 = st.tabs(["🛠️ Setup Advisor", "🏁 Driver Coach"])

# --- TAB 1: SETUP ADVISOR ---
with tab1:
    st.header("Setup Management & Engineer Analysis")
    col_setup, col_engineer = st.columns([1, 1])
    
    with col_setup:
        st.subheader("Indlæs Setup Data")
        car_model = st.selectbox("Bilmodel:", ["Porsche 911 Cup (992)", "GT3 Class", "F4", "LMP2"])
        track_name = st.text_input("Bane:", placeholder="F.eks. Spa-Francorchamps...")
        
        setup_file = st.file_uploader("Upload Garage HTML setup", type=["html"])
        setup_content = ""
        if setup_file:
            raw_html = setup_file.read()
            try:
                setup_content = raw_html.decode("utf-8")
            except:
                setup_content = raw_html.decode("iso-8859-1")
            st.success("✅ Setup-data indlæst!")

    with col_engineer:
        st.subheader("Spørg Ingeniøren")
        user_issue = st.text_area("Beskriv bilens opførsel:", placeholder="F.eks.: Bilen understyrer mid-corner i de hurtige sving...")
        
        if st.button("🔧 Analysér Setup"):
            if setup_content and user_issue:
                with st.spinner("Ingeniøren regner på tallene..."):
                    prompt = f"Du er en iRacing Engineer. Bane: {track_name}. Bil: {car_model}. Problem: {user_issue}. Her er setup data: {setup_content[:3000]}. Giv 3 konkrete råd."
                    try:
                        response = model.generate_content(prompt)
                        st.info(response.text)
                    except Exception as e:
                        st.error(f"Fejl: {e}")
            else:
                st.warning("Upload setup og beskriv problemet først.")

# --- TAB 2: DRIVER COACH ---
with tab2:
    st.header("Telemetri Analyse & Coaching")
    
    if 'session_log' not in st.session_state:
        st.session_state.session_log = []

    col_img, col_ai = st.columns([1, 1])
    
    with col_img:
        st.subheader("Garage 61 Data")
        from streamlit_paste_button import paste_image_button
        pasted_output = paste_image_button(label="📋 Paste screenshot (Ctrl+V)", background_color="#FF4B4B")
        
        tele_file = st.file_uploader("Eller upload fil", type=["png", "jpg", "jpeg"])
        
        final_img = None
        if tele_file: final_img = Image.open(tele_file)
        elif pasted_output.image_data is not None: final_img = pasted_output.image_data
            
        if final_img:
            st.image(final_img, caption="Session Telemetri", use_container_width=True)

    with col_ai:
        st.subheader("🤖 AI Engineer Feedback")
        if final_img:
            if st.button("🚀 Analysér min kørsel nu"):
                with st.spinner("AI Coachen kigger på dine grafer..."):
                    prompt = "Analysér bremsetryk, throttle og coast time på dette billede. Sammenlign blå med rød og giv 3 konkrete øvelser."
                    try:
                        response = model.generate_content([prompt, final_img])
                        analysis = response.text
                        st.session_state.session_log.append({"time": datetime.datetime.now().strftime("%H:%M"), "content": analysis})
                        st.markdown(analysis)
                    except Exception as e:
                        st.error(f"Fejl: {e}")
        else:
            st.info("Paste et screenshot for at starte.")

    # --- SESSION LOG ---
    if st.session_state.session_log:
        st.write("---")
        col_h, col_c = st.columns([3, 1])
        col_h.subheader("📋 Session Log")
        if col_c.button("🗑️ Slet Log"):
            st.session_state.session_log = []
            st.rerun()
        
        for entry in reversed(st.session_state.session_log):
            with st.expander(f"Analyse kl. {entry['time']}"):
                st.write(entry['content'])
