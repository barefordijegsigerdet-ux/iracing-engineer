import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Race Engineer AI", layout="wide")

# --- DATA: SETUP KNOWLEDGE BASE ---
# Maps specific driver "feelings" to engineering solutions
SETUP_MATRIX = {
    "GT3 / GTE": {
        "Too much 'understeer' on corner entry": "Soften Front Springs or increase Front Aero (Wing).",
        "The rear 'snaps' when I touch the gas": "Soften Rear Anti-Roll Bar or increase Rear Wing.",
        "Car feels 'lazy' or slow to turn": "Stiffen Front Springs or increase Front Toe-out.",
        "Scraping/Bottoming on curbs": "Increase Ride Height (Front and Rear) or stiffen Bumpstops.",
        "Unstable under heavy braking": "Move Brake Bias forward (+1-2%)."
    },
    "Formula / High Downforce": {
        "Understeer in high-speed turns": "Increase Front Wing Angle.",
        "Oversteer in high-speed turns": "Increase Rear Wing Angle.",
        "Bottoming at high speed": "Increase Third-Spring (Heave) stiffness.",
        "Car feels 'darty' and nervous": "Increase Rear Toe-in or decrease Front Wing."
    }
}

# --- TABS SETUP ---
tab_coach, tab_setup_eng = st.tabs(["🏎️ Driver Coaching", "🔧 Setup Engineer"])

with tab_coach:
    st.subheader("🏁 Live Driver Audit")
    st.markdown("Focus on the driving. I'll give you your mission.")
    
    # [Telemetery processing logic from previous iterations]
    st.info("Upload your Garage 61 .csv to see your next instruction.")
    # (The logic seen in image_1e23e4.png would reside here)

with tab_setup_eng:
    st.subheader("🔧 Engineering & Car Prep")
    
    col_input, col_output = st.columns([1, 1])
    
    with col_input:
        st.write("### 🗣️ Driver Feedback")
        car_type = st.selectbox("Vehicle Category", list(SETUP_MATRIX.keys()))
        
        feeling = st.selectbox(
            "Describe the car's worst behavior:",
            ["Select the main issue..."] + list(SETUP_MATRIX[car_type].keys())
        )
        
        style_pref = st.select_slider(
            "Preferred Balance Style",
            options=["Safe/Understeer", "Neutral", "Aggressive/Oversteer"],
            value="Neutral"
        )
        
        driver_notes = st.text_area("What else? (e.g., 'Only happens at Turn 7 at Zandvoort')")
        
        if st.button("Consult Engineer"):
            st.session_state.last_consult = feeling

    with col_output:
        st.write("### 🛠️ Mechanical Fix")
        if 'last_consult' in st.session_state and st.session_state.last_consult != "Select the main issue...":
            recommendation = SETUP_MATRIX[car_type][st.session_state.last_consult]
            
            st.success(f"**Recommended Change:** {recommendation}")
            
            # Contextual Logic
            st.write("---")
            st.write("**Why this works for your style:**")
            if style_pref == "Aggressive/Oversteer":
                st.write("Since you prefer a 'pointy' car, we are prioritizing front-end bite. Be careful with the throttle on exit.")
            elif style_pref == "Safe/Understeer":
                st.write("We are adding stability to the rear so you can trust the car more, even if it costs a bit of turn-in speed.")
            
            st.caption("Pro Tip: If you make a change and it doesn't help after 3 laps, revert it. Don't 'chase' the setup.")
