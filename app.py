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

# Vi bruger Gemini 3.1 Flash Lite Preview for at maksimere kvoten (15 RPM)
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')

# --- 2. UI DESIGN & LAYOUT ---
st.set_page_config(page_title="iRacing Pro Engineer", page_icon="🏎️", layout="wide")

st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: bold; }
    .stActionButton { background-color: #FF4B4B !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏎️ iRacing Pro Engineer & Driver Coach")

# --- 3. SIDEBAR: GARAGE 61 SESSION CONDITIONS ---
with st.sidebar:
    st.header("📖 Session Management")
    
    with st.expander("🌤️ Garage 61 Conditions", expanded=True):
        # 1. Sky
        sky = st.selectbox("Sky", ["Clear skies", "Partly cloudy", "Mostly cloudy", "Overcast", "Cloudy"])
        
        # 2. Track Temp & 3. Air Temp
        col_t1, col_t2 = st.columns(2)
        track_temp = col_t1.number_input("Track Temp (°C)", value=38.3, step=0.1)
        air_temp = col_t2.number_input("Air Temp (°C)", value=20.9, step=0.1)
        
        # 4. Wind Speed & Direction
        col_w1, col_w2 = st.columns([2, 1])
        wind_speed = col_w1.number_input("Wind (km/h)", value=4)
        wind_dir = col_w2.selectbox("Dir", ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "ENE", "ESE", "WNW", "WSW", "NNE", "NNW", "SSE", "SSW"])
        
        # 5. Relative Humidity
        rel_humidity = st.slider("Rel. Humidity (%)", 0, 100, 82)
        
        # 6. Fog Level
        fog_level = st.slider("Fog Level (%)", 0, 100, 0)
        
        # 7. Precipitation
        precipitation = st.slider("Precipitation (%)", 0, 100, 0)
        
        # 8. Track State
        track_state = st.selectbox("Track State", 
                                  ["Clean", "Low usage", "Moderately low usage", "Moderate", "Heavy", "Greasy"],
                                  index=2)
        
        # 9. Fuel Level
        fuel_level = st.number_input("Fuel Level (L)", value=40.88, step=0.01)

    # Samler forholdene til AI'en
    current_conditions = (
        f"FORHOLD: Sky: {sky}, Bane: {track_temp}°C, Luft: {air_temp}°C, "
        f"Vind: {wind_speed} km/h {wind_dir}, Fugt: {rel_humidity}%, "
        f"Tåge: {fog_level}%, Regn: {precipitation}%, "
        f"Bane-state: {track_state}, Brændstof: {fuel_level}L."
    )

    st.write("---")
    
    with st.expander("ℹ️ Om dette projekt"):
        st.markdown(f"""
        **Udviklet af Jonas Hauerbach**
        
        Dette projekt er skabt for at gøre avanceret data-analyse tilgængelig for alle iRacere, uanset om man jagter tiendedele på Spa, Monza eller de tekniske sving på Sebring.
        
        Appen bruger **Google Gemini 3.1** til at analysere dine pedal-inputs og setup-valg i realtid baseret på dine specifikke baneforhold.
        
        *Kører på Hobby Tier (Gratis kvote). Ved fejl, vent 30 sekunder.*
        """)
    
    st.sidebar.caption(f"© {datetime.date.today().year} | Version 3.0")

# --- 4. TABS ---
tab1, tab2 = st.tabs(["🛠️ Setup Advisor", "🏁 Driver Coach"])

# --- TAB 1: SETUP ADVISOR ---
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
            st.success("✅ Setup-fil scannet!")

    with col_engineer:
        st.subheader("🔧 AI Race Engineer")
        user_issue = st.text_area("Hvad vil du ændre/forbedre?", 
                                   placeholder="Beskriv bilens balance...")
        
        if st.button("🔧 Analysér Setup"):
            if setup_content and user_issue:
                with st.spinner("Ingeniøren beregner ændringer..."):
                    prompt = f"""
                    Du er en iRacing Engineer. 
                    KONTEKST: Bane: {track_name}, Bil: {car_model}. 
                    FORHOLD: {current_conditions}.
                    PROBLEM: {user_issue}. 
                    SETUP DATA: {setup_content[:3000]}. 
                    Giv 3 konkrete råd til setup-ændringer baseret på disse forhold.
                    """
                    try:
                        response = model.generate_content(prompt)
                        st.info(response.text)
                    except Exception as e:
                        st.error(f"Fejl: {e}")
            else:
                st.warning("Indlæs venligst setup og beskriv dit problem.")

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
        st.subheader("🤖 AI Driver Coach")
        if final_img:
            if st.button("🚀 Analysér min kørsel nu"):
                with st.spinner("Coachen analyserer dine data..."):
                    prompt = f"""
                    Analysér denne iRacing telemetri. 
                    SESSION INFO: {current_conditions}. 
                    Fokusér på bremsetryk (blå vs rød), throttle timing og coast time. 
                    Giv 3 konkrete øvelser til næste stint.
                    """
                    try:
                        response = model.generate_content([prompt, final_img])
                        analysis = response.text
                        st.session_state.session_log.append({
                            "time": datetime.datetime.now().strftime("%H:%M"), 
                            "content": analysis
                        })
                        st.markdown(analysis)
                    except Exception as e:
                        st.error(f"Fejl: {e}")
        else:
            st.info("Paste et screenshot fra Garage 61 for at få feedback.")

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
        
        full_report = "\n\n".join([f"--- KL. {e['time']} ---\n{e['content']}" for e in st.session_state.session_log])
        st.download_button("📥 Download Rapport", data=full_report, file_name="coaching_report.txt")
