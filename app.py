import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Coach Consultation", layout="wide")

# --- DATA ENGINE ---
def get_diagnostics(df_u, df_r):
    # Standardize to 5000 pts to find the "Pain Point"
    dist_pct = np.linspace(0, 1, 5000)
    # Calculate delta slope to find where you're bleeding time fastest
    u_time = np.cumsum(np.diff(df_u['LapDistPct'], prepend=0) / (df_u['Speed'].replace(0,0.1)/3.6))
    r_time = np.cumsum(np.diff(df_r['LapDistPct'], prepend=0) / (df_r['Speed'].replace(0,0.1)/3.6))
    
    u_t_i = np.interp(dist_pct, df_u['LapDistPct'], u_time)
    r_t_i = np.interp(dist_pct, df_r['LapDistPct'], r_time)
    delta = u_t_i - r_t_i
    
    # Find max loss rate (slope of delta)
    loss_rate = np.gradient(delta)
    target_idx = np.argmax(loss_rate)
    return dist_pct[target_idx], delta[target_idx]

# --- UI ---
st.title("🎙️ Talk to the Race Engineer")
st.markdown("Upload your lap and the reference. I will find your biggest mistake and explain the logic.")

c1, c2 = st.columns(2)
with c1: ref_file = st.file_uploader("🟦 Reference", type=['csv'])
with c2: user_file = st.file_uploader("🟥 Your Lap", type=['csv'])

if ref_file and user_file:
    df_r = pd.read_csv(ref_file).sort_values('LapDistPct')
    df_u = pd.read_csv(user_file).sort_values('LapDistPct')
    
    error_pct, total_delta = get_diagnostics(df_u, df_r)
    
    # Slicing the 'Error Zone'
    window = 0.015 
    u_slice = df_u[(df_u['LapDistPct'] > error_pct - window) & (df_u['LapDistPct'] < error_pct + window)]
    r_slice = df_r[(df_r['LapDistPct'] > error_pct - window) & (df_r['LapDistPct'] < error_pct + window)]

    st.divider()
    
    # COACHING LOGIC DISPLAY
    col_chat, col_viz = st.columns([1, 1])
    
    with col_chat:
        st.subheader("Engineer's Diagnostic")
        st.error(f"📍 Critical Time Loss detected at {error_pct*100:.1f}% of the lap.")
        
        # LOGIC CHECK 1: Brake Release vs Speed
        if u_slice['Speed'].min() < r_slice['Speed'].min() - 3:
            st.write("### 🔍 The Logic: 'Overslowing'")
            st.write("You are trading too much entry speed for a 'safe' apex. You're effectively stopping the car in the middle of the corner.")
            st.info("🏁 **Fix:** Aim to release the last 20% of your brake pressure earlier. Use the car's momentum to carry it to the apex rather than 'driving' it there.")
        
        # LOGIC CHECK 2: Throttle Application
        elif u_slice['Throttle'].mean() < r_slice['Throttle'].mean() - 0.2:
            st.write("### 🔍 The Logic: 'Exit Hesitation'")
            st.write("You are waiting for the car to be perfectly straight before hitting 100% throttle. The Pro is using throttle to help the car steer out.")
            st.info("🏁 **Fix:** Try to get to 'Maintenance Throttle' (10-20%) earlier to settle the rear, then ramp to 100% as you open the steering.")

    with col_viz:
        # Show only the relevant 'Error' data
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=r_slice['Speed'], name="Pro Speed", line=dict(color='blue', dash='dot')))
        fig.add_trace(go.Scatter(y=u_slice['Speed'], name="Your Speed", line=dict(color='red', width=3)))
        fig.update_layout(title="Speed Profile at Error Point", template="plotly_dark", height=300)
        st.plotly_chart(fig, use_container_width=True)

    # USER QUERY
    st.text_input("Ask the Coach: (e.g., 'Why am I losing time in the slow hairpins?')")
