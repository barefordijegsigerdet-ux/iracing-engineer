import streamlit as st
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics, get_sector_analysis
from components.charts import create_main_telemetry, create_friction_circle, create_track_map

st.set_page_config(page_title="Race Engineer Pro", layout="wide")

# Sidebar
with st.sidebar:
    st.header("Upload Laps")
    u_file = st.file_uploader("Your Lap", type="csv")
    r_file = st.file_uploader("Reference Lap", type="csv")
    speed_mode = st.selectbox("Speed Override", ["Auto-detect", "mph → km/h", "m/s → km/h"])

if u_file and r_file:
    u_df = load_and_process_data(u_file, speed_mode)
    r_df = load_and_process_data(r_file, speed_mode)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    # Tabs
    t1, t2, t3 = st.tabs(["📊 Telemetry", "⭕ G-G Circle", "🗺️ Track Map"])

    with t1:
        st.plotly_chart(create_main_telemetry(u_df, r_df), use_container_width=True)
    
    with t2:
        c1, c2 = st.columns([1, 1])
        c1.plotly_chart(create_friction_circle(u_df, r_df))
        c2.subheader("Sector Breakdown")
        c2.table(get_sector_analysis(u_df))

    with t3:
        # Check if GPS data is valid and not just all zeros
        has_gps = "lat" in u_df.columns and "lon" in u_df.columns and u_df["lat"].abs().sum() > 0
        
        if has_gps:
            st.plotly_chart(create_track_map(u_df), use_container_width=True)
        else:
            st.info("🛰️ No valid GPS data (Lat/Lon) found in this telemetry file.")
