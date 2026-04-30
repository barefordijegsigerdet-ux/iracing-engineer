import streamlit as st
import pandas as pd

# --- SETUP DICTIONARY: SUBJECTIVE TO OBJECTIVE ---
# This acts as the Engineer's "Brain"
SETUP_ADVISOR = {
    "Corner Entry": {
        "Understeer (Doesn't want to turn)": "Lower Front Ride Height or Soften Front Springs.",
        "Oversteer (Rear is nervous/slides)": "Move Brake Bias forward or Stiffen Front Compression.",
    },
    "Mid-Corner": {
        "Understeer (Pushes wide)": "Soften Front Anti-Roll Bar or increase Front Wing.",
        "Oversteer (Rear feels loose)": "Soften Rear Anti-Roll Bar or increase Rear Wing.",
    },
    "Corner Exit": {
        "Understeer (Pushes wide on gas)": "Soften Front Rebound or increase Rear Compression.",
        "Oversteer (Snaps when flooring it)": "Soften Rear Springs or increase Rear Toe-in.",
    },
    "General / Bumps": {
        "Car bounces on curbs": "Soften Slow Compression or increase Ride Height.",
        "Bottoming out on straights": "Increase Spring Rate or add Bumpstop shims.",
    }
}

st.set_page_config(page_title="Chassis Engineering Lab", layout="wide")

# --- UI HEADER ---
st.title("🛠️ Chassis Engineering Lab")
st.markdown("Driver Coaching is disabled. Focus: **Mechanical Compliance & Driveability.**")

# --- LAYOUT ---
col_feedback, col_action = st.columns([1, 1])

with col_feedback:
    st.subheader("📋 Driver Debrief")
    st.info("Tell me exactly what you dislike about the current balance.")
    
    # 1. Select the Phase
    phase = st.selectbox("Where is the issue occurring?", list(SETUP_ADVISOR.keys()))
    
    # 2. Select the Feeling
    feeling = st.selectbox("What is the car doing?", list(SETUP_ADVISOR[phase].keys()))
    
    # 3. Driving Style Adjustment
    style = st.radio(
        "Preferred Driving Style:",
        ["Pointy/Oversteery (Rotation focus)", "Stable/Understeery (Security focus)", "Balanced"],
        index=2
    )
    
    notes = st.text_area("Specific Details (e.g., 'Only happens in Turn 3 under trail-braking')")

with col_action:
    st.subheader("🔧 Engineer's Prescription")
    
    # Logic-based recommendation
    fix = SETUP_ADVISOR[phase][feeling]
    
    st.success(f"**Primary Adjustment:** {fix}")
    
    # Contextual Tuning
    st.markdown("---")
    st.write("### 🧠 The Engineering Logic")
    if "Understeer" in feeling:
        st.write("We need to shift the **Mechanical Grip** to the front axle. By softening the front, we allow more weight transfer to load the front tires.")
    elif "Oversteer" in feeling:
        st.write("The rear tires are being overwhelmed. We are reducing the rate of weight transfer or increasing downforce to keep the rear planted.")

    # Style-specific tweak
    if style == "Pointy/Oversteery (Rotation focus)" and "Understeer" in feeling:
        st.warning("⚠️ **Aggressive Tweak:** Since you like a pointy car, consider also increasing **Rear Ride Height** by 2mm to force the nose down.")
    
    st.divider()
    st.caption("Pro Tip: Check your tire temps. If the middles are hotter than the edges, your pressures are too high, which masks setup issues.")

# --- SETUP LOG ---
st.header("📝 Setup Change Log")
if 'log' not in st.session_state: st.session_state.log = []

with st.form("log_form"):
    change = st.text_input("What did you change?")
    result = st.text_input("Result (e.g., 'Gained 0.2s', 'Too loose')")
    if st.form_submit_state("Save Change"):
        st.session_state.log.append({"Change": change, "Result": result})

if st.session_state.log:
    st.table(pd.DataFrame(st.session_state.log))
