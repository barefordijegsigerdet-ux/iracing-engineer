import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Race Engineer | Telemetry Lab", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 5px; }
        </style>
    """, unsafe_allow_html=True)

# --- REFINED DATA PROCESSING ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans, casts, and sorts Garage 61 telemetry data.
    """
    # Standardize column names (handling potential case sensitivity)
    df.columns = [c.strip() for c in df.columns]
    
    # Required columns for the MVP
    required = ['LapDistPct', 'Speed', 'Throttle', 'Brake']
    for col in required:
        if col not in df.columns:
            st.error(f"Critical Error: Column '{col}' missing from CSV.")
            st.stop()

    # Convert to numeric, drop rows with NaN in LapDistPct
    for col in required:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['LapDistPct'])

    # CRITICAL: Sort by distance and remove duplicates for interpolation
    df = df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])
    
    # Scale Throttle/Brake to 0-100 if they are in 0-1 format
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1: # Threshold to detect 0-1 scaling
            df[col] = df[col] * 100

    return df[required]

def align_and_resample(driver_df: pd.DataFrame, bench_df: pd.DataFrame, samples: int = 5000):
    """
    High-precision resampling to a common spatial grid.
    """
    grid = np.linspace(0, 100, samples) # LapDistPct is usually 0-100
    
    def interpolate_lap(df):
        resampled = pd.DataFrame({'LapDistPct': grid})
        # Use np.interp on sorted data
        for col in ['Speed', 'Throttle', 'Brake']:
            resampled[col] = np.interp(grid, df['LapDistPct'], df[col])
        return resampled

    return interpolate_lap(driver_df), interpolate_lap(bench_df), grid

def calculate_time_delta(driver_df: pd.DataFrame, bench_df: pd.DataFrame, grid: np.array):
    """
    Calculates time delta based on speed and distance change.
    """
    v_driver = driver_df['Speed'].values / 3.6 # km/h to m/s
    v_bench = bench_df['Speed'].values / 3.6
    
    # Floor speed to avoid infinity (0.5 m/s minimum)
    v_driver = np.maximum(v_driver, 0.5)
    v_bench = np.maximum(v_bench, 0.5)
    
    # ds = change in % * estimated lap length (normalized to 1000m for relative delta)
    # The absolute lap length doesn't change the shape of the delta curve.
    ds = np.diff(grid, prepend=0) * 10 
    
    dt_driver = ds / v_driver
    dt_bench = ds / v_bench
    
    return np.cumsum(dt_driver - dt_bench)

# --- UI LOGIC ---

def main():
    apply_custom_css()
    st.title("🏎️ Telemetry Lab | MVP")
    
    st.sidebar.header("Data Ingestion")
    driver_file = st.sidebar.file_uploader("Upload Driver Lap", type=['csv'])
    bench_file = st.sidebar.file_uploader("Upload Benchmark Lap", type=['csv'])
    
    if driver_file and bench_file:
        # Load and clean
        df_d = process_telemetry(pd.read_csv(driver_file))
        df_b = process_telemetry(pd.read_csv(bench_file))
        
        # Resample
        res_d, res_b, grid = align_and_resample(df_d, df_b)
        
        # Delta
        delta = calculate_time_delta(res_d, res_b, grid)
        
        # Visualization
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03,
            row_heights=[0.2, 0.3, 0.25, 0.25],
            subplot_titles=("Time Delta (s)", "Speed (km/h)", "Throttle (%)", "Brake (%)")
        )

        # Plotting Logic
        colors = {'driver': '#00d1ff', 'bench': '#ffffff', 'delta': '#ff4b4b'}
        
        # Time Delta
        fig.add_trace(go.Scatter(x=grid, y=delta, name="Delta", line=dict(color=colors['delta'], width=2)), row=1, col=1)
        
        # Speed
        fig.add_trace(go.Scatter(x=grid, y=res_b['Speed'], name="Bench", line=dict(color=colors['bench'], dash='dash', width=1)), row=2, col=1)
        fig.add_trace(go.Scatter(x=grid, y=res_d['Speed'], name="Driver", line=dict(color=colors['driver'], width=2)), row=2, col=1)
        
        # Throttle
        fig.add_trace(go.Scatter(x=grid, y=res_b['Throttle'], name="Bench T", line=dict(color=colors['bench'], dash='dash', width=1)), row=3, col=1)
        fig.add_trace(go.Scatter(x=grid, y=res_d['Throttle'], name="Driver T", line=dict(color='#00ff41', width=2)), row=3, col=1)
        
        # Brake
        fig.add_trace(go.Scatter(x=grid, y=res_b['Brake'], name="Bench B", line=dict(color=colors['bench'], dash='dash', width=1)), row=4, col=1)
        fig.add_trace(go.Scatter(x=grid, y=res_d['Brake'], name="Driver B", line=dict(color='#ff4b4b', width=2)), row=4, col=1)

        fig.update_layout(height=900, template="plotly_dark", showlegend=False, hovermode="x unified")
        fig.update_yaxes(range=[0, 105], row=3, col=1) # Throttle %
        fig.update_yaxes(range=[0, 105], row=4, col=1) # Brake %
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Health Check Metrics
        cols = st.columns(3)
        cols[0].metric("Driver Data Points", len(df_d))
        cols[1].metric("Benchmark Data Points", len(df_b))
        cols[2].metric("Resampled Points", len(grid))

    else:
        st.info("Upload two CSV files to begin analysis.")

if __name__ == "__main__":
    main()
