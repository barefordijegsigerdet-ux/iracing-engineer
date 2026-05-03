import streamlit as st
import google.generativeai as genai
from PIL import Image
from engine.setup_logic import get_vehicle_advice
from engine.coaching_tips import get_track_data

# --- KONFIGURATION ---
st.set_page_config(page_title="iRacing AI Engineer", page_icon="🏎️", layout="wide")

# Opsætning af Gemini (Gemini 3.1 Flash Image Preview er ideel til screenshots)
# Erstat 'DIN_API_NØGLE' med din faktiske nøgle fra Google AI Studio
API_KEY = "DIN_API_NØGLE" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-3.1-flash-image-preview')

# --- FUNKTIONER ---
def analyze_with_ai(image, car_name):
    prompt = f"""
    Du er en professionel Race Engineer. Her er et telemetri-screenshot fra Garage 61 for en {car_name}.
    Sammenlign brugerens linje med referencen og identificér de 3 vigtigste steder hvor der tabes tid.
    Giv konkrete råd til enten setup-ændringer eller køreteknik. Vær kort og kontant.
    """
    response = model.generate_content([prompt, image])
    return response.text

# --- UI DESIGN ---
st.title("🏎️ iRacing AI Engineer & Setup Exporter")
st.sidebar.title("Kontrolpanel")
mode = st.sidebar.radio("Vælg værktøj:", ["🛠️ Setup & AI Analyse", "🏁 Driver Coach"])

if mode == "🛠️ Setup & AI Analyse":
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("Konfiguration")
        selected_car = st.selectbox("Vælg Bil:", ["Porsche 911 Cup (992)", "GT3 Class"])
        problem = st.selectbox("Hvad mærker du?", ["Understyring (Indgang)", "Overstyring (Exit)", "Nervøs på curbs", "Bundskrab (Bottoming)"])
        
        static_advice = get_vehicle_advice(selected_car, problem)
        st.success(f"**Standard-råd:** {static_advice}")
        
        st.write("---")
        st.subheader("Situationsbestemt AI Analyse")
        uploaded_file = st.file_uploader("Upload screenshot fra Garage 61 (f.eks. speed/throttle)", type=["png", "jpg", "jpeg"])
        
        if uploaded_file and st.button("🚀 Anmod om AI Feedback"):
            img = Image.open(uploaded_file)
            with st.spinner("AI Engineer analyserer dine specifikke data..."):
                try:
                    ai_response = analyze_with_ai(img, selected_car)
                    st.session_state['ai_feedback'] = ai_response
                except Exception as e:
                    st.error(f"Fejl i AI-forbindelse: {e}")

    with col2:
        st.header("Engineer Rapport")
        if 'ai_feedback' in st.session_state:
            st.markdown("### 🤖 AI Feedback på din session:")
            st.write(st.session_state['ai_feedback'])
            
            # Eksport-mulighed
            export_text = f"ENGINEER REPORT - {selected_car}\n\nSymptom: {problem}\nStandard Råd: {static_advice}\n\nAI ANALYSE:\n{st.session_state['ai_feedback']}"
            st.download_button(
                label="📥 Download Rapport som TXT",
                data=export_text,
                file_name="race_engineer_report.txt",
                mime="text/plain"
            )
        else:
            st.info("Upload et billede og tryk på knappen for at få en specifik analyse af din kørsel.")

elif mode == "🏁 Driver Coach":
    st.header("Bane-reference")
    selected_track = st.selectbox("Vælg Bane:", ["Zandvoort", "Spa"])
    track_info = get_track_data(selected_track)
    
    c1, c2 = st.columns(2)
    with c1:
        if track_info["map"]:
            st.image(track_info["map"], caption=f"Kort over {selected_track}")
    with c2:
        st.subheader("Coach Noter")
        for corner, note in track_info["notes"].items():
            with st.expander(corner):
                st.write(note)

st.sidebar.write("---")
st.sidebar.caption("Version 2.0 - Powered by Gemini 3.1 Flash")
