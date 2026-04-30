import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# --- UTILS: TIME CONVERSION ---
def lap_to_seconds(lap_str):
    """Converts '1:41.332' to 101.332 seconds."""
    try:
        if ':' in str(lap_str):
            m, s = str(lap_str).split(':')
            return int(m) * 60 + float(s)
        return float(lap_str)
    except:
        return None

# --- ENGINE: SESSION SUMMARY ANALYSIS ---

def analyze_session(df):
    """Processes the Lap-by-Lap Session Summary CSV."""
    df['LapSeconds'] = df['Lap time'].apply(lap_to_seconds)
    # Filter out pit laps and non-clean laps for pace analysis
    clean_laps = df[(df['Pit in'] == 'No') & (df['Pit out'] == 'No') & (df['Clean'] == 'Yes')].copy()
    
    metrics = {
        "avg_pace": clean_laps['LapSeconds'].mean(),
        "consistency": clean_laps['LapSeconds'].std(), # Standard Deviation
        "fuel_per_lap": df['Fuel used'].mean(),
        "total_laps": df['Lap'].max()
    }
    return df, clean_laps, metrics

# --- ENGINE: TELEMETRY (PREVIOUS LOGIC) ---

def process_telemetry(df):
    df.columns = [c.strip() for c in df.columns]
    # Ensure speed is km/h
    if df['Speed'].max() < 100: df['Speed'] *= 3.6
    # Ensure pedals are 0-100
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1: df[col] *= 100.0
    return df

# --- UI SETUP ---
st.set_page_config(page_title="Race Engineer Pro", layout="wide")

def main():
    st.title("🏎️ Race Engineer Pro | Endurance & Performance Suite")
    
    with st.sidebar:
        st.header("1. Telemetry (Single Lap)")
        file_d = st.file_uploader("Driver Telemetry CSV", type=['csv'])
        file_b = st.file_uploader("Benchmark Telemetry CSV", type=['csv'])
        
        st.header("2. Session Summary (Stint)")
        file_s = st.file_uploader("Session Summary CSV", type=['csv'])
        st.info("Upload the 'Laps' export from Garage 61 for stint analysis.")

    tab_telemetry, tab_session, tab_coach, tab_setup = st.tabs([
        "📊 Telemetry Analysis", "⏱️ Stint & Fuel", "🧠 Driver Coach", "🔧 Setup Lab"
    ])

    # --- TAB: SESSION ANALYSIS (NEW) ---
    with tab_session:
        if file_s:
            df_s, clean_laps, m = analyze_session(pd.read_csv(file_s))
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Avg Pace", f"{m['avg_pace']:.3f}s")
            c2.metric("Pace Variance", f"±{m['consistency']:.3f}s", delta_color="inverse")
            c3.metric("Fuel / Lap", f"{m['fuel_per_lap']:.2f} L")
            
            # Estimate Stint Length
            remaining_fuel = df_s['Fuel level'].iloc[-1]
            laps_left = remaining_fuel / m['fuel_per_lap'] if m['fuel_per_lap'] > 0 else 0
            c4.metric("Est. Laps Remaining", f"{laps_left:.1f}")

            # Pace Chart
            fig_pace = px.line(df_s, x='Lap', y='LapSeconds', title="Stint Pace Evolution", 
                               markers=True, template="plotly_dark", color_discrete_sequence=['#00a2ff'])
            fig_pace.add_hline(y=m['avg_pace'], line_dash="dash", line_color="white", annotation_text="Avg Pace")
            st.plotly_chart(fig_pace, use_container_width=True)

            # Sector Consistency
            st.subheader("Sector Breakdown")
            sec_cols = ['Sector 1', 'Sector 2', 'Sector 3']
            for col in sec_cols: df_s[col] = df_s[col].apply(lap_to_seconds)
            
            fig_sectors = px.box(df_s, y=sec_cols, template="plotly_dark", title="Sector Consistency (Lower is better)")
            st.plotly_chart(fig_sectors, use_container_width=True)
        else:
            st.warning("Upload a Session Summary CSV to see stint pace and fuel data.")

    # --- TAB: DRIVER COACH (LOGIC) ---
    with tab_coach:
        if file_d:
            df_t = process_telemetry(pd.read_csv(file_d))
            st.header("AI Coaching Insights")
            
            # Logic: Coasting Detection
            coast_mask = (df_t['Throttle'] < 5) & (df_t['Brake'] < 5)
            coast_time = coast_mask.mean() * 100
            
            # Logic: ABS Overuse
            abs_usage = (df_t['ABSActive'] > 0).sum()
            
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if coast_time > 15:
                    st.error(f"**Coasting Alert ({coast_time:.1f}%):** You are 'parking' the car mid-corner. Transition faster from brake to throttle.")
                else:
                    st.success(f"**Pedal Efficiency:** Good. Coasting is at {coast_time:.1f}%.")
                
                if abs_usage > 500:
                    st.warning("**ABS Over-reliance:** You are leaning on the ABS too hard. This will kill your front tires in a long stint.")
            
            with col_c2:
                # Traction Circle
                fig_gg = px.scatter(df_t, x='LatAccel', y='LongAccel', color='Speed', 
                                    range_x=[-3,3], range_y=[-3,3], template="plotly_dark", title="G-G Diagram (Traction Circle)")
                st.plotly_chart(fig_gg, use_container_width=True)
        else:
            st.info("Upload Telemetry CSV for Driver Coaching.")

    # --- TAB: SETUP LAB ---
    with tab_setup:
        if file_d:
            st.header("Mechanical Balance Analysis")
            # Understeer Gradient: Steering Angle vs Lateral G
            fig_setup = px.scatter(df_t, x='LatAccel', y='SteeringWheelAngle', color='Speed', 
                                   template="plotly_dark", title="Steering vs Lateral G (Balance Signature)")
            st.plotly_chart(fig_setup, use_container_width=True)
            st.caption("If the line curves upward at high Gs, the car is understeering. If it flattens, it's oversteering.")
        else:
            st.info("Upload Telemetry CSV for Setup Analysis.")

    # --- TAB: TELEMETRY (SINGLE LAP) ---
    with tab_telemetry:
        if file_d and file_b:
            st.write("Standard 8-row Telemetry Stack Active.")
            # [Insert the Plotly make_subplots code from the previous response here]
        else:
            st.info("Upload Driver and Benchmark Telemetry for 1:1 comparison.")

if __name__ == "__main__":
    main()
