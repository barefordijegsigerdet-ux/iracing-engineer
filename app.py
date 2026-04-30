import streamlit as st
import pandas as pd
import numpy as np

# --- ENGINEER LOGIC ENGINE ---
def generate_engineer_report(v_min_diff, throttle_pumps, max_brake, bias):
    report = {
        "Driving": [],
        "Bias": [],
        "Summary": ""
    }
    
    # 1. Driving Analysis (Pattern Recognition)
    if throttle_pumps > 3:
        report["Driving"].append(f"**Throttle Hesitation:** Detected {throttle_pumps} pumps on exit. You are 'testing' traction. Trust the car or adjust bias.")
    if max_brake > 70:
        report["Driving"].append(f"**Over-Braking:** Peak pressure of {max_brake}% is triggering Deep ABS, killing your turn-in and vMin.")
    if v_min_diff < -5:
        report["Driving"].append(f"**Corner Speed:** You are over-slowing the apex by {abs(v_min_diff)} km/h compared to the benchmark.")

    # 2. Bias Analysis
    benchmark_bias = 50.7
    if bias < benchmark_bias and max_brake > 65:
        report["Bias"].append(f"**The Paradox:** Current {bias}% is more rearward than benchmark ({benchmark_bias}%). Your high pressure ({max_brake}%) is destabilizing the rear.")
    
    return report

st.set_page_config(page_title="SimCup AI Engineer", layout="wide")

st.title("🏁 SimCup DK | Porsche 992.2 Engineer")

# --- DATA INPUT SIMULATION ---
# In a real app, these values would be calculated from your uploaded .csv
with st.sidebar:
    st.header("Telemetry Snapshot")
    v_min_delta = st.slider("vMin vs Benchmark (km/h)", -20, 5, -10)
    pumps = st.number_input("Throttle Pumps Detected", value=6)
    peak_b = st.slider("Max Brake Pressure (%)", 0, 100, 75)
    current_b = st.number_input("Current Brake Bias", value=50.0, step=0.1)

# --- THE AI STUDIO FEEDBACK UI ---
st.subheader("📋 Engineering Analysis Report")

analysis = generate_engineer_report(v_min_delta, pumps, peak_b, current_b)

colA, colB = st.columns(2)

with colA:
    st.markdown("### (A) Driving Issues")
    for issue in analysis["Driving"]:
        st.error(issue)

with colB:
    st.markdown("### (B) Brake Bias Issues")
    for b_issue in analysis["Bias"]:
        st.warning(b_issue)

st.divider()

# Only shows advice when "Asked" - per your AI Studio instructions
if st.button("Request Coaching & Bias Adjustments"):
    st.success("### Engineer's Conclusion")
    st.write(f"""
    1. **Primary Objective:** Flatten the Delta spike. 
    2. **The Fix:** Move Bias to **50.7%** to match Leeroy. 
    3. **The Technique:** Reduce peak brake pressure to **60%** to avoid ABS engagement. 
    This will allow the car to rotate naturally so you can reach 100% throttle without the 'saw-tooth' modulation.
    """)
