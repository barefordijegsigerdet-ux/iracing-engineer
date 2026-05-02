import streamlit as st
from engine.setup_logic import get_porsche_advice
from engine.coaching_tips import get_track_notes

# Konfiguration
st.set_page_config(page_title="iRacing Engineer Pro", page_icon="🏎️", layout="wide")

# Custom CSS for et mørkt "Racing" look
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stSelectbox label { color: #ff4b4b !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏎️ iRacing Porsche Cup Engineer & Coach")
st.write("---")

# Navigation i sidebjælken
mode = st.sidebar.radio("Vælg Værktøj:", ["🛠️ Setup Engineer", "🏁 Driver Coach"])

if mode == "🛠️ Setup Engineer":
    st.header("Virtual Race Engineer")
    st.subheader("Diagnosticér din Porsche 992 Cup")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        problem = st.selectbox("Hvad mærker du i bilen?", [
            "Understyring (Indgang)", 
            "Understyring (Mid-corner)", 
            "Overstyring (Exit)",
            "Bilen er nervøs over curbs",
            "Blokering af forhjul"
        ])
    
    with col2:
        advice = get_porsche_advice(problem)
        st.write(f"### 💡 Analyse")
        st.success(advice["Løsning"])
        st.write(f"### 🔧 Setup Ændring")
        st.info(advice["Setup"])

elif mode == "🏁 Driver Coach":
    st.header("Driver Coach: Bane-analyse")
    track = st.selectbox("Vælg Bane:", ["Zandvoort"])
    
    st.write("---")
    notes = get_track_notes(track)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.image("https://www.iracing.com/wp-content/uploads/2020/06/zandvoort-map.png", caption="Banekort: Zandvoort")
    
    with col2:
        st.subheader("Coach Noter")
        for corner, note in notes.items():
            with st.expander(corner):
                st.write(note)

st.sidebar.write("---")
st.sidebar.info("Tip: Brug Garage 61 til at finde symptomerne (f.eks. rat-støj eller hastighedstab), og brug denne app til at finde løsningen.")
