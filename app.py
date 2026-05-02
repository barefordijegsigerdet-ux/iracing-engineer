import streamlit as st
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics, get_sector_analysis, get_coach_insights
from components.charts import create_main_telemetry, create_friction_circle, create_track_map

st.set_page_config(page_title="Race Engineer Pro", layout="wide")

st.sidebar.title("🏁 Lap Files")
u_file = st.sidebar.file_uploader("Upload Your Lap (CSV)", type="csv")
r_file = st.sidebar.file_uploader("Upload Reference (CSV)", type="csv")
speed_override = st.sidebar.selectbox("Speed Correction", ["Auto-detect", "mph → km/h", "m/s → km/h"])

if u_file and r_file:
    u_df = load_and_process_data(u_file, speed_override)
    r_df = load_and_process_data(r_file, speed_override)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    t1, t2, t3, t4 = st.tabs(["📊 Telemetry", "⭕ Physics", "🗺️ Track Map", "🧠 AI Coach"])

    with t1:
        st.plotly_chart(create_main_telemetry(u_df, r_df), use_container_width=True)
    with t2:
        col1, col2 = st.columns(2)
        col1.plotly_chart(create_friction_circle(u_df, r_df))
        col2.table(get_sector_analysis(u_df))
    with t3:
        if u_df["lat"].abs().sum() > 0:
            st.plotly_chart(create_track_map(u_df), use_container_width=True)
    with t4:
        st.subheader("Coach Observations")
        coach_data = get_coach_insights(u_df, r_df)
        for _, row in coach_data.iterrows():
            st.warning(f"**{row['Category']}**: {row['Observation']}")
            st.info(row['Advice'])
