import streamlit as st
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics, get_coach_insights
from components.charts import create_main_telemetry, create_friction_circle, create_track_map

st.set_page_config(page_title="RaceEngineer AI", layout="wide")

st.sidebar.title("🏁 Session Data")
u_file = st.sidebar.file_uploader("Upload Your Lap (CSV)", type="csv")
r_file = st.sidebar.file_uploader("Upload Reference Lap (CSV)", type="csv")

# ... (dine imports forbliver de samme)

if u_file and r_file:
    with st.spinner("Analyzing..."):
        u_df, r_df = load_and_process_data(u_file, r_file)
        u_df, r_df = calculate_physics_metrics(u_df, r_df)

    # Vi beholder fanerne, men ændrer indholdet i t1
    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🗺️ Full Track Map", "🏎️ Tire Usage", "🧠 AI Coach"])

    with t1:
        # Lav to kolonner: en bred til grafer og en smal til kortet
        col_graphs, col_map = st.columns([3, 1]) 

        with col_graphs:
            st.plotly_chart(create_main_telemetry(u_df, r_df), use_container_width=True)
        
        with col_map:
            st.write("### Track Position")
            # Vi gør kortet lidt mindre her, så det passer til siden
            st.plotly_chart(create_track_map(u_df, r_df), use_container_width=True)
            
            # Du kan evt. tilføje live stats under kortet her
            st.metric("Current Delta", f"{u_df['delta'].iloc[-1]:.3f} s")

    with t2:
        # En stor version af kortet hvis man vil nørde detaljer
        st.plotly_chart(create_track_map(u_df, r_df), use_container_width=True)

    # ... (resten af dine tabs t3 og t4 forbliver de samme)
    with t3: st.plotly_chart(create_friction_circle(u_df, r_df))
    with t4:
        st.subheader("Coach Observations")
        insights = get_coach_insights(u_df, r_df)
        for _, row in insights.iterrows():
            st.warning(f"**{row['Category']}**: {row['Observation']}")
            st.info(row['Advice'])
else:
    st.info("Please upload both laps to begin.")
