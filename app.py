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
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        [data-testid="stSidebar"] { background-color: #0b0e14; border-right: 1px solid #30363d; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    
    # Required channels according to your CSV list
    req = ['LapDistPct', 'Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'Lat', 'Lon']
    for col in req:
        if col not in df.columns:
            st.error(f"Missing column: {col}")
            st.stop()

    for col in req:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Normalize Distance to 0.0 - 1.0
    if df['LapDistPct'].max() > 1.1:
        df['LapDistPct'] = df['LapDistPct'] / 100.0

    # Normalize Pedals to 0 - 100%
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1:
            df[col] = df[col] * 100.0

    # Sort and drop duplicates for np.interp
    df = df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])
    return df[req]

def align_and_resample(df_d, df_b, points=5000):
    grid = np.linspace(0, 1, points)
    
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'Lat', 'Lon']
        for col in channels:
            out[col] = np.interp(grid, df['LapDistPct'], df[col])
        return out

    return interp_channel(df_d), interp_channel(df_b), grid

def calculate_physics(res_d, res_b, grid):
    """
    Calculates Time Delta and Line Distance (in meters) from GPS data.
    """
    # 1. Time Delta
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    ds = np.diff(grid, prepend=0) * 4300 # Zandvoort Length Estimate
    delta = np.cumsum(ds / v_d - ds / v_b)
    
    # 2. Line Distance (Magnitude of GPS separation converted to meters)
    # 1 deg Lat approx 111,000m. 1 deg Lon at Zandvoort approx 67,000m.
    d_lat = (res_d['Lat'] - res_b['Lat']) * 111000
    d_lon = (res_d['Lon'] - res_b['Lon']) * 67000
    line_distance = np.sqrt(d_lat**2 + d_lon**2)
    
    return delta, line_distance

# --- UI RENDERER ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer | Garage 61 Replication")
    
    with st.sidebar:
        st.header("Upload Laps")
        file_d = st.file_uploader("Driver Lap CSV (Blue Line)", type=['csv'])
        file_b = st.file_uploader("Benchmark Lap CSV (Red Line)", type=['csv'])

    if file_d and file_b:
        # Load and Clean
        df_d = process_telemetry(pd.read_csv(file_d))
        df_b = process_telemetry(pd.read_csv(file_b))
        
        # Resample
        res_d, res_b, grid = align_and_resample(df_d, df_b)
        
        # Custom Calculations
        delta, line_dist = calculate_physics(res_d, res_b, grid)
        
        # Top Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Final Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
        c2.metric("Max Driver Speed", f"{res_d['Speed'].max():.1f} km/h")
        c3.metric("Max Line Separation", f"{line_dist.max():.2f} m")

        # Garage 61 Stack: 8 Rows
        fig = make_subplots(
            rows=8, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.015,
            row_heights=[0.15, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.15],
            subplot_titles=(
                "Speed (km/h)", "Throttle (%)", "Brake (%)", 
                "Gear", "RPM", "Steering Angle", 
                "Line Distance (m separation)", "Time Delta (s)"
            )
        )

        x_pct = grid * 100
        
        # Color mapping to match Garage 61
        color_bench = '#ff3344'  # Red
        color_driver = '#00a2ff' # Blue
        
        # Row 1: Speed
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['Speed'], name="Bench", line=dict(color=color_bench, width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['Speed'], name="Driver", line=dict(color=color_driver, width=1.5)), row=1, col=1)
        
        # Row 2: Throttle
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['Throttle'], line=dict(color=color_bench, width=1.5)), row=2, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['Throttle'], line=dict(color=color_driver, width=1.5)), row=2, col=1)
        
        # Row 3: Brake
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['Brake'], line=dict(color=color_bench, width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['Brake'], line=dict(color=color_driver, width=1.5)), row=3, col=1)
        
        # Row 4: Gear
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['Gear'], line=dict(color=color_bench, shape='hv', width=1.5)), row=4, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['Gear'], line=dict(color=color_driver, shape='hv', width=1.5)), row=4, col=1)
        
        # Row 5: RPM
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['RPM'], line=dict(color=color_bench, width=1.5)), row=5, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['RPM'], line=dict(color=color_driver, width=1.5)), row=5, col=1)
        
        # Row 6: Steering Angle
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['SteeringWheelAngle'], line=dict(color=color_bench, width=1.5)), row=6, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['SteeringWheelAngle'], line=dict(color=color_driver, width=1.5)), row=6, col=1)
        
        # Row 7: Line Distance (Magnitude of lateral line deviation)
        fig.add_trace(go.Scatter(x=x_pct, y=line_dist, name="Line Sep", line=dict(color=color_driver, width=2)), row=7, col=1)
        
        # Row 8: Time Delta
        fig.add_trace(go.Scatter(x=x_pct, y=delta, name="Delta", line=dict(color=color_driver, width=2)), row=8, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="grey", row=8, col=1)

        fig.update_layout(height=1400, template="plotly_dark", showlegend=False, hovermode="x unified", margin=dict(t=30, b=30))
        fig.update_xaxes(title_text="Lap Distance (%)", row=8, col=1)
        
        # Set dashed lines across all backgrounds like G61
        fig.update_yaxes(showgrid=True, gridcolor='#30363d', gridwidth=1, griddash='dash')
        fig.update_xaxes(showgrid=True, gridcolor='#30363d', gridwidth=1, griddash='dash')
        
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Awaiting telemetry files. Please upload your CSV exports from Garage 61.")

if __name__ == "__main__":
    main()
