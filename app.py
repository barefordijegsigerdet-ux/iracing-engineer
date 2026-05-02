import streamlit as st
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_main_telemetry, create_track_map

st.set_page_config(page_title="RaceEngineer AI", layout="wide")

# Session state til interaktion
if "hover_dist" not in st.session_state:
    st.session_state.hover_dist = 0

st.sidebar.title("🏁 iRacing Engineer")
u_file = st.sidebar.file_uploader("Upload Your Lap (CSV)", type="csv")
r_file = st.sidebar.file_uploader("Upload Reference (CSV)", type="csv")

# AI API Key input i sidebaren
st.sidebar.divider()
ai_key = st.sidebar.text_input("AI Coach API Key", type="password", help="Indtast din OpenAI eller Google Gemini nøgle")

if u_file and r_file:
    u_df, r_df = load_and_process_data(u_file, r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🗺️ Full Map", "🏎️ Tires", "🧠 AI Coach"])

    with t1:
        col_graphs, col_map = st.columns([3, 1])

        with col_graphs:
            fig_tele = create_main_telemetry(u_df, r_df)
            
            # Bruger indbygget Streamlit interaktion (stabil)
            event_data = st.plotly_chart(
                fig_tele, 
                use_container_width=True, 
                on_select="rerun", 
                key="tele_dashboard"
            )
            
            # Opdater position ved klik/valg
            if event_data and "selection" in event_data and event_data["selection"]["points"]:
                st.session_state.hover_dist = event_data["selection"]["points"][0]["x"]

        with col_map:
            st.write("### Track Position")
            st.plotly_chart(create_track_map(u_df, r_df, st.session_state.hover_dist), use_container_width=True)
            
            # Live stats
            idx = (u_df['distance'] - st.session_state.hover_dist).abs().idxmin()
            st.metric("Distance", f"{st.session_state.hover_dist:.0f} m")
            st.metric("Delta", f"{u_df.loc[idx, 'delta']:.3f} s")

    with t4:
        st.header("🧠 AI Driver Coach")
        if not ai_key:
            st.warning("Indtast venligst en API-nøgle i sidebaren for at få AI-analyse.")
        else:
            st.info("AI'en er klar til at analysere din omgang...")
            # Her indsætter vi din AI-logik senere
