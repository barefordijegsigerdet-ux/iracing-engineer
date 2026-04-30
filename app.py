import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- ARCHITECTURAL SETUP ---
st.set_page_config(page_title="Race Engineer | Pro Telemetry", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        [data-testid="stSidebar"] { background-color: #0b0e14; border-right: 1px solid #30363d; }
        </style>
    """, unsafe_allow_html=True)

# --- CORE DATA ENGINE ---

def clean_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes the single-lap CSV. Handles unit normalization for 
    Throttle, Brake, and Distance.
    """
    # 1. Clean Column Names
    df.columns = [c.strip() for c in df.columns]
    
    # 2. Force Numeric
    cols_to_fix = ['Speed', 'LapDistPct', 'Brake', 'Throttle', 'RPM', 'SteeringWheelAngle', 'Gear', 'ABSActive', 'Lat', 'Lon']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0.0 # Placeholder for missing sensors

    # 3. Handle Distance Normalization (Ensure 0.0 - 1.0)
    if df['LapDistPct'].max() > 1.1:
        df['LapDistPct'] = df['LapDistPct'] / 100.0

    # 4. Handle Throttle/Brake Normalization (Ensure 0 - 100)
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1:
            df[col] = df[col] * 100.0

    # 5. Sort for Interpolation (Vital for single lap accuracy)
    df = df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])
    
    return df

def resample_laps(df_d, df_b, points=5000):
    """
    Interpolates both laps to a fixed 5000-point baseline.
    """
    grid = np.linspace(0, 1, points)
    
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'RPM', 'Gear', 'SteeringWheelAngle', 'ABSActive', 'Lat', 'Lon']
        for col in channels:
            out[col] = np.interp(grid, df['LapDistPct'], df[col])
        return out

    return interp_channel(df_d), interp_channel(df_b), grid

def get_time_delta(res_d, res_b, grid):
    """
    Calculates cumulative time difference. 
    Formula: dt = ds / v. We assume a 4.5km lap length for scaling.
    """
    # Convert km/h to m/s
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    
    # ds = change in distance percentage * 4500 meters
    ds = np.diff(grid, prepend=0) * 4500
    
    dt_d = ds / v_d
    dt_b = ds / v_b
    
    return np.cumsum(dt_d - dt_b)

# --- UI RENDERER ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer | Telemetry Analysis")
    
    with st.sidebar:
        st.header("Session Data")
        file_d = st.file_uploader("Driver Lap CSV", type=['csv'])
        file_b = st.file_uploader("Benchmark Lap CSV", type=['csv'])
        st.divider()
        st.caption("Target: Porsche 992.2 GT3 Cup Analysis")

    if file_d and file_b:
        # Load and Clean
        df_d = clean_telemetry(pd.read_csv(file_d))
        df_b = clean_telemetry(pd.read_csv(file_b))
        
        # Resample & Compute
        res_d, res_b, grid = resample_laps(df_d, df_b)
        delta = get_time_delta(res_d, res_b, grid)
        
        # Display Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
        c2.metric("Max Speed", f"{df_d['Speed'].max():.1f} km/h")
        c3.metric("Avg Throttle", f"{df_d['Throttle'].mean():.1f}%")

        # Main Visualization Stack
        fig = make_subplots(
            rows=7, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.1, 0.2, 0.15, 0.15, 0.1, 0.1, 0.2],
            subplot_titles=("Time Delta", "Speed (km/h)", "Throttle (%)", "Brake (%)", "Gear", "RPM", "Steering Angle")
        )

        x_pct = grid * 100
        
        # 1. Delta
        fig.add_trace(go.Scatter(x=x_pct, y=delta, name="Delta", line=dict(color='#ff4b4b', width=2)), row=1, col=1)
        
        # 2. Speed
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['Speed'], name="Bench", line=dict(color='rgba(255,255,255,0.2)', dash='dash')), row=2, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['Speed'], name="Driver", line=dict(color='#00d1ff', width=2.5)), row=2, col=1)
        
        # 3. Throttle
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['Throttle'], line=dict(color='rgba(255,255,255,0.2)', dash='dash')), row=3, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['Throttle'], line=dict(color='#00ff41', width=2)), row=3, col=1)
        
        # 4. Brake & ABS Active Highlight (Yellow dots)
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['Brake'], line=dict(color='rgba(255,255,255,0.2)', dash='dash')), row=4, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['Brake'], line=dict(color='#ff2a2a', width=2)), row=4, col=1)
        abs_hits = res_d['Brake'].where(res_d['ABSActive'] > 0.5)
        fig.add_trace(go.Scatter(x=x_pct, y=abs_hits, mode='markers', marker=dict(color='yellow', size=3), name="ABS"), row=4, col=1)
        
        # 5. Gear
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['Gear'], line=dict(color='white', shape='hv')), row=5, col=1)
        
        # 6. RPM
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['RPM'], line=dict(color='#ff8c00', width=1)), row=6, col=1)
        
        # 7. Steering Angle
        fig.add_trace(go.Scatter(x=x_pct, y=res_b['SteeringWheelAngle'], line=dict(color='rgba(255,255,255,0.2)', dash='dash')), row=7, col=1)
        fig.add_trace(go.Scatter(x=x_pct, y=res_d['SteeringWheelAngle'], line=dict(color='#00d1ff', width=1.5)), row=7, col=1)

        fig.update_layout(height=1100, template="plotly_dark", showlegend=False, hovermode="x unified", margin=dict(t=30, b=30))
        fig.update_xaxes(title_text="Lap Distance (%)", row=7, col=1)
        
        st.plotly_chart(fig, use_container_width=True)

        # Track Map Section
        st.subheader("Spatial Line Analysis")
        col_map, col_data = st.columns([2, 1])
        with col_map:
            fig_map = go.Figure()
            fig_map.add_trace(go.Scatter(x=res_b['Lon'], y=res_b['Lat'], line=dict(color='white', width=4, dash='dash'), name="Bench"))
            fig_map.add_trace(go.Scatter(x=res_d['Lon'], y=res_d['Lat'], line=dict(color='#00d1ff', width=2), name="Driver"))
            fig_map.update_layout(template="plotly_dark", height=500, xaxis_visible=False, yaxis_visible=False, title="Track Map (Lat/Lon)")
            st.plotly_chart(fig_map, use_container_width=True)
        
        with col_data:
            st.write("### Sector Insights")
            st.info("Steering Trace: High variability suggests mid-corner instability. Check Porsche 992 Cup rear rebound settings.")

    else:
        st.info("Awaiting telemetry CSV files for single-lap analysis.")

if __name__ == "__main__":
    main()
