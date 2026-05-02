import streamlit as st
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_main_telemetry, create_track_map

st.set_page_config(page_title="RaceEngineer AI", layout="wide")

# Initialiser session state til synkronisering
if "hover_dist" not in st.session_state:
    st.session_state.hover_dist = 0

st.sidebar.title("🏁 iRacing Engineer")
u_file = st.sidebar.file_uploader("Upload Your Lap (CSV)", type="csv")
r_file = st.sidebar.file_uploader("Upload Reference (CSV)", type="csv")

st.sidebar.divider()
st.sidebar.subheader("🤖 AI Driver Coach")
# Anbefalet: Brug Gemini 3.1 Flash Lite for flest gratis uses
ai_key = st.sidebar.text_input("Gemini API Key", type="password", help="Hent din nøgle hos Google AI Studio")

if u_file and r_file:
    u_df, r_df = load_and_process_data(u_file, r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🗺️ Full Map", "🏎️ Tires", "🧠 AI Coach"])

    with t1:
        col_graphs, col_map = st.columns([3, 1])

        with col_graphs:
            fig_tele = create_main_telemetry(u_df, r_df)
            
            # Vi bruger on_select="rerun" for at fange interaktion
            event_data = st.plotly_chart(
                fig_tele, 
                use_container_width=True, 
                on_select="rerun", 
                key="tele_sync_main"
            )
            
            # Tving synkronisering mellem graf og kort
            if event_data and "selection" in event_data and event_data["selection"]["points"]:
                new_dist = event_data["selection"]["points"][0]["x"]
                if new_dist != st.session_state.hover_dist:
                    st.session_state.hover_dist = new_dist
                    st.rerun() 

        with col_map:
            st.write("### Track Position")
            # Kortet opdateres nu øjeblikkeligt pga. st.rerun()
            fig_map = create_track_map(u_df, r_df, st.session_state.hover_dist)
            st.plotly_chart(fig_map, use_container_width=True, key="map_sync_side")
            
            # Metrics
            idx = (u_df['distance'] - st.session_state.hover_dist).abs().idxmin()
            st.metric("Distance", f"{st.session_state.hover_dist:.0f} m")
            st.metric("Delta", f"{u_df.loc[idx, 'delta']:.3f} s")

    with t4:
        st.header("🧠 AI Driver Coach (Gemini 3.1 Flash Lite)")
        if not ai_key:
            st.warning("Indtast venligst din Gemini API-nøgle i sidebaren for at få adgang.")
        else:
            if st.button("Analysér min kørsel"):
                with st.spinner("AI'en beregner dine fejl..."):
                    # Placeholder for AI kald
                    st.success("AI Coach er klar. Skal vi sende data nu?")

else:
    st.info("Upload dine CSV-filer for at starte.")
