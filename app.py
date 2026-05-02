import streamlit as st
import google.generativeai as genai
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_main_telemetry, create_track_map

st.set_page_config(page_title="RaceEngineer AI", layout="wide")

if "hover_dist" not in st.session_state:
    st.session_state.hover_dist = 0

st.sidebar.title("🏁 iRacing Engineer")
u_file = st.sidebar.file_uploader("Upload Your Lap (CSV)", type="csv")
r_file = st.sidebar.file_uploader("Upload Reference (CSV)", type="csv")

st.sidebar.divider()
st.sidebar.subheader("🤖 AI Settings")
ai_key = st.sidebar.text_input("Gemini API Key", type="password")

def get_ai_coaching(api_key, user_df, ref_df):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
    
    # Vi inkluderer nu 'gear' i sammendraget
    summary_data = user_df[['distance', 'speed', 'gear', 'throttle', 'brake', 'delta']].iloc[::25].to_csv()
    
    prompt = f"""
    Du er en Race Engineer AI. Analyser denne telemetri.
    Sammenlign brugerens kørsel med referencen.
    
    Fokusér specifikt på:
    1. Tidstab (Delta).
    2. Gearvalg: Bruger køreren et forkert gear i svingene (f.eks. 2. gear hvor ref bruger 3.)?
    3. Short-shifting: Skifter køreren gear for tidligt eller for sent?
    
    Giv konkrete tips til at vinde tid. Svar på dansk.
    
    Data:
    {summary_data}
    """
    response = model.generate_content(prompt)
    return response.text
if u_file and r_file:
    u_df, r_df = load_and_process_data(u_file, r_file)
    u_df, r_df = calculate_physics_metrics(u_df, r_df)

    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "🗺️ Full Map", "🏎️ Tires", "🧠 AI Coach"])

    with t1:
        col_graphs, col_map = st.columns([3, 1])
        with col_graphs:
            fig_tele = create_main_telemetry(u_df, r_df)
            event = st.plotly_chart(fig_tele, use_container_width=True, on_select="rerun", key="tele")
            if event and "selection" in event and event["selection"]["points"]:
                st.session_state.hover_dist = event["selection"]["points"][0]["x"]
                st.rerun()

        with col_map:
            st.plotly_chart(create_track_map(u_df, r_df, st.session_state.hover_dist), use_container_width=True)
            idx = (u_df['distance'] - st.session_state.hover_dist).abs().idxmin()
            st.metric("Distance", f"{st.session_state.hover_dist:.0f} m")
            st.metric("Delta", f"{u_df.loc[idx, 'delta']:.3f} s")

    with t4:
        st.header("🧠 AI Driver Coach")
        if not ai_key:
            st.warning("Indtast venligst din Gemini API-nøgle i sidebaren.")
        else:
            if st.button("Generér Analyse"):
                with st.spinner("Gemini analyserer din omgang..."):
                    try:
                        feedback = get_ai_coaching(ai_key, u_df, r_df)
                        st.markdown(feedback)
                    except Exception as e:
                        st.error(f"Fejl i AI-opkald: {e}")
