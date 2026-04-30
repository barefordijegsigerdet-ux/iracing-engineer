import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Race Engineer AI", layout="wide")

# --- DATABASE: SETUP LOGIC ---
# This translates "I feel X" into "Do Y"
SETUP_LOGIC = {
    "Entry Oversteer (Rear slides entering turn)": "Increase Front Compression or Decrease Rear Rebound. Check if Brake Bias is too far rearward.",
    "Mid-Corner Understeer (Car won't turn)": "Soften Front Anti-Roll Bar or increase Front Wing/Downforce.",
    "Exit Snap (Rear slides when hitting gas)": "Soften Rear Springs or increase Rear Toe-in for stability.",
    "Bottoming Out (Scraping on bumps)": "Increase Ride Height or stiffen Springs/Bumpstops.",
    "Unstable under Heavy Braking": "Move Brake Bias forward or increase Differential Coast Ramp angle."
}

# --- TAB 1: DRIVER COACH ---
def render_coach():
    st.subheader("🏁 Driver Coaching & Audit")
    st.info("Upload your latest Garage 61 export. I'll find the biggest time loss and give you one specific instruction.")
    
    col1, col2 = st.columns(2)
    with col1: ref = st.file_uploader("🟦 Reference", type=['csv'], key="ref_c")
    with col2: user = st.file_uploader("🟥 Your Lap", type=['csv'], key="user_c")

    if ref and user:
        df_r = pd.read_csv(ref).sort_values('LapDistPct')
        df_u = pd.read_csv(user).sort_values('LapDistPct')
        
        # FIND THE PAIN POINT (Logic: Max Delta Slope)
        dist_pct = np.linspace(0, 1, 2000)
        u_time = np.cumsum(np.diff(df_u['LapDistPct'], prepend=0) / (df_u['Speed'].replace(0,0.1)/3.6))
        r_time = np.cumsum(np.diff(df_r['LapDistPct'], prepend=0) / (df_r['Speed'].replace(0,0.1)/3.6))
        delta = np.interp(dist_pct, df_u['LapDistPct'], u_time) - np.interp(dist_pct, df_r['LapDistPct'], r_time)
        
        target_idx = np.argmax(np.gradient(delta))
        error_pct = dist_pct[target_idx]
        
        st.error(f"### Diagnostic: Big loss at {error_pct*100:.1f}% of the lap")
        
        # Logic Audit
        u_slice = df_u.iloc[int(len(df_u)*error_pct)]
        r_slice = df_r.iloc[int(len(df_r)*error_pct)]
        
        if u_slice['Brake'] > r_slice['Brake'] + 0.2:
            st.markdown("### 💡 **Instruction: Over-braking**")
            st.write("You are killing the car's rotation by staying on the brakes too long. **Release the brake 10% earlier** and trust the front tires to grip.")
        elif u_slice['Speed'] < r_slice['Speed'] - 5:
            st.markdown("### 💡 **Instruction: Apex Momentum**")
            st.write("Your minimum speed is too low. You are 'parking' the car. Focus on **carrying 5kph more** through the center of the corner.")
        else:
            st.markdown("### 💡 **Instruction: Throttle Commitment**")
            st.write("The Pro is at 100% throttle while you are at 60%. **Straighten the car earlier** so you can floor it sooner.")

# --- TAB 2: SETUP ENGINEER ---
def render_setup():
    st.subheader("🔧 Setup Shop")
    st.markdown("Describe what the car is doing wrong. I will give you the mechanical fix.")
    
    col_setup, col_fix = st.columns([1, 1])
    
    with col_setup:
        st.write("### 💬 Driver Feedback")
        complaint = st.selectbox("What is the car doing?", ["Select an issue..."] + list(SETUP_LOGIC.keys()))
        style = st.radio("Driving Style preference:", ["Aggressive (Pointy nose)", "Stable (Safe rear)", "Balanced"])
        
        setup_file = st.file_uploader("Upload .sto or .json Setup (Optional context)", type=['sto', 'json', 'txt'])
        notes = st.text_area("Extra details (e.g., 'Only happens in high-speed turns')")

    with col_fix:
        st.write("### 🛠️ Engineer's Adjustment")
        if complaint != "Select an issue...":
            st.success(f"**Recommended Change:** {SETUP_LOGIC[complaint]}")
            if "Oversteer" in complaint:
                st.write("---")
                st.write("**Visual Reference: Weight Transfer**")
                st.caption("When you lift off the throttle, weight shifts forward. If your rear springs are too stiff, the tires lose vertical load and slide.")
            
            st.warning("⚠️ **Rule of Thumb:** Only change ONE thing at a time. Test for 3 laps before changing something else.")
        else:
            st.info("Select a behavior from the dropdown to see the recommended setup fix.")

# --- MAIN APP NAVIGATION ---
tab_coaching, tab_setup = st.tabs(["🏎️ Driver Coach", "🔧 Setup Engineer"])

with tab_coaching:
    render_coach()

with tab_setup:
    render_setup()
