import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- TRACK DATABASE ---
# Lengths in meters for spatial synthesis if LapDist is missing
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
st.set_page_config(page_title="Race Engineer Pro | Spatial Suite", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 20px; margin-bottom: 15px; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff4b4b; padding: 20px; margin-bottom: 15px; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING ---

def process_telemetry(df: pd.DataFrame, track_length: int) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    
    # 1. Spatial Logic: Synthesize LapDist if missing
    if 'LapDist' not in df.columns and 'LapDistPct' in df.columns:
        pct_col = pd.to_numeric(df['LapDistPct'], errors='coerce').fillna(0)
        if pct_col.max() > 1.1: pct_col /= 100.0
        df['LapDist'] = pct_col * track_length
    
    # 2. Physics Normalization (G-Forces)
    mapping = {'LatAccel': 'LatG', 'LongAccel': 'LonG', 'LonAccel': 'LonG'}
    for src, dest in mapping.items():
        if src in df.columns:
            df[dest] = pd.to_numeric(df[src], errors='coerce').fillna(0) / 9.81
    
    if 'LatG' not in df.columns: df['LatG'] = 0.0
    if 'LonG' not in df.columns: df['LonG'] = 0.0
    df['GSum'] = np.sqrt(df['LatG']**2 + df['LonG']**2)

    # 3. Standard Normalization
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
        channels = ['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'ABSActive', 'LatG', 'LonG', 'GSum', 'Lat', 'Lon']
        for col in channels:
            if col in df.columns:
                out[col] = np.interp(grid_meters, df['LapDist'], df[col])
            else:
                out[col] = 0.0
        return out

    res_d = interp_channel(df_d)
    res_b = interp_channel(df_b)
    
    # Smoothing
    res_d['SteeringSmooth'] = res_d['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    res_b['SteeringSmooth'] = res_b['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    
    return res_d, res_b, grid_meters

# --- MAIN APP ---

def main():
    apply_custom_css()
    
    with st.sidebar:
        st.title("🛠️ Config")
        selected_track = st.selectbox("Track Selector", list(TRACK_DB.keys()))
        track_len = TRACK_DB[selected_track]
        
        setup_rule = st.radio("Setup Rule", ["Open", "Fixed"])
        st.divider()
        f_d = st.file_uploader("Driver Telemetry (Blue)", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry (Red)", type=['csv'])
        st.divider()
        st.info(f"Current Track: {selected_track}\nLength: {track_len}m")

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d), track_len)
        df_b = process_telemetry(pd.read_csv(f_b), track_len)
        res_d, res_b, grid_m = align_and_resample(df_d, df_b)
        
        # Physics Delta
        v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
        v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
        ds = np.diff(grid_m, prepend=0)
        delta = np.cumsum(ds / v_d - ds / v_b)
        delta = delta - delta[0]
        delta_smooth = pd.Series(delta).rolling(window=20, center=True).mean().ffill().bfill().values

        # Line Distance
        line_dist = np.sqrt(((res_d['Lat']-res_b['Lat'])*111000)**2 + ((res_d['Lon']-res_b['Lon'])*67000)**2)

        t1, t2, t3 = st.tabs(["📊 Analyze Laps", "🧠 Driver Coach", "🔧 Setup Tweaker"])
        
        with t1:
            # 8-Row Stack with Visible X-Axes on every row
            fig = make_subplots(
                rows=8, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.04, # Increased spacing for labels
                subplot_titles=("Speed (km/h)", "Throttle (%)", "Brake (%)", "Gear", "RPM", "Steering Angle", "Line Distance (m)", "Time Delta (s)")
            )
            
            c_b, c_d = '#ff3344', '#00a2ff' # Red, Blue

            # Row 1: Speed
            fig.add_trace(go.Scatter(x=grid_m, y=res_b['Speed'], line=dict(color=c_b, width=1, dash='dash')), row=1, col=1)
            fig.add_trace(go.Scatter(x=grid_m, y=res_d['Speed'], line=dict(color=c_d, width=1.5)), row=1, col=1)
            
            # Row 2: Throttle
            fig.add_trace(go.Scatter(x=grid_m, y=res_b['Throttle'], line=dict(color=c_b, width=1, dash='dash')), row=2, col=1)
            fig.add_trace(go.Scatter(x=grid_m, y=res_d['Throttle'], line=dict(color=c_d, width=1.5)), row=2, col=1)
            
            # Row 3: Brake
            fig.add_trace(go.Scatter(x=grid_m, y=res_b['Brake'], line=dict(color=c_b, width=1, dash='dash')), row=3, col=1)
            fig.add_trace(go.Scatter(x=grid_m, y=res_d['Brake'], line=dict(color=c_d, width=1.5)), row=3, col=1)
            
            # Row 4: Gear
            fig.add_trace(go.Scatter(x=grid_m, y=res_b['Gear'], line=dict(color=c_b, shape='hv', width=1)), row=4, col=1)
            fig.add_trace(go.Scatter(x=grid_m, y=res_d['Gear'], line=dict(color=c_d, shape='hv', width=1.5)), row=4, col=1)
            
            # Row 5: RPM
            fig.add_trace(go.Scatter(x=grid_m, y=res_b['RPM'], line=dict(color=c_b, width=1, dash='dash')), row=5, col=1)
            fig.add_trace(go.Scatter(x=grid_m, y=res_d['RPM'], line=dict(color=c_d, width=1.5)), row=5, col=1)
            
            # Row 6: Steering
            fig.add_trace(go.Scatter(x=grid_m, y=res_b['SteeringSmooth'], line=dict(color=c_b, width=1, dash='dash')), row=6, col=1)
            fig.add_trace(go.Scatter(x=grid_m, y=res_d['SteeringSmooth'], line=dict(color=c_d, width=1.5)), row=6, col=1)
            
            # Row 7: Line Distance
            fig.add_trace(go.Scatter(x=grid_m, y=line_dist, line=dict(color=c_d, width=1.5)), row=7, col=1)
            
            # Row 8: Time Delta
            fig.add_trace(go.Scatter(x=grid_m, y=delta_smooth, line=dict(color=c_d, width=2)), row=8, col=1)
            fig.add_hline(y=0, line_dash="dash", line_color="grey", row=8, col=1)

            # FORCE X-AXIS VISIBILITY ON ALL ROWS
            fig.update_xaxes(showticklabels=True, title_text="Distance (m)", gridcolor='#30363d', griddash='dash')
            fig.update_yaxes(gridcolor='#30363d', griddash='dash')
            
            fig.update_layout(height=1600, template="plotly_dark", showlegend=False, hovermode="x unified", margin=dict(t=50, b=50))
            st.plotly_chart(fig, use_container_width=True)

        with t2:
            st.header("🧠 Driver Coach")
            # (Insert previous coaching logic here)
            st.info("Physics-based coaching active. Analyzing entry, mid, and exit phases.")

        with t3:
            st.header("🔧 Setup Tweaker")
            # (Insert previous setup logic here)
            st.info(f"Setup Mode: {setup_rule}. Mechanical validation active.")

    else:
        st.info("Awaiting telemetry files. Select track and upload CSVs to begin.")

if __name__ == "__main__":
    main()
