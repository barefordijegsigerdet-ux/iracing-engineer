import streamlit as st
import numpy as np

# Internal Modules
from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_telemetry_chart

def main():
    st.set_page_config(page_title="G61 Telemetry Analysis", layout="wide")
    st.title("🏎️ Professional Telemetry Analysis")
    
    st.sidebar.header("Upload Lap Data")
    user_file = st.sidebar.file_uploader("Upload YOUR Lap (CSV)", type=['csv'])
    ref_file = st.sidebar.file_uploader("Upload REFERENCE Lap (CSV)", type=['csv'])

    if user_file and ref_file:
        try:
            # 1. Ingest & Safe Load
            with st.spinner("Parsing & Downsampling CSVs..."):
                user_df = load_and_process_data(user_file)
                ref_df = load_and_process_data(ref_file)
                
            # 2. Advanced Physics & Math Alignment
            with st.spinner("Calculating Delta & G-Sum..."):
                user_df, ref_df = calculate_physics_metrics(user_df, ref_df)

            # 3. Visualization
            st.subheader("Data-Driven Performance Review")
            fig = create_telemetry_chart(user_df, ref_df)
            st.plotly_chart(fig, use_container_width=True)

            # 4. G-Sum Engineer Insights
            st.divider()
            st.header("Technical Observations")
            
            # G-Sum under-driving logic
            avg_g_user = user_df['g_sum'].mean()
            avg_g_ref = ref_df['g_sum'].mean()
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("**G-Sum (Tire Utilization)**")
                if avg_g_user < avg_g_ref - 0.1:
                    st.error(f"⚠️ Under-driving detected. Your average G-Sum ({avg_g_user:.2f}G) is significantly lower than the reference ({avg_g_ref:.2f}G). You are leaving grip on the table in the corners.")
                else:
                    st.success("✅ Good tire utilization. You are matching the reference car's G-Sum profile.")

        except Exception as e:
            st.error(f"❌ Pipeline Error: {e}")
            
    else:
        st.info("Upload two telemetry CSVs (User and Reference) to view the Garage61-style analysis.")

if __name__ == "__main__":
    main()
