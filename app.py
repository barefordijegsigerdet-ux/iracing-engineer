import streamlit as st
from streamlit_plotly_events import plotly_events # Husk at importere denne!
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_main_telemetry, create_track_map

st.set_page_config(page_title="RaceEngineer AI", layout="wide")

# Session state til at holde styr på musens position
if "hover_dist" not in st.session_state:
    st.session_state.hover_dist = 0

# ... (din file uploader kode)

if u_file and r_file:
    u_df, r_df = load_and_process_data(u_file, r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🗺️ Full Map", "🏎️ Tires", "🧠 Coach"])

    with t1:
        col_graphs, col_map = st.columns([3, 1])

        with col_graphs:
            # Fang hover-events fra telemetrien
            hover_data = plotly_events(
                create_main_telemetry(u_df, r_df),
                click_event=False,
                hover_event=True,
                override_height=800,
                key="tele_charts"
            )
            
            # Opdater position hvis musen bevæger sig
            if hover_data:
                st.session_state.hover_dist = hover_data[0]['x']

        with col_map:
            st.write("### Track Position")
            # Tegn kortet med den aktuelle hover_dist
            fig_map = create_track_map(u_df, r_df, st.session_state.hover_dist)
            st.plotly_chart(fig_map, use_container_width=True, key="side_map")
            
            st.metric("Dist", f"{st.session_state.hover_dist:.0f} m")
