import streamlit as st
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics, get_coach_insights
from components.charts import create_main_telemetry, create_friction_circle, create_track_map

st.set_page_config(page_title="iRacing Engineer Pro", layout="wide")

st.sidebar.title("🏁 Upload Laps")
u_file = st.sidebar.file_uploader("Your Lap", type="csv")
r_file = st.sidebar.file_uploader("Reference Lap", type="csv")

if u_file and r_file:
    u_df = load_and_process_data(u_file)
    r_df = load_and_process_data(r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    t1, t2, t3, t4 = st.tabs(["📊 Telemetry", "🏎️ Tire Usage", "🗺️ Driving Line", "🧠 Coach"])

    with t1:
        st.plotly_chart(create_main_telemetry(u_df, r_df), use_container_width=True)
    with t2:
        st.subheader("Friction Circle Analysis")
        st.plotly_chart(create_friction_circle(u_df, r_df))
    with t3:
        st.plotly_chart(create_track_map(u_df, r_df), use_container_width=True)
    with t4:
        st.subheader("Coach Observations")
        coach_df = get_coach_insights(u_df, r_df)
        for _, row in coach_df.iterrows():
            st.warning(f"**{row['Category']}**: {row['Observation']}")
            st.info(row['Advice'])
