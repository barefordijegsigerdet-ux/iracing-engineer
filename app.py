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

    # --- SPEED CORRECTION LOGIC ---
    # If max speed is < 100, it is likely in m/s. Convert to km/h.
    if df['Speed'].max() < 100:
        df['Speed'] = df['Speed'] * 3.6
    
    # Normalize Distance to 0.0 - 1.0
    if df['LapDistPct'].max() > 1.1:
        df['LapDistPct'] /= 100.0

    # Normalize Pedals to 0 - 100%
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
    # Use km/h converted back to m/s for accurate time math
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    
    # Zandvoort is ~4259m. Using this for the spatial ds calculation.
    ds = np.diff(grid, prepend=0) * 4259 
    delta = np.cumsum(ds / v_d - ds / v_b)
    
    # Line Distance (GPS separation in meters)
    d_lat = (res_d['Lat'] - res_b['Lat']) * 111000
    d_lon = (res_d['Lon'] - res_b['Lon']) * 67000
    line_distance = np.sqrt(d_lat**2 + d_lon**2)
    
    return delta, line_distance

# --- UI: TRACK MAP ---

def create_track_map(res_d, res_b):
    fig = go.Figure()
    # Track Surface
    fig.add_trace(go.Scatter(x=res_b['Lon'], y=res_b['Lat'], line=dict(color='#2a2e35', width=15), hoverinfo='skip'))
    # Lines
    fig.add_trace(go.Scatter(x=res_b['Lon'], y=res_b['Lat'], line=dict(color='#ff3344', width=2), name='Bench'))
    fig.add_trace(go.Scatter(x=res_d['Lon'], y=res_d['Lat'], line=dict(color='#00a2ff', width=2), name='Driver'))

    fig.update_layout(
        template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
        showlegend=False, height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
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
        
        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
        c2.metric("Driver Top Speed", f"{res_d['Speed'].max():.1f} km/h")
        c3.metric("Bench Top Speed", f"{res_b['Speed'].max():.1f} km/h")

        # Track Map
        st.plotly_chart(create_track_map(res_d, res_b), use_container_width=True)

        # Telemetry Stack
        fig = make_subplots(
            rows=8, cols=1, shared_xaxes=True, vertical_spacing=0.01,
            row_heights=[0.15, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.15],
            subplot_titles=("Speed (km/h)", "Throttle (%)", "Brake (%)", "Gear", "RPM", "Steering", "Line Distance (m)", "Time Delta (s)")
        )

        x = grid * 100
        c_b, c_d = '#ff3344', '#00a2ff'

        # Speed
        fig.add_trace(go.Scatter(x=x, y=res_b['Speed'], line=dict(color=c_b, width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['Speed'], line=dict(color=c_d, width=1.5)), row=1, col=1)
        
        # Throttle
        fig.add_trace(go.Scatter(x=x, y=res_b['Throttle'], line=dict(color=c_b, width=1.5)), row=2, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['Throttle'], line=dict(color=c_d, width=1.5)), row=2, col=1)
        
        # Brake
        fig.add_trace(go.Scatter(x=x, y=res_b['Brake'], line=dict(color=c_b, width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['Brake'], line=dict(color=c_d, width=1.5)), row=3, col=1)
        
        # Gear
        fig.add_trace(go.Scatter(x=x, y=res_b['Gear'], line=dict(color=c_b, shape='hv', width=1.5)), row=4, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['Gear'], line=dict(color=c_d, shape='hv', width=1.5)), row=4, col=1)
        
        # RPM
        fig.add_trace(go.Scatter(x=x, y=res_b['RPM'], line=dict(color=c_b, width=1.5)), row=5, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['RPM'], line=dict(color=c_d, width=1.5)), row=5, col=1)
        
        # Steering
        fig.add_trace(go.Scatter(x=x, y=res_b['SteeringWheelAngle'], line=dict(color=c_b, width=1.5)), row=6, col=1)
        fig.add_trace(go.Scatter(x=x, y=res_d['SteeringWheelAngle'], line=dict(color=c_d, width=1.5)), row=6, col=1)
        
        # Line Distance
        fig.add_trace(go.Scatter(x=x, y=line_dist, line=dict(color=c_d, width=2)), row=7, col=1)
        
        # Time Delta
        fig.add_trace(go.Scatter(x=x, y=delta, line=dict(color=c_d, width=2)), row=8, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="grey", row=8, col=1)

        fig.update_layout(height=1400, template="plotly_dark", showlegend=False, hovermode="x unified")
        fig.update_yaxes(showgrid=True, gridcolor='#30363d', griddash='dash')
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Upload CSVs to begin.")

if __name__ == "__main__":
    main()
