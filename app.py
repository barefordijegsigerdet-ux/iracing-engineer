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
    req = ['LapDistPct', 'Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'Lat', 'Lon']
    
    for col in req:
        if col not in df.columns:
            st.error(f"Missing column: {col}")
            st.stop()
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if df['LapDistPct'].max() > 1.1:
        df['LapDistPct'] /= 100.0

    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1:
            df[col] *= 100.0

    return df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])

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
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    ds = np.diff(grid, prepend=0) * 4300 
    delta = np.cumsum(ds / v_d - ds / v_b)
    
    # Line Distance (GPS separation in meters)
    d_lat = (res_d['Lat'] - res_b['Lat']) * 111000
    d_lon = (res_d['Lon'] - res_b['Lon']) * 67000
    line_distance = np.sqrt(d_lat**2 + d_lon**2)
    
    return delta, line_distance

# --- UI: TRACK MAP RENDERER ---

def create_track_map(res_d, res_b):
    """
    Creates the Garage 61 style track map with layered lines.
    """
    fig = go.Figure()

    # 1. Track Surface (Thick Gray Path)
    fig.add_trace(go.Scatter(
        x=res_b['Lon'], y=res_b['Lat'],
        line=dict(color='#2a2e35', width=12),
        hoverinfo='skip', name='Track'
    ))

    # 2. Benchmark Line (Red)
    fig.add_trace(go.Scatter(
        x=res_b['Lon'], y=res_b['Lat'],
        line=dict(color='#ff3344', width=2),
        name='Benchmark'
    ))

    # 3. Driver Line (Blue)
    fig.add_trace(go.Scatter(
        x=res_d['Lon'], y=res_d['Lat'],
        line=dict(color='#00a2ff', width=2),
        name='Driver'
    ))

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), # CRITICAL: 1:1 Aspect Ratio
        showlegend=False,
        height=500
    )
    return fig

# --- UI: MAIN APP ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer | Pro Telemetry")
    
    with st.sidebar:
        st.header("Data Ingestion")
        file_d = st.file_uploader("Driver Lap (Blue)", type=['csv'])
        file_b = st.file_uploader("Benchmark Lap (Red)", type=['csv'])

    if file_d and file_b:
        df_d = process_telemetry(pd.read_csv(file_d))
        df_b = process_telemetry(pd.read_csv(file_b))
        res_d, res_b, grid = align_and_resample(df_d, df_b)
        delta, line_dist = calculate_physics(res_d, res_b, grid)
        
        # Layout: Map on the left, Insights on the right
        col_map, col_metrics = st.columns([2, 1])
        with col_map:
            st.plotly_chart(create_track_map(res_d, res_b), use_container_width=True)
        with col_metrics:
            st.metric("Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
            st.metric("Max Line Deviation", f"{line_dist.max():.2f}m")
            st.info("Spatial Analysis: The blue line shows your tighter entry into Turn 3 compared to the benchmark.")

        # Telemetry Stack (G61 Order)
        fig = make_subplots(
            rows=8, cols=1, shared_xaxes=True, vertical_spacing=0.01,
            row_heights=[0.15, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.15],
            subplot_titles=("Speed", "Throttle", "Brake", "Gear", "RPM", "Steering", "Line Distance", "Time Delta")
        )

        x = grid * 100
        c_b, c_d = '#ff3344', '#00a2ff' # Red, Blue

        # Add traces (Simplified for brevity, same logic as previous step)
        for row, col_name in enumerate(['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle'], 1):
            fig.add_trace(go.Scatter(x=x, y=res_b[col_name], line=dict(color=c_b, width=1.5)), row=row, col=1)
            fig.add_trace(go.Scatter(x=x, y=res_d[col_name], line=dict(color=c_d, width=1.5)), row=row, col=1)
        
        fig.add_trace(go.Scatter(x=x, y=line_dist, line=dict(color=c_d, width=2)), row=7, col=1)
        fig.add_trace(go.Scatter(x=x, y=delta, line=dict(color=c_d, width=2)), row=8, col=1)

        fig.update_layout(height=1400, template="plotly_dark", showlegend=False, hovermode="x unified")
        fig.update_yaxes(showgrid=True, gridcolor='#30363d', griddash='dash')
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Upload CSVs to begin.")

if __name__ == "__main__":
    main()
