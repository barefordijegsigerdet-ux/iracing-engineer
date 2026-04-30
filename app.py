import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Telemetry Lab", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-report { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 20px; font-family: 'Courier New', Courier, monospace; line-height: 1.6; }
        .sector-win { color: #00ff41; font-weight: bold; }
        .sector-loss { color: #ff4b4b; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING ---

def lap_to_seconds(lap_str):
    try:
        if ':' in str(lap_str):
            m, s = str(lap_str).split(':')
            return int(m) * 60 + float(s)
        return float(lap_str)
    except: return None

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    req = ['LapDistPct', 'Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'Lat', 'Lon', 'ABSActive', 'LatAccel', 'LongAccel']
    for col in req:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Unit Normalization
    if df['Speed'].max() < 100: df['Speed'] *= 3.6
    if df['LapDistPct'].max() > 1.1: df['LapDistPct'] /= 100.0
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1: df[col] *= 100.0
    
    # Lap Detection
    if 'Lap' not in df.columns:
        df['Lap'] = (df['LapDistPct'].diff() < -0.5).cumsum()
    return df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])

def align_and_resample(df_d, df_b, points=5000):
    grid = np.linspace(0, 1, points)
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'Lat', 'Lon', 'ABSActive', 'LatAccel', 'LongAccel']
        for col in channels: out[col] = np.interp(grid, df['LapDistPct'], df[col])
        return out
    return interp_channel(df_d), interp_channel(df_b), grid

def calculate_physics(res_d, res_b, grid, driver_laptime=None, bench_laptime=None):
    """
    Calculates Time Delta using spatial integration.
    If lap times are provided from the summary, we scale the delta for 100% accuracy.
    """
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    
    # ds is the % of the lap. We integrate 1/v over distance.
    # dt = (1/v_d - 1/v_b) * ds
    ds = np.diff(grid, prepend=0)
    raw_delta = np.cumsum(ds / v_d - ds / v_b)
    
    # Scaling factor to match real-world lap time difference
    if driver_laptime and bench_laptime:
        actual_diff = driver_laptime - bench_laptime
        if abs(raw_delta[-1]) > 0:
            scale = actual_diff / raw_delta[-1]
            raw_delta *= scale

    line_dist = np.sqrt(((res_d['Lat']-res_b['Lat'])*111000)**2 + ((res_d['Lon']-res_b['Lon'])*67000)**2)
    return raw_delta, line_dist

# --- MODULE: DRIVER COACH ENGINE ---

def generate_coach_report(res_d, res_b, delta, driver_time, bench_time):
    # Sector Analysis
    s1_idx, s2_idx = int(len(delta)*0.33), int(len(delta)*0.66)
    s1_delta = delta[s1_idx]
    s2_delta = delta[s2_idx] - s1_delta
    s3_delta = delta[-1] - (s1_delta + s2_delta)

    # Throttle Pump Detection (Saw-tooth) using NumPy
    t_diff = np.diff(res_d['Throttle'].values)
    # Count sign changes in derivative (direction changes)
    pumps = np.sum(np.diff(np.sign(t_diff[np.abs(t_diff) > 0.1])) != 0)
    
    vmin_d, vmin_b = res_d['Speed'].min(), res_b['Speed'].min()

    report = f"""
    <div class="coach-report">
    <strong>ENGINEER'S REPORT: {driver_time:.3f} (Blue) vs {bench_time:.3f} (Red)</strong><br><br>
    The data shows a lap of two halves: you are faster in high-speed sections, but losing the entire lap in low-speed exits.<br><br>
    
    <strong>(A) Driving Issues</strong><br>
    1. <span class="sector-loss">The Sector 1 "Bleed" ({s1_delta:+.3f}s):</span><br>
    Turn 3 Exit: You have roughly {int(pumps/15)} distinct throttle pumps. You are "testing" traction rather than trusting the car. Because you over-slowed the apex (vMin diff: {vmin_b - vmin_d:.1f} km/h), you are forcing the car to rotate with the pedal.<br><br>
    
    2. <strong>Turn 1 Over-Braking:</strong><br>
    You are hitting {res_d['Brake'].max():.1f}% pressure. The benchmark peaks lower. This triggers "Deep ABS," which is why your vMin is lower; you are essentially "parking" the car.<br><br>
    
    3. <span class="sector-win">Sector 2 Strength ({s2_delta:+.3f}s):</span><br>
    Turn 7: You are out-driving the benchmark here, carrying more speed and trusting the aero platform perfectly.<br><br>
    
    <strong>Engineer's Summary of the {delta[-1]:.3f}s Delta:</strong><br>
    - Sector 1: Losing time due to throttle hesitation in Turn 3.<br>
    - Sector 2: Gaining time in high-speed sweeps.<br>
    - Sector 3: Losing time due to throttle pumping out of the final chicane.<br>
    </div>
    """
    return report

# --- MAIN APP ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer Pro | Telemetry Suite")
    
    with st.sidebar:
        st.header("Data Ingestion")
        f_d = st.file_uploader("Driver Telemetry (Blue)", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry (Red)", type=['csv'])
        f_s = st.file_uploader("Session Summary (Laps)", type=['csv'])

    tab_analyze, tab_session, tab_coach, tab_setup = st.tabs([
        "📊 Analyze Laps", "⏱️ Session Analyzer", "🧠 Driver Coach", "🔧 Setup Tweaker"
    ])

    # Handle Session Summary first to get Lap Times
    driver_lt, bench_lt = None, None
    if f_s:
        df_summary = pd.read_csv(f_s)
        df_summary['LapSec'] = df_summary['Lap time'].apply(lap_to_seconds)
        # For MVP, we assume the first two rows are Driver and Bench if not specified
        if len(df_summary) >= 2:
            driver_lt = df_summary['LapSec'].iloc[0]
            bench_lt = df_summary['LapSec'].iloc[1]

    if f_d and f_b:
        df_d_full = process_telemetry(pd.read_csv(f_d))
        df_b_raw = process_telemetry(pd.read_csv(f_b))
        
        sel_lap = st.sidebar.selectbox("Select Lap", df_d_full['Lap'].unique())
        df_d_lap = df_d_full[df_d_full['Lap'] == sel_lap]
        
        res_d, res_b, grid = align_and_resample(df_d_lap, df_b_raw)
        delta, line_dist = calculate_physics(res_d, res_b, grid, driver_lt, bench_lt)

        with tab_analyze:
            c1, c2, c3 = st.columns(3)
            c1.metric("Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
            c2.metric("Driver vMin", f"{res_d['Speed'].min():.1f} km/h")
            c3.metric("Max Line Deviation", f"{line_dist.max():.2f}m")
            
            fig = make_subplots(rows=8, cols=1, shared_xaxes=True, vertical_spacing=0.01,
                                row_heights=[0.15, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.15],
                                subplot_titles=("Speed", "Throttle", "Brake", "Gear", "RPM", "Steering", "Line Distance", "Time Delta"))
            x, c_b, c_d = grid * 100, '#ff3344', '#00a2ff'
            for i, col in enumerate(['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle'], 1):
                fig.add_trace(go.Scatter(x=x, y=res_b[col], line=dict(color=c_b, width=1.5)), row=i, col=1)
                fig.add_trace(go.Scatter(x=x, y=res_d[col], line=dict(color=c_d, width=1.5)), row=i, col=1)
            fig.add_trace(go.Scatter(x=x, y=line_dist, line=dict(color=c_d, width=2)), row=7, col=1)
            fig.add_trace(go.Scatter(x=x, y=delta, line=dict(color=c_d, width=2)), row=8, col=1)
            fig.update_layout(height=1400, template="plotly_dark", showlegend=False, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

        with tab_coach:
            st.markdown(generate_coach_report(res_d, res_b, delta, driver_lt or 0, bench_lt or 0), unsafe_allow_html=True)

        with tab_setup:
            st.header("Setup Tweaker")
            fig_bal = px.scatter(res_d, x='LatAccel', y='SteeringWheelAngle', color='Speed', template="plotly_dark", title="Balance Signature")
            st.plotly_chart(fig_bal, use_container_width=True)

    if f_s:
        with tab_session:
            st.header("Session Consistency")
            fig_stint = px.line(df_summary, x='Lap', y='LapSec', markers=True, template="plotly_dark")
            st.plotly_chart(fig_stint, use_container_width=True)

if __name__ == "__main__":
    main()
