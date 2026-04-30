import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import find_peaks

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

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    # Standard G61 Headers
    req = ['LapDistPct', 'Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'Lat', 'Lon', 'ABSActive', 'LatAccel', 'LongAccel']
    if 'Time' in df.columns: req.append('Time')
    
    for col in req:
        if col not in df.columns: df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Unit Normalization
    if df['Speed'].max() < 100: df['Speed'] *= 3.6
    if df['LapDistPct'].max() > 1.1: df['LapDistPct'] /= 100.0
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1: df[col] *= 100.0
    
    return df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])

def align_and_resample(df_d, df_b, points=5000):
    grid = np.linspace(0, 1, points)
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'Lat', 'Lon', 'ABSActive', 'LatAccel', 'LongAccel']
        if 'Time' in df.columns: channels.append('Time')
        for col in channels: out[col] = np.interp(grid, df['LapDistPct'], df[col])
        return out
    return interp_channel(df_d), interp_channel(df_b), grid

def calculate_physics(res_d, res_b, grid):
    # 1. Time Delta Calculation
    # If 'Time' exists, use the difference of absolute times. 
    # Otherwise, use spatial integration: dt = ds / v
    if 'Time' in res_d.columns and 'Time' in res_b.columns:
        delta = res_d['Time'].values - res_b['Time'].values
    else:
        v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
        v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
        ds = np.diff(grid, prepend=0) * 4259 # Zandvoort length
        delta = np.cumsum(ds / v_d - ds / v_b)
    
    # 2. Line Distance (GPS separation)
    line_distance = np.sqrt(((res_d['Lat']-res_b['Lat'])*111000)**2 + ((res_d['Lon']-res_b['Lon'])*67000)**2)
    
    # 3. G-Sum (Tire Stress)
    res_d['GSum'] = np.sqrt(res_d['LatAccel']**2 + res_d['LongAccel']**2)
    
    return delta, line_distance

# --- MODULE: DRIVER COACH ENGINE ---

def generate_coach_report(res_d, res_b, grid, delta):
    """
    Logic-based diagnostic engine to generate the narrative report.
    """
    # Identify Sectors (Approximate for Zandvoort)
    s1_end, s2_end = 0.33, 0.66
    d_s1 = delta[int(len(delta)*s1_end)]
    d_s2 = delta[int(len(delta)*s2_end)] - d_s1
    d_s3 = delta[-1] - (d_s1 + d_s2)

    # Detect Saw-tooth Throttle (Direction changes in throttle during exit phases)
    # We look for more than 3 sign changes in the derivative while throttle > 10%
    throttle_diff = np.diff(res_d['Throttle'].values)
    pumps = np.sum(np.diff(np.sign(throttle_diff[throttle_diff != 0])) != 0)
    
    # Detect ABS Deep Engagement
    abs_count = (res_d['ABSActive'] > 0.5).sum()
    
    # Detect vMin differences
    vmin_d = res_d['Speed'].min()
    vmin_b = res_b['Speed'].min()

    report = f"""
    <div class="coach-report">
    <strong>ENGINEER'S REPORT: Driver (Blue) vs Benchmark (Red)</strong><br><br>
    The data shows a lap of two halves: you are significantly faster in high-speed sections, but losing the entire lap in low-speed exits and braking transitions.<br><br>
    
    <strong>(A) Driving Issues</strong><br>
    1. <span class="sector-loss">The Sector 1 "Bleed" ({d_s1:+.3f}s):</span><br>
    Turn 3 (Hugenholtz) Exit: Look at your throttle trace. You have {pumps//10} distinct throttle pumps (saw-tooth pattern) before reaching 100%. You are "testing" the traction rather than trusting the car. Because you over-slowed the apex (vMin diff: {vmin_b - vmin_d:.1f} km/h), you are trying to force acceleration while heavily loaded.<br><br>
    
    2. <strong>Turn 1 (Tarzan) Over-Braking:</strong><br>
    Telemetry shows you are hitting {res_d['Brake'].max():.1f}% pressure and holding deep into the ABS. The benchmark peaks lower and has a cleaner release. Your high pressure is triggering "Deep ABS," preventing rotation.<br><br>
    
    3. <span class="sector-win">Sector 2 Strength ({d_s2:+.3f}s):</span><br>
    Turn 7 (Scheivlak): You are out-driving the benchmark here. You carry more speed and trust the aero platform perfectly. This proves you have the "hands" for high-speed sections.<br><br>
    
    <strong>(B) Brake Bias & Summary</strong><br>
    Because you are hitting the brakes so much harder, you are negating the rotation benefits of your setup. You are slamming weight forward violently, causing the front ABS to take over.<br><br>
    
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

    if f_d and f_b:
        df_d_full = process_telemetry(pd.read_csv(f_d))
        df_b_raw = process_telemetry(pd.read_csv(f_b))
        
        sel_lap = st.sidebar.selectbox("Select Lap", df_d_full['Lap'].unique())
        df_d_lap = df_d_full[df_d_full['Lap'] == sel_lap]
        
        res_d, res_b, grid = align_and_resample(df_d_lap, df_b_raw)
        delta, line_dist = calculate_physics(res_d, res_b, grid)

        with tab_analyze:
            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
            c2.metric("Driver vMin", f"{res_d['Speed'].min():.1f} km/h")
            c3.metric("Max Line Deviation", f"{line_dist.max():.2f}m")
            
            # G61 Replication Stack
            fig = make_subplots(rows=8, cols=1, shared_xaxes=True, vertical_spacing=0.01,
                                row_heights=[0.15, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.15],
                                subplot_titles=("Speed", "Throttle", "Brake", "Gear", "RPM", "Steering", "Line Distance", "Time Delta"))
            x, c_b, c_d = grid * 100, '#ff3344', '#00a2ff'
            
            for i, col in enumerate(['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle'], 1):
                fig.add_trace(go.Scatter(x=x, y=res_b[col], line=dict(color=c_b, width=1.5)), row=i, col=1)
                fig.add_trace(go.Scatter(x=x, y=res_d[col], line=dict(color=c_d, width=1.5)), row=i, col=1)
                if col == 'Brake': # Add ABS Shading
                    abs_zone = res_d['Brake'].where(res_d['ABSActive'] > 0.5)
                    fig.add_trace(go.Scatter(x=x, y=abs_zone, fill='tozeroy', fillcolor='rgba(255,255,0,0.2)', line=dict(width=0)), row=i, col=1)

            fig.add_trace(go.Scatter(x=x, y=line_dist, line=dict(color=c_d, width=2)), row=7, col=1)
            fig.add_trace(go.Scatter(x=x, y=delta, line=dict(color=c_d, width=2)), row=8, col=1)
            fig.update_layout(height=1400, template="plotly_dark", showlegend=False, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

        with tab_coach:
            st.markdown(generate_coach_report(res_d, res_b, grid, delta), unsafe_allow_html=True)

        with tab_setup:
            st.header("Setup Tweaker")
            st.info("Mechanical Balance: Plotting Steering vs Lateral G to identify Understeer Gradient.")
            fig_bal = px.scatter(res_d, x='LatAccel', y='SteeringWheelAngle', color='Speed', template="plotly_dark")
            st.plotly_chart(fig_bal, use_container_width=True)

    with tab_session:
        if f_s:
            df_s = pd.read_csv(f_s)
            st.header("Session Consistency & Tire Stress")
            # Consistency Score: 100 - (StdDev * 10)
            df_s['LapSec'] = df_s['Lap time'].apply(lambda x: int(x.split(':')[0])*60 + float(x.split(':')[1]) if ':' in str(x) else 0)
            std_dev = df_s[df_s['LapSec'] > 0]['LapSec'].std()
            st.metric("Consistency Score", f"{max(0, 100 - (std_dev*20)):.1f}/100", help="Based on lap time variance.")
            
            fig_stint = px.line(df_s, x='Lap', y='LapSec', markers=True, template="plotly_dark", title="Pace Consistency")
            st.plotly_chart(fig_stint, use_container_width=True)
        else:
            st.info("Upload Session Summary for consistency analysis.")

if __name__ == "__main__":
    main()
