import streamlit as st

# Internal Modules
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_delta
from components.charts import create_telemetry_chart

def main():
    st.set_page_config(page_title="iRacing Race Engineer Pro", layout="wide")
    st.title("🏎️ Race Engineer Telemetry Analysis")
    
    st.sidebar.header("Upload Lap Data")
    st.sidebar.info("Upload CSV exports from Garage 61, VRS, or iRacing. The pipeline will auto-normalize headers.")

    user_file = st.sidebar.file_uploader("Upload YOUR Lap (CSV)", type=['csv'])
    ref_file = st.sidebar.file_uploader("Upload REFERENCE Lap (CSV)", type=['csv'])

    if user_file and ref_file:
        try:
            # 1. Safely Load and Normalize via Ingestion Module
            with st.spinner("Normalizing telemetry schemas..."):
                user_df = load_and_process_data(user_file)
                ref_df = load_and_process_data(ref_file)
                
            # 2. Physics / Math Processing via Physics Module
            with st.spinner("Calculating spatial deltas..."):
                if 'delta' not in user_df.columns:
                    delta_df = calculate_physics_delta(user_df, ref_df)
                else:
                    delta_df = user_df[['distance', 'delta']]

            # 3. Visualization via Charts Component
            st.subheader("Pillar Analysis: Data-Driven Performance")
            
            fig = create_telemetry_chart(user_df, ref_df, delta_df)
            st.plotly_chart(fig, use_container_width=True)

            # 4. Engineer Insights
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                st.header("Technical Observations")
                user_vmin, ref_vmin = user_df['speed'].min(), ref_df['speed'].min()
                
                if user_vmin < ref_vmin - 2.0: # 2km/h tolerance
                    st.error(f"⚠️ Over-slowed: Your vMin is {round(ref_vmin - user_vmin, 1)} km/h lower than the reference.")
                else:
                    st.success("✅ Minimum speed is competitive.")

            with col2:
                st.header("Actionable To-Do's")
                st.write("- **Check Braking Phase:** Look for where the red line (User) starts before the white dashed line.")
                st.write("- **Throttle Timing:** Identify if the green throttle line is rising later than the reference.")

        except KeyError as ke:
            st.error(f"❌ Schema Error: Missing vital telemetry column. {ke}")
        except ValueError as ve:
            st.error(f"❌ Processing Error: Unprocessable values in telemetry. {ve}")
        except Exception as e:
            st.error(f"❌ An unexpected application error occurred: {e}")
            
    else:
        # Safe Degradation State
        st.warning("Please upload both a User lap and a Reference lap to begin analysis.")
        st.info("The application expects a CSV containing at least: Distance, Speed, Throttle, and Brake.")

if __name__ == "__main__":
    main()
