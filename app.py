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
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #00d1ff; }
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        </style>
    """, unsafe_allow_html=True)

# --- REFINED DATA PROCESSING ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes Garage 61 CSV data for the interpolation engine.
    """
    df.columns = [c.strip() for c in df.columns]
    
    required = ['LapDistPct', 'Speed', 'Throttle', 'Brake']
    for col in required:
        if col not in df.columns:
            st.error(f"Missing column: {col}")
            st.stop()

    # Cast to numeric
    for col in required:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['LapDistPct'])

    # DATA NORMALIZATION: Ensure LapDistPct is 0.0 to 1.0
    if df['LapDistPct'].max() > 1.1:
        df['LapDistPct'] = df['LapDistPct'] / 100.0
    
    # Scale Throttle/Brake to 0-100
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1:
            df[col] = df[col] * 100.0

    # Sort and drop duplicates for np.interp
    df = df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])
    
    return df[required]

def align_and_resample(driver_df: pd.DataFrame, bench_df: pd.DataFrame, samples: int = 5000):
    """
    Creates a common 0.0 -> 1.0 spatial grid and maps both laps to it.
    """
    # Grid is 0.0 to 1.0 to match normalized LapDistPct
    grid = np.linspace(0, 1, samples)
    
    def interpolate_lap(df):
        resampled = pd.DataFrame({'LapDistPct': grid})
        for col in ['Speed', 'Throttle', 'Brake']:
            resampled[col] = np.interp(grid, df['LapDistPct'], df[col])
        return resampled

    return interpolate_lap(driver_df), interpolate_lap(bench_df), grid

def calculate_time_delta(driver_df: pd.DataFrame, bench_df: pd.DataFrame, grid: np.array):
    """
    Calculates time delta based on speed (m/s) and distance.
    """
    v_driver = np.maximum(driver_df['Speed'].values / 3.6, 0.5)
    v_bench = np.maximum(bench_df['Speed'].values / 3.6, 0.5)
    
    # Calculate ds (change in distance in meters) 
    # We use 5000m as a proxy for an average GT3 lap length for delta scaling
    track_length_estimate = 5000 
    ds = np.diff(grid, prepend=0) * track_length_estimate
    
    dt_driver = ds / v_driver
    dt_bench = ds / v_bench
    
    return np.cumsum(dt_driver - dt_bench)

# --- APP LAYOUT ---

def main():
    apply_custom_css()
    st.title("🏎️ Telemetry Lab | MVP")
    
    st.sidebar.header("Data Ingestion")
    driver_file = st.sidebar.file_uploader("Upload Driver Lap", type=['csv'])
    bench_file = st.sidebar.file_uploader("Upload Benchmark Lap", type=['csv'])
    
    if driver_file and bench_file:
        # Data Pipeline
        df_d = process_telemetry(pd.read_csv(driver_file))
        df_b = process_telemetry(pd.read_csv(bench_file))
        
        res_d, res_b, grid = align_and_resample(df_d, df_b)
        delta = calculate_time_delta(res_d, res_b, grid)
        
        # UI Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Lap Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
        m2.metric("Driver Samples", len(df_d))
        m3.metric("Alignment Precision", f"{len(grid)} pts")

        # Telemetry Chart
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03,
            row_heights=[0.2, 0.3, 0.25, 0.25],
            subplot_titles=("Time Delta (s)", "Speed (km/h)", "Throttle (%)", "Brake (%)")
        )

        # Plotting
        # X is multiplied by 100 in the display only for readability (0-100%)
        display_x = grid * 100 
        
        # Row 1: Delta
        fig.add_trace(go.Scatter(x=display_x, y=delta, name="Delta", line=dict(color='#ff4b4b', width=2)), row=1, col=1)
        
        # Row 2: Speed
        fig.add_trace(go.Scatter(x=display_x, y=res_b['Speed'], name="Bench", line=dict(color='rgba(255,255,255,0.3)', dash='dash')), row=2, col=1)
        fig.add_trace(go.Scatter(x=display_x, y=res_d['Speed'], name="Driver", line=dict(color='#00d1ff', width=2)), row=2, col=1)
        
        # Row 3: Throttle
        fig.add_trace(go.Scatter(x=display_x, y=res_b['Throttle'], name="Bench", line=dict(color='rgba(255,255,255,0.3)', dash='dash')), row=3, col=1)
        fig.add_trace(go.Scatter(x=display_x, y=res_d['Throttle'], name="Driver", line=dict(color='#00ff41', width=2)), row=3, col=1)
        
        # Row 4: Brake
        fig.add_trace(go.Scatter(x=display_x, y=res_b['Brake'], name="Bench", line=dict(color='rgba(255,255,255,0.3)', dash='dash')), row=4, col=1)
        fig.add_trace(go.Scatter(x=display_x, y=res_d['Brake'], name="Driver", line=dict(color='#ff4b4b', width=2)), row=4, col=1)

        fig.update_layout(height=850, template="plotly_dark", showlegend=False, hovermode="x unified", margin=dict(t=50))
        fig.update_xaxes(title_text="Track Distance (%)", row=4, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("Awaiting telemetry CSV files from Garage 61.")

if __name__ == "__main__":
    main()
