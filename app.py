import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Lead Architect | Telemetry Lab", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; }
        .stMetric { background-color: #1c2128; border: 1px solid #30363d; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans data using available headers: Speed, LapDistPct, Brake, Throttle, etc.
    """
    df.columns = [c.strip() for c in df.columns]
    
    # Required for the engine
    req = ['LapDistPct', 'Speed', 'Throttle', 'Brake', 'RPM', 'Gear', 'SteeringWheelAngle', 'ABSActive']
    for col in req:
        if col not in df.columns:
            # Create dummy for ABS if missing, otherwise fail
            if col == 'ABSActive': df['ABSActive'] = 0
            else:
                st.error(f"Missing column: {col}")
                st.stop()

    # Numeric conversion
    for col in req:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # LAP SLICING LOGIC
    # If the file contains multiple laps, LapDistPct will reset (e.g., 99 -> 1)
    # We find the first reset and take only that slice.
    reset_points = df.index[df['LapDistPct'].diff() < -0.5].tolist()
    if reset_points:
        df = df.iloc[:reset_points[0]].copy()

    # Ensure 0.0 - 1.0 range for interpolation
    if df['LapDistPct'].max() > 1.1:
        df['LapDistPct'] = df['LapDistPct'] / 100.0

    # Clean for interpolation
    df = df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])
    
    # Scale Throttle/Brake to 0-100
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1: df[col] *= 100
            
    return df[req]

def align_and_resample(driver_df: pd.DataFrame, bench_df: pd.DataFrame, samples: int = 5000):
    grid = np.linspace(0, 1, samples)
    
    def interpolate_lap(df):
        resampled = pd.DataFrame({'LapDistPct': grid})
        cols_to_interp = ['Speed', 'Throttle', 'Brake', 'RPM', 'Gear', 'SteeringWheelAngle', 'ABSActive']
        for col in cols_to_interp:
            resampled[col] = np.interp(grid, df['LapDistPct'], df[col])
        return resampled

    return interpolate_lap(driver_df), interpolate_lap(bench_df), grid

def calculate_time_delta(res_d, res_b, grid):
    # Assume 4300m (Zandvoort length) for realistic delta scaling
    track_length = 4300 
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    ds = np.diff(grid, prepend=0) * track_length
    return np.cumsum(ds / v_d - ds / v_b)

# --- UI: DASHBOARD ---

def main():
    apply_custom_css()
    st.title("🏁 Race Engineer | Professional Telemetry")
    
    d_file = st.sidebar.file_uploader("Driver CSV", type=['csv'])
    b_file = st.sidebar.file_uploader("Benchmark CSV", type=['csv'])

    if d_file and b_file:
        # Data Pipeline
        df_d = process_telemetry(pd.read_csv(d_file))
        df_b = process_telemetry(pd.read_csv(b_file))
        
        res_d, res_b, grid = align_and_resample(df_d, df_b)
        delta = calculate_time_delta(res_d, res_b, grid)
        
        # Dashboard Layout
        fig = make_subplots(
            rows=6, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.02,
            row_heights=[0.1, 0.2, 0.15, 0.15, 0.15, 0.25],
            subplot_titles=("Time Delta", "Speed", "Throttle", "Brake", "Gear", "Steering Angle")
        )

        x = grid * 100 # Convert to % for UI

        # 1. Delta
        fig.add_trace(go.Scatter(x=x, y=delta, name="Delta", line=dict(color='#ff4b4b')), row=1, col=1)
        
        # 2. Speed
        fig.add_trace(go.Scatter(x=x, y=res_b['Speed'], line=dict(color='grey', dash='dash')), row=2, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['Speed'], line=dict(color='#00d1ff')), row=2, col=1)
        
        # 3. Throttle
        fig.add_trace(go.Scatter(x=x, y=res_b['Throttle'], line=dict(color='grey', dash='dash')), row=3, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['Throttle'], line=dict(color='#00ff41')), row=3, col=1)
        
        # 4. Brake & ABS Active Highlight
        fig.add_trace(go.Scatter(x=x, y=res_b['Brake'], line=dict(color='grey', dash='dash')), row=4, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['Brake'], line=dict(color='#ff2a2a')), row=4, col=1)
        # Highlight ABS intervention in yellow on the brake chart
        abs_intervene = res_d['Brake'].where(res_d['ABSActive'] > 0)
        fig.add_trace(go.Scatter(x=x, y=abs_intervene, name="ABS", mode='markers', marker=dict(color='yellow', size=2)), row=4, col=1)
        
        # 5. Gear
        fig.add_trace(go.Scatter(x=x, y=res_b['Gear'], line=dict(color='grey', dash='step')), row=5, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['Gear'], line=dict(color='#ffffff', shape='hv')), row=5, col=1)
        
        # 6. Steering Wheel Angle
        fig.add_trace(go.Scatter(x=x, y=res_b['SteeringWheelAngle'], line=dict(color='grey', dash='dash')), row=6, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['SteeringWheelAngle'], line=dict(color='#ff8c00')), row=6, col=1)

        fig.update_layout(height=1000, template="plotly_dark", showlegend=False, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Please upload Garage 61 CSV files. Architect standing by.")

if __name__ == "__main__":
    main()
