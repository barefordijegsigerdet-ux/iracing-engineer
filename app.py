import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION & UI SETUP ---
st.set_page_config(page_title="Race Engineer | Telemetry Lab", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 5px; }
        </style>
    """, unsafe_allow_html=True)

# --- CORE LOGIC FUNCTIONS ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and casts Garage 61 telemetry data.
    Ensures critical sensors are treated as floats.
    """
    expected_cols = ['LapDistPct', 'Speed', 'Throttle', 'Brake']
    # Check for presence of columns
    for col in expected_cols:
        if col not in df.columns:
            st.error(f"Missing critical column: {col}")
            st.stop()
            
    # Cast to float and handle potential string formatting from CSV
    for col in expected_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    return df[expected_cols]

def align_and_resample(driver_df: pd.DataFrame, bench_df: pd.DataFrame, samples: int = 5000):
    """
    Resamples both laps to a common 5,000 point spatial baseline using LapDistPct.
    This allows for 1:1 row comparison and Time Delta calculation.
    """
    # Define common spatial baseline (0 to 1.0)
    grid = np.linspace(0, 1, samples)
    
    def interpolate_lap(df):
        resampled = pd.DataFrame({'LapDistPct': grid})
        for col in ['Speed', 'Throttle', 'Brake']:
            resampled[col] = np.interp(grid, df['LapDistPct'], df[col])
        return resampled

    return interpolate_lap(driver_df), interpolate_lap(bench_df), grid

def calculate_time_delta(driver_df: pd.DataFrame, bench_df: pd.DataFrame, grid: np.array):
    """
    Calculates cumulative time delta.
    Logic: dt = ds / v. We assume a normalized track length for delta visualization.
    Note: Speed is converted from km/h to m/s for physics accuracy.
    """
    # Convert km/h to m/s
    v_driver = driver_df['Speed'].values / 3.6
    v_bench = bench_df['Speed'].values / 3.6
    
    # Avoid division by zero
    v_driver = np.where(v_driver < 0.5, 0.5, v_driver)
    v_bench = np.where(v_bench < 0.5, 0.5, v_bench)
    
    # Calculate incremental distance (assuming arbitrary 1000m for scaling, 
    # but since it's % based, the relative delta remains accurate)
    ds = np.diff(grid, prepend=0)
    
    # Time = Distance / Speed. We calculate relative time spent in each slice.
    dt_driver = ds / v_driver
    dt_bench = ds / v_bench
    
    # Cumulative sum of the difference
    delta = np.cumsum(dt_driver - dt_bench)
    
    # Scale to typical lap lengths (Garage 61 doesn't always export total distance)
    # This provides a normalized 'Time Lost/Gained' trend
    return delta

# --- MAIN APP LOGIC ---

def main():
    apply_custom_css()
    st.title("🏎️ Telemetry Lab | MVP")
    st.sidebar.header("Data Ingestion")
    
    # 1. File Uploaders
    driver_file = st.sidebar.file_uploader("Upload Driver Lap (CSV)", type=['csv'])
    bench_file = st.sidebar.file_uploader("Upload Benchmark Lap (CSV)", type=['csv'])
    
    if driver_file and bench_file:
        # Load data
        df_d_raw = pd.read_csv(driver_file)
        df_b_raw = pd.read_csv(bench_file)
        
        # Process and Clean
        df_d = process_telemetry(df_d_raw)
        df_b = process_telemetry(df_b_raw)
        
        # Resample to 5000 points
        resampled_d, resampled_b, spatial_grid = align_and_resample(df_d, df_b)
        
        # Calculate Delta
        delta = calculate_time_delta(resampled_d, resampled_b, spatial_grid)
        resampled_d['Delta'] = delta

        # Dashboard Tabs
        tab_traces, tab_analysis = st.tabs(["📊 Telemetry Traces", "🔬 Technical Analysis"])
        
        with tab_traces:
            # Vertical Stacked Charts
            fig = make_subplots(
                rows=4, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.02,
                row_heights=[0.2, 0.3, 0.25, 0.25],
                subplot_titles=("Time Delta (s)", "Speed (km/h)", "Throttle (%)", "Brake (%)")
            )
            
            # Subplot 1: Time Delta
            fig.add_trace(go.Scatter(x=spatial_grid, y=resampled_d['Delta'], name="Delta", line=dict(color='#ff4b4b')), row=1, col=1)
            
            # Subplot 2: Speed
            fig.add_trace(go.Scatter(x=spatial_grid, y=resampled_b['Speed'], name="Bench Speed", line=dict(color='white', dash='dash', width=1)), row=2, col=1)
            fig.add_trace(go.Scatter(x=spatial_grid, y=resampled_d['Speed'], name="Driver Speed", line=dict(color='#00d1ff')), row=2, col=1)
            
            # Subplot 3: Throttle
            fig.add_trace(go.Scatter(x=spatial_grid, y=resampled_b['Throttle'], name="Bench Throttle", line=dict(color='white', dash='dash', width=1)), row=3, col=1)
            fig.add_trace(go.Scatter(x=spatial_grid, y=resampled_d['Throttle'], name="Driver Throttle", line=dict(color='#00ff41')), row=3, col=1)
            
            # Subplot 4: Brake
            fig.add_trace(go.Scatter(x=spatial_grid, y=resampled_b['Brake'], name="Bench Brake", line=dict(color='white', dash='dash', width=1)), row=4, col=1)
            fig.add_trace(go.Scatter(x=spatial_grid, y=resampled_d['Brake'], name="Driver Brake", line=dict(color='#ff4b4b')), row=4, col=1)
            
            fig.update_layout(height=800, template="plotly_dark", showlegend=False, margin=dict(l=50, r=50, t=30, b=50))
            fig.update_xaxes(title_text="Track Progress (%)", row=4, col=1)
            
            st.plotly_chart(fig, use_container_width=True)

        with tab_analysis:
            st.info("Analysis modules (G-Sum, ABS/TC detection) will be implemented in the next iteration.")
            st.write("Initial alignment complete. Scoped variables ready for diagnostic logic.")
            
    else:
        st.info("Waiting for telemetry files. Please upload CSV exports from Garage 61.")
        st.image("https://images.unsplash.com/photo-1594735297214-5d9444bc2b6b?auto=format&fit=crop&q=80&w=2000", caption="Engineering Logic Engine Standby")

if __name__ == "__main__":
    main()
