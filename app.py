import streamlit as st
import plotly.graph_objects as go
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_main_telemetry, create_track_map

st.set_page_config(page_title="RaceEngineer AI", layout="wide")

# Session state til at holde styr på musens position
if "hover_dist" not in st.session_state:
    st.session_state.hover_dist = 0

st.sidebar.title("🏁 Session Data")
u_file = st.sidebar.file_uploader("Upload Your Lap (CSV)", type="csv")
r_file = st.sidebar.file_uploader("Upload Reference Lap (CSV)", type="csv")

if u_file and r_file:
    u_df, r_df = load_and_process_data(u_file, r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🗺️ Full Map", "🏎️ Tires", "🧠 Coach"])

    with t1:
        col_graphs, col_map = st.columns([3, 1])

        with col_graphs:
            fig_tele = create_main_telemetry(u_df, r_df)
            
            # Brug st.plotly_chart med eksplicit selection_mode
            event_data = st.plotly_chart(
                fig_tele, 
                use_container_width=True, 
                on_select="rerun", 
                selection_mode=["points"], # Vi vil kun have fat i punkter
                key="tele_main"
            )
            
            # Debugging: Hvis du vil se om den overhovedet fanger noget, 
            # kan du midlertidigt fjerne '#' fra linjen herunder:
            # st.write(event_data) 

            if event_data and "selection" in event_data:
                points = event_data["selection"].get("points", [])
                if points:
                    # Vi tager x-værdien fra det første punkt i listen
                    st.session_state.hover_dist = points[0].get("x", 0)
                    # Tving en opdatering af siden så kortet følger med
                    st.rerun()
                    
        with col_map:
            st.write("### Track Position")
            fig_map = create_track_map(u_df, r_df, st.session_state.hover_dist)
            st.plotly_chart(fig_map, use_container_width=True, key="side_map")
            
            st.metric("Dist", f"{st.session_state.hover_dist:.0f} m")
