import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Spatial Analysis", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 20px; margin-bottom: 15px; }
        .warning-card { background-color: #2d2616; border-left: 5px solid #ffcc00; padding: 20px; margin-bottom: 15px; color: #ffcc00; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff4b4b; padding: 20px; margin-bottom: 15px; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    
    # 1. Spatial Logic: Ensure LapDist (Meters) exists
    if 'LapDist' not in df.columns and 'LapDistPct' in df.columns:
        # Proxy track length (4259m for Zandvoort) if absolute distance is missing
        track_len = 4259 
        pct_col = pd.to_numeric(df['LapDistPct'], errors='coerce').fillna(0)
        if pct_col.max() > 1.1: pct_col /= 100.0
        df['LapDist'] = pct_col * track_len
    
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
    """Resamples both laps to a common meter-based grid."""
    max_dist = df_b['LapDist'].max()
    grid_meters = np.linspace(0, max_dist, points)
    
    def interp_channel(df):
        out = pd.DataFrame({'LapDist': grid_meters})
        channels = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'ABSActive', 'TCActive', 'LatG', 'LonG', 'GSum']
        for col in channels:
            if col in df.columns:
                out[col] = np.interp(grid_meters, df['LapDist'], df[col])
            else:
                out[col] = 0.0
        return out

    res_d = interp_channel(df_d)
    res_b = interp_channel(df_b)
    
    # Smoothing for heuristics
    res_d['SteeringSmooth'] = res_d['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    
    return res_d, res_b, grid_meters

# --- MODULE: DRIVER COACH (HEURISTICS) ---

def analyze_smoothness(df):
    insights = []
    # Throttle Stabbing (1-second window approx 50 samples)
    roll_max = df['Throttle'].rolling(window=50, center=True).max()
    roll_min = df['Throttle'].rolling(window=50, center=True).min()
    if ((roll_max > 80) & (roll_min < 20)).any():
        insights.append({"level": "warning", "msg": "Unstable Platform: Stop stabbing the throttle. Squeeze the pedal to load the rear tires."})

    # ABS Trail Braking Overshoot
    trail_abs = (df['ABSActive'] > 0.5) & (df['Brake'] < 30) & (df['Brake'] > 5)
    if trail_abs.sum() > 50:
        insights.append({"level": "critical", "msg": "ABS Over-reliance: You are triggering ABS during turn-in. Reduce brake pressure by 10% to allow rotation."})
    return insights

# --- MAIN APP ---

def main():
    apply_custom_css()
    
    with st.sidebar:
        st.title("🛠️ Config")
        setup = st.radio("Setup Rule", ["Open", "Fixed"])
        st.divider()
        f_d = st.file_uploader("Driver Telemetry", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry", type=['csv'])

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d))
        df_b = process_telemetry(pd.read_csv(f_b))
        res_d, res_b, grid_m = align_and_resample(df_d, df_b)
        
        # Physics Delta (dt = ds / v)
        v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
        v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
        ds = np.diff(grid_m, prepend=0)
        delta = np.cumsum(ds / v_d - ds / v_b)
        delta = delta - delta[0]

        t1, t2, t3 = st.tabs(["📊 Analyze Laps", "🧠 Driver Coach", "🔧 Setup Tweaker"])
        
        with t1:
            # Telemetry Stack with Meter X-Axis
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                                subplot_titles=("Time Delta (s)", "Speed (km/h)", "Throttle (%)", "Brake (%)"))
            
            # Row 1: Delta
            fig.add_trace(go.Scatter(x=grid_m, y=delta, name="Delta", line=dict(color='#ff4b4b', width=2)), row=1, col=1)
            
            # Row 2: Speed
            fig.add_trace(go.Scatter(x=grid_m, y=res_b['Speed'], name="Bench", line=dict(color='rgba(255,255,255,0.3)', dash='dash')), row=2, col=1)
            fig.add_trace(go.Scatter(x=grid_m, y=res_d['Speed'], name="Driver", line=dict(color='cyan')), row=2, col=1)
            
            # Row 3: Throttle
            fig.add_trace(go.Scatter(x=grid_m, y=res_d['Throttle'], name="Throttle", line=dict(color='#00ff41')), row=3, col=1)
            
            # Row 4: Brake
            fig.add_trace(go.Scatter(x=grid_m, y=res_d['Brake'], name="Brake", line=dict(color='#ff4b4b')), row=4, col=1)
            # ABS Shading
            abs_pts = res_d['Brake'].where(res_d['ABSActive'] > 0.5)
            fig.add_trace(go.Scatter(x=grid_m, y=abs_pts, fill='tozeroy', fillcolor='rgba(255,255,0,0.2)', line=dict(width=0)), row=4, col=1)
            
            fig.update_layout(height=1000, template="plotly_dark", showlegend=False, hovermode="x unified")
            fig.update_xaxes(title_text="Distance (meters)", row=4, col=1)
            st.plotly_chart(fig, use_container_width=True)

        with t2:
            st.header("🧠 Driver Coach")
            insights = analyze_smoothness(res_d)
            for insight in insights:
                card = "warning-card" if insight['level'] == "warning" else "critical-card"
                st.markdown(f'<div class="{card}">{insight["msg"]}</div>', unsafe_allow_html=True)
            
            # G-G Diagram
            fig_gg = go.Figure()
            fig_gg.add_trace(go.Scatter(x=res_d['LatG'], y=res_d['LonG'], mode='markers', marker=dict(color=res_d['Speed'], colorscale='Viridis', size=4)))
            fig_gg.update_layout(template="plotly_dark", title="Traction Circle (G-G)", xaxis=dict(title="Lat G", range=[-2.5, 2.5]), yaxis=dict(title="Lon G", range=[-2.5, 2.5]), height=500, width=500)
            st.plotly_chart(fig_gg)

        with t3:
            st.header("🔧 Setup Tweaker")
            # Balance Signature (Filtered)
            mask = (res_d['Speed'] > 60) & (res_d['Brake'] < 5)
            sig_data = res_d[mask]
            fig_sig = go.Figure()
            fig_sig.add_trace(go.Scatter(x=sig_data['LatG'].abs(), y=sig_data['SteeringSmooth'].abs(), mode='markers', marker=dict(color=sig_data['Speed'], size=4)))
            fig_sig.update_layout(template="plotly_dark", title="Balance Signature (Mid-Corner)", xaxis_title="Lat G", yaxis_title="Steering Angle", height=500)
            st.plotly_chart(fig_sig, use_container_width=True)

    else:
        st.info("Upload telemetry CSVs to begin spatial analysis.")

if __name__ == "__main__":
    main()
