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
        .main { background-color: #0e1117; color: #e0e0e0; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #00d1ff; }
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING ---

def process_telemetry(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """
    Cleans data and filters for a specific lap. 
    Garage 61 CSVs often contain the entire session.
    """
    df.columns = [c.strip() for c in df.columns]
    
    # Identify required columns
    # We prefer 'LapDist' (meters) over 'LapDistPct' for absolute accuracy
    req = ['LapDist', 'Speed', 'Throttle', 'Brake', 'Lap']
    for col in req:
        if col not in df.columns:
            # Fallback for G61 variations
            if col == 'LapDist' and 'LapDistPct' in df.columns:
                df['LapDist'] = df['LapDistPct']
            else:
                st.error(f"Missing column '{col}' in {label}")
                st.stop()

    # Numeric conversion
    for col in ['LapDist', 'Speed', 'Throttle', 'Brake']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # LAP FILTERING LOGIC
    # If multiple laps exist, we take the one with the most data (usually the active lap)
    # Or we can let the user choose. For MVP, we take the most frequent Lap index.
    target_lap = df['Lap'].mode()[0]
    df = df[df['Lap'] == target_lap].copy()

    # Final cleanup
    df = df.sort_values(by='LapDist').drop_duplicates(subset=['LapDist']).dropna()
    
    # Scale Throttle/Brake to 0-100
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1:
            df[col] *= 100
            
    return df

def align_and_resample(driver_df: pd.DataFrame, bench_df: pd.DataFrame, samples: int = 5000):
    """
    Resamples both laps to the Benchmark's total distance.
    """
    # Use the benchmark distance as the master spatial grid
    max_dist = bench_df['LapDist'].max()
    grid = np.linspace(0, max_dist, samples)
    
    def interpolate_lap(df):
        resampled = pd.DataFrame({'LapDist': grid})
        for col in ['Speed', 'Throttle', 'Brake']:
            resampled[col] = np.interp(grid, df['LapDist'], df[col])
        return resampled

    return interpolate_lap(driver_df), interpolate_lap(bench_df), grid

def calculate_time_delta(res_d, res_b, grid):
    """
    High-fidelity Time Delta calculation using meters and m/s.
    """
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0) # km/h to m/s
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    
    ds = np.diff(grid, prepend=0)
    
    dt_d = ds / v_d
    dt_b = ds / v_b
    
    return np.cumsum(dt_d - dt_b)

# --- UI: MAIN APP ---

def main():
    apply_custom_css()
    st.title("🏎️ Telemetry Lab | Pro Alignment")
    
    with st.sidebar:
        st.header("1. Data Ingestion")
        d_file = st.file_uploader("Driver Lap CSV", type=['csv'])
        b_file = st.file_uploader("Benchmark Lap CSV", type=['csv'])
        st.divider()
        st.info("Ensure CSVs are exports from individual laps or sessions.")

    if d_file and b_file:
        # 1. Process
        df_d_raw = process_telemetry(pd.read_csv(d_file), "Driver File")
        df_b_raw = process_telemetry(pd.read_csv(b_file), "Benchmark File")
        
        # 2. Resample (Synchronize spatial coordinates)
        res_d, res_b, grid = align_and_resample(df_d_raw, df_b_raw)
        
        # 3. Calculate Physics-based Delta
        delta = calculate_time_delta(res_d, res_b, grid)
        
        # 4. Visualization Layout
        st.subheader("Spatial Analysis")
        
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.04,
            row_heights=[0.15, 0.35, 0.25, 0.25],
            subplot_titles=("Time Delta (s)", "Speed (km/h)", "Throttle (%)", "Brake (%)")
        )

        # Plot Config
        x_km = grid / 1000 # Convert meters to KM for the X-axis
        
        # Delta Plot (Red)
        fig.add_trace(go.Scatter(x=x_km, y=delta, name="Delta", line=dict(color='#ff4b4b', width=2)), row=1, col=1)
        
        # Speed Plot (Blue/White)
        fig.add_trace(go.Scatter(x=x_km, y=res_b['Speed'], name="Benchmark", line=dict(color='white', dash='dash', width=1)), row=2, col=1)
        fig.add_trace(go.Scatter(x=x_km, y=res_d['Speed'], name="Driver", line=dict(color='#00d1ff', width=2)), row=2, col=1)
        
        # Throttle Plot (Green)
        fig.add_trace(go.Scatter(x=x_km, y=res_b['Throttle'], line=dict(color='white', dash='dash', width=1), opacity=0.3), row=3, col=1)
        fig.add_trace(go.Scatter(x=x_km, y=res_d['Throttle'], name="Throttle", line=dict(color='#00ff41', width=2)), row=3, col=1)
        
        # Brake Plot (Red)
        fig.add_trace(go.Scatter(x=x_km, y=res_b['Brake'], line=dict(color='white', dash='dash', width=1), opacity=0.3), row=4, col=1)
        fig.add_trace(go.Scatter(x=x_km, y=res_d['Brake'], name="Brake", line=dict(color='#ff2a2a', width=2)), row=4, col=1)

        fig.update_layout(height=900, template="plotly_dark", showlegend=False, hovermode="x unified", margin=dict(t=30, b=10))
        fig.update_xaxes(title_text="Distance (km)", row=4, col=1)
        
        st.plotly_chart(fig, use_container_width=True)

        # Engineering Feedback
        col1, col2, col3 = st.columns(3)
        col1.metric("Final Delta", f"{delta[-1]:.3f}s")
        col2.metric("Track Length", f"{grid[-1]:.0f}m")
        col3.metric("Data Density", f"{len(df_d_raw)} samples")

    else:
        st.warning("Please upload both CSV files to generate the engineering traces.")

if __name__ == "__main__":
    main()
