import streamlit as st
from engine.setup_logic import get_vehicle_advice
from engine.coaching_tips import get_track_data

st.set_page_config(page_title="iRacing Engineer Pro", layout="wide")

# Sidebjælke: Valg af Bil og Værktøj
st.sidebar.title("🏎️ Pro iRacing Tools")
tool = st.sidebar.radio("Vælg værktøj", ["Setup Advisor", "Driver Coach"])

if tool == "Setup Advisor":
    st.title("🛠️ Setup Engineer")
    
    # Bil-valg
    car = st.selectbox("Vælg din bil:", ["Porsche 911 Cup (992)", "GT3 Class (General)", "Formula 4 / Super Formula"])
    
    # Symptom-valg
    problem = st.selectbox("Hvad mærker du?", ["Understyring (Indgang)", "Overstyring (Exit)", "Nervøs på curbs", "Bundskrab (Bottoming)"])
    
    advice = get_vehicle_advice(car, problem)
    st.info(f"**Anbefaling for {car}:**\n\n{advice}")

elif tool == "Driver Coach":
    st.title("🏁 Driver Coaching")
    
    # Bane-valg (Dynamisk liste)
    track_name = st.selectbox("Vælg bane:", ["Zandvoort", "Spa-Francorchamps", "Monza"])
    data = get_track_data(track_name)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if data["map"]:
            st.image(data["map"], caption=f"Banekort: {track_name}")
            
    with col2:
        st.subheader(f"Track Notes: {track_name}")
        for corner, note in data["notes"].items():
            with st.expander(corner):
                st.write(note)

st.sidebar.write("---")
st.sidebar.caption("Hostet version v1.2")
