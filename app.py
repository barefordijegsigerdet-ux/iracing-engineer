import streamlit as st
import pandas as pd
from streamlit_plotly_events import plotly_events
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_main_telemetry, create_track_map

st.set_page_config(page_title="RaceEngineer AI", layout="wide")

# Tving CSS til at holde en fast højde på komponenterne (vigtigt for plotly_events)
st.markdown("""
    <style>
    .element-container iframe {
        height: 800px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Session state til at holde styr på musens position på banen
if "hover_dist" not in st.session_state:
    st.session_state.hover_dist = 0

st.sidebar.title("🏁 iRacing Telemetry")
u_file = st.sidebar.file_uploader("Upload Your Lap (CSV)", type="csv")
r_file = st.sidebar.file_uploader("Upload Reference Lap (CSV)", type="csv")

if u_file and r_file:
    # 1. Load data
    u_df, r_df = load_and_process_data(u_file, r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🗺️ Full Map", "🏎️ Tires", "🧠 Coach"])

    with t1:
        col_graphs, col_map = st.columns([3, 1])

        with col_graphs:
            # Generer telemetri figuren
            fig_tele = create_main_telemetry(u_df, r_df)
            
            # Brug plotly_events til at fange hover (svæv med musen)
            # override_height sikrer at grafen ikke kollapser til 0px
            selected_point = plotly_events(
                fig_tele,
                click_event=False,
                hover_event=True,
                override_height=800,
                key="tele_main_hover"
            )

            # Hvis musen svæver over et punkt, gem distancen og opdater siden
            if selected_point:
                new_dist = selected_point[0]['x']
                if abs(new_dist - st.session_state.hover_dist) > 1: # Undgå unødvendige opdateringer
                    st.session_state.hover_dist = new_dist
                    st.rerun()

        with col_map:
            st.write("### Track Position")
            # Tegn kortet med den røde prik baseret på hover_dist
            fig_map = create_track_map(u_df, r_df, st.session_state.hover_dist)
            st.plotly_chart(fig_map, use_container_width=True, key="side_track_map")
            
            st.metric("Current Distance", f"{st.session_state.hover_dist:.0f} m")
            
            # Tilføj evt. live delta hvis det findes i din dataframe
            idx = (u_df['distance'] - st.session_state.hover_dist).abs().idxmin()
            current_delta = u_df.loc[idx, 'delta']
            st.metric("Delta", f"{current_delta:.3f} s", delta_color="inverse")

else:
    st.header("Velkommen til RaceEngineer AI")
    st.info("Upload din egen omgang og en reference-omgang i sidebaren for at begynde analysen.")
