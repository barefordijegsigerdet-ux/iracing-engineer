import streamlit as st

# --- ENHANCED ENGINEER LOGIC ---
def get_advanced_feedback(pumps, peak_brake, vmin_delta, current_bias):
    driving = []
    bias_logic = []
    
    # Driving Analysis - Corner Entry
    if peak_brake > 70:
        driving.append({
            "title": "🚫 ABS Over-Engagement",
            "msg": f"Peak pressure of {peak_brake}% is locking the front end. You're 'parking' the car at the apex.",
            "fix": "Reduce peak to ~60% and focus on a faster, smoother release."
        })
    
    # Driving Analysis - Corner Exit
    if pumps >= 4:
        driving.append({
            "title": "📈 Throttle Saw-Toothing",
            "msg": f"Detected {pumps} throttle pumps. This 'traction testing' is costing you ~40m of acceleration distance.",
            "fix": "Hold a steady partial throttle (40-50%) before committing to 100%."
        })

    # The Bias Paradox Logic
    if current_bias < 50.5 and peak_brake > 65:
        bias_logic.append({
            "title": "⚖️ The Entry Paradox",
            "msg": f"Your {current_bias}% bias is too aggressive for your braking force.",
            "insight": "High pressure + Rear bias = Unstable entry. This is why you don't trust the car on exit."
        })
        
    return driving, bias_logic

# --- UI STYLING ---
st.set_page_config(layout="wide")
st.markdown("""<style>
    .report-card { background-color: #1e1e1e; padding: 20px; border-radius: 10px; border-left: 5px solid #ff4b4b; margin-bottom: 10px; }
    .bias-card { background-color: #1e1e1e; padding: 20px; border-radius: 10px; border-left: 5px solid #ffd166; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# ... (Sidebar inputs code from previous version) ...

driving_issues, bias_issues = get_advanced_feedback(pumps, peak_b, v_min_delta, current_b)

col1, col2 = st.columns(2)

with col1:
    st.markdown("### (A) Driving Analysis")
    for issue in driving_issues:
        st.markdown(f"""<div class='report-card'>
            <h4>{issue['title']}</h4>
            <p>{issue['msg']}</p>
            <small><b>ENGINEER'S FIX:</b> {issue['fix']}</small>
        </div>""", unsafe_allow_html=True)

with col2:
    st.markdown("### (B) Brake Bias Strategy")
    for issue in bias_issues:
        st.markdown(f"""<div class='bias-card'>
            <h4>{issue['title']}</h4>
            <p>{issue['msg']}</p>
            <p style='color:#ffd166;'><i>{issue['insight']}</i></p>
        </div>""", unsafe_allow_html=True)
