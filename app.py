import streamlit as st
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics, get_coach_insights
from components.charts import create_main_telemetry, create_friction_circle, create_track_map

st.set_page_config(page_title="RaceEngineer AI", layout="wide", page_icon="🏎️")

st.sidebar.title("🏁 Session Data")
u_file = st.sidebar.file_uploader("Upload Your Lap (CSV)", type="csv")
r_file = st.sidebar.file_uploader("Upload Reference Lap (CSV)", type="csv")

if u_file and r_file:
    with st.spinner("Analyzing telemetry..."):
        # This one line now handles both files based on our new ingestion.py
        u_df, r_df = load_and_process_data(u_file, r_file)
        
        # Then proceed with physics
        u_df, r_df = calculate_physics_metrics(u_df, r_df)

    t1, t2, t3, t4 = st.tabs(["📊 Telemetry", "🗺️ Driving Line", "🏎️ Tire Usage", "🧠 AI Coach"])

    with t1:
        st.plotly_chart(create_main_telemetry(u_df, r_df), use_container_width=True)
    with t2:
        st.plotly_chart(create_track_map(u_df, r_df), use_container_width=True)
    with t3:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.plotly_chart(create_friction_circle(u_df, r_df))
        with col2:
            st.write("### How to read this:")
            st.write("The outer edges represent the limit of your tires.")
            st.write("- **Red (Ref):** Professional threshold.")
            st.write("- **Blue (You):** Your actual performance.")
            st.info("If your blue markers don't reach as far out as the red ones, you aren't using all the available grip.")
    with t4:
        st.subheader("Coach Observations")
        insights = get_coach_insights(u_df, r_df)
        for _, row in insights.iterrows():
            st.warning(f"**{row['Category']}**: {row['Observation']}")
            st.info(row['Advice'])
else:
    st.info("Please upload both your lap and a reference lap to begin analysis.")
