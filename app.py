import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- TRACK DATABASE ---
TRACK_DB = {
    "Zandvoort (GP)": 4259,
    "Spa-Francorchamps": 7004,
    "Sebring (International)": 6020,
    "Nürburgring (GP)": 5148,
    "Suzuka (GP)": 5807,
    "Mount Panorama": 6213,
    "Road America": 6448,
    "Watkins Glen (Boot)": 5450
}

# --- CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | G61 Replication", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING ---

def process_telemetry(df: pd.DataFrame, track_length: int) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    if 'LapDist' not in df.columns and 'LapDistPct' in df.columns:
        pct_col = pd.to_numeric(df['LapDistPct'], errors='coerce').fillna(0)
        if pct_col.max() > 1.1: pct_col /= 100.0
        df['LapDist'] = pct_col * track_length
    
    # Physics Normalization
    mapping = {'LatAccel': 'LatG', 'LongAccel': 'LonG', 'LonAccel': 'LonG'}
    for src, dest in mapping.items():
        if src in df.columns:
            df[dest] = pd.to_numeric(df[src], errors='coerce').fillna(0) / 9.81
    
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6
    
    for col in ['Throttle', 'Brake']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            if df[col].max() <= 1.1: df[col] *= 100.0
            
    return df.sort_values(by='LapDist').drop_duplicates(subset=['LapDist'])

def align_and_resample(df_d, df_b, points=5000):
    max_dist = df_b['LapDist'].max()
    grid_meters = np.linspace(0, max_dist, points)
    
    def interp_channel(df):
        out = pd.DataFrame({'LapDist': grid_meters})
        channels = ['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'ABSActive', 'LatG', 'LonG', 'Lat', 'Lon']
        for col in channels:
            out[col] = np.interp(grid_meters, df['LapDist'], df[col]) if col in df.columns else 0.0
        return out

    return interp_channel(df_d), interp_channel(df_b), grid_meters

def calculate_signed_line_dist(res_d, res_b):
    """
    Calculates signed lateral distance (Left/Right) from benchmark.
    Uses 2D cross product of benchmark heading and displacement vector.
    """
    # 1. Magnitude of separation in meters
    # Approx: 1 deg Lat = 111,000m, 1 deg Lon = 111,000m * cos(lat)
    # Using a simplified 111k/80k for European tracks like Zandvoort
    dy_m = (res_d['Lat'] - res_b['Lat']) * 111000
    dx_m = (res_d['Lon'] - res_b['Lon']) * 75000 
    magnitude = np.sqrt(dx_m**2 + dy_m**2)

    # 2. Direction (Cross Product)
    # Benchmark heading vector (tangent)
    tx = np.gradient(res_b['Lon'])
    ty = np.gradient(res_b['Lat'])
    
    # Displacement vector
    ux = res_d['Lon'] - res_b['Lon']
    uy = res_d['Lat'] - res_b['Lat']
    
    # Determinant (2D Cross Product)
    # If positive, driver is to one side; if negative, the other.
    direction = np.sign(tx * uy - ty * ux)
    
    return magnitude * direction

# --- MAIN APP ---

def main():
    apply_custom_css()
    
    with st.sidebar:
        st.title("🛠️ Config")
        selected_track = st.selectbox("Track Selector", list(TRACK_DB.keys()))
        track_len = TRACK_DB[selected_track]
        f_d = st.file_uploader("Driver Telemetry", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry", type=['csv'])

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d), track_len)
        df_b = process_telemetry(pd.read_csv(f_b), track_len)
        res_d, res_b, grid_m = align_and_resample(df_d, df_b)
        
        # Physics
        v_d, v_b = np.maximum(res_d['Speed'].values / 3.6, 1.0), np.maximum(res_b['Speed'].values / 3.6, 1.0)
        delta = np.cumsum(np.diff(grid_m, prepend=0) / v_d - np.diff(grid_m, prepend=0) / v_b)
        signed_line_dist = calculate_signed_line_dist(res_d, res_b)

        t1, t2, t3 = st.tabs(["📊 Analyze Laps", "🧠 Driver Coach", "🔧 Setup Tweaker"])
        
        with t1:
            fig = make_subplots(rows=8, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                                subplot_titles=("Speed", "Throttle", "Brake", "Gear", "RPM", "Steering", "Line Distance", "Time Delta"))
            
            # Standard Traces... (Speed, Throttle, etc.)
            for i, col in enumerate(['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle'], 1):
                fig.add_trace(go.Scatter(x=grid_m, y=res_b[col], line=dict(color='#ff3344', width=1), name="Bench"), row=i, col=1)
                fig.add_trace(go.Scatter(x=grid_m, y=res_d[col], line=dict(color='#00a2ff', width=1.8), name="Driver"), row=i, col=1)

            # --- ROW 7: LINE DISTANCE (G61 REPLICATION) ---
            # Solid Red Zero Line
            fig.add_hline(y=0, line_color="#ff3344", line_width=1.5, row=7, col=1)
            
            # Signed Blue Trace
            # Custom hover text for Left/Right
            hover_text = [f"{'Right' if val > 0 else 'Left'} {abs(val):.2f} m" for val in signed_line_dist]
            fig.add_trace(go.Scatter(
                x=grid_m, y=signed_line_dist, 
                line=dict(color='#00a2ff', width=1.5),
                text=hover_text,
                hovertemplate="%{text}<extra></extra>",
                name="Line Distance"
            ), row=7, col=1)
            
            # Row 8: Delta
            fig.add_trace(go.Scatter(x=grid_m, y=delta, line=dict(color='#00a2ff', width=2)), row=8, col=1)
            fig.add_hline(y=0, line_dash="dash", line_color="grey", row=8, col=1)

            # Formatting
            fig.update_xaxes(showticklabels=True, title_text="Distance (m)", gridcolor='#30363d', griddash='dash')
            fig.update_yaxes(gridcolor='#30363d', griddash='dash')
            fig.update_yaxes(range=[-3.5, 3.5], row=7, col=1) # Match G61 Y-axis scale
            
            fig.update_layout(height=1800, template="plotly_dark", showlegend=False, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Awaiting telemetry files.")

if __name__ == "__main__":
    main()
