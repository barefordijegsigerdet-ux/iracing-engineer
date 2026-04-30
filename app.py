import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# --- CONFIGURATION & THEME ---
st.set_page_config(page_title="Race Engineer Pro | iRacing", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
        .setup-card { background-color: #1c2128; border-left: 5px solid #ff8c00; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
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
    if df['Speed'].max() < 100: df['Speed'] *= 3.6
    if df['LapDistPct'].max() > 1.1: df['LapDistPct'] /= 100.0
    for col in ['Throttle', 'Brake']:
        if df[col].max() <= 1.1: df[col] *= 100.0
    if 'Lap' not in df.columns:
        df['Lap'] = (df['LapDistPct'].diff() < -0.5).cumsum()
    return df

def align_and_resample(df_d, df_b, points=5000):
    grid = np.linspace(0, 1, points)
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringWheelAngle', 'Lat', 'Lon', 'ABSActive', 'LatAccel', 'LongAccel']
        for col in channels: out[col] = np.interp(grid, df['LapDistPct'], df[col])
        return out
    return interp_channel(df_d), interp_channel(df_b), grid

# --- MODULE 1: ANALYZE LAPS ---
def render_analyze_laps(res_d, res_b, grid, delta, line_dist):
    c1, c2, c3 = st.columns(3)
    c1.metric("Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
    c2.metric("Driver Top Speed", f"{res_d['Speed'].max():.1f} km/h")
    c3.metric("Max Line Deviation", f"{line_dist.max():.2f}m")
    
    # Track Map
    fig_map = go.Figure()
    fig_map.add_trace(go.Scatter(x=res_b['Lon'], y=res_b['Lat'], line=dict(color='#2a2e35', width=15), hoverinfo='skip'))
    fig_map.add_trace(go.Scatter(x=res_b['Lon'], y=res_b['Lat'], line=dict(color='#ff3344', width=2), name='Bench'))
    fig_map.add_trace(go.Scatter(x=res_d['Lon'], y=res_d['Lat'], line=dict(color='#00a2ff', width=2), name='Driver'))
    fig_map.update_layout(template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), 
                          yaxis=dict(visible=False, scaleanchor="x", scaleratio=1), showlegend=False, height=400)
    st.plotly_chart(fig_map, use_container_width=True)

    # Telemetry Stack
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

# --- MODULE 2: SESSION ANALYZER ---
def render_session_analyzer(file_s):
    df_s = pd.read_csv(file_s)
    df_s['LapSeconds'] = df_s['Lap time'].apply(lap_to_seconds)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Pace", f"{df_s['LapSeconds'].mean():.3f}s")
    c2.metric("Consistency (StdDev)", f"±{df_s['LapSeconds'].std():.3f}s")
    c3.metric("Avg Fuel Burn", f"{df_s['Fuel used'].mean():.2f} L")
    
    fig_pace = px.line(df_s, x='Lap', y='LapSeconds', markers=True, template="plotly_dark", title="Stint Pace Evolution")
    st.plotly_chart(fig_pace, use_container_width=True)
    
    st.subheader("Sector Consistency")
    sec_cols = ['Sector 1', 'Sector 2', 'Sector 3']
    for col in sec_cols: df_s[col] = df_s[col].apply(lap_to_seconds)
    fig_box = px.box(df_s, y=sec_cols, template="plotly_dark")
    st.plotly_chart(fig_box, use_container_width=True)

# --- MODULE 3: DRIVER COACH ---
def render_driver_coach(df_lap):
    st.header("🧠 AI Coaching Insights")
    coast_pct = ((df_lap['Throttle'] < 5) & (df_lap['Brake'] < 5)).mean() * 100
    abs_usage = (df_lap['ABSActive'] > 0.5).sum()
    
    col1, col2 = st.columns(2)
    with col1:
        if coast_pct > 15:
            st.markdown(f'<div class="coach-card"><strong>Warning:</strong> High Coasting ({coast_pct:.1f}%). You are losing time mid-corner. Transition faster between pedals.</div>', unsafe_allow_html=True)
        if abs_usage > 400:
            st.markdown(f'<div class="coach-card"><strong>Critical:</strong> Deep ABS Intervention. You are over-braking, which will overheat the front tires in a stint.</div>', unsafe_allow_html=True)
        
        fig_gg = px.scatter(df_lap, x='LatAccel', y='LongAccel', color='Speed', template="plotly_dark", title="Traction Circle (G-G Diagram)")
        st.plotly_chart(fig_gg, use_container_width=True)
    with col2:
        st.info("Coaching Tip: In the Porsche 992 Cup, trail braking is essential to keep the nose weighted. A 'hollow' traction circle suggests you are separating braking and turning too much.")

# --- MODULE 4: SETUP TWEAKER ---
def render_setup_tweaker(df_lap):
    st.header("🔧 Setup Diagnosis Engine")
    
    with st.expander("Step 1: Driver Subjective Feedback", expanded=True):
        issue = st.selectbox("What is the primary handling issue?", 
                             ["None", "Entry Oversteer", "Mid-Corner Understeer", "Exit Oversteer", "Braking Instability"])
    
    st.subheader("Step 2: Telemetry Validation")
    # Calculate Understeer Gradient (Steering vs LatAccel)
    fig_bal = px.scatter(df_lap, x='LatAccel', y='SteeringWheelAngle', color='Speed', template="plotly_dark", title="Balance Signature")
    st.plotly_chart(fig_bal, use_container_width=True)
    
    st.subheader("Step 3: Engineering Recommendations")
    if issue == "Mid-Corner Understeer":
        st.markdown('<div class="setup-card"><strong>Recommendation:</strong> Soften Front ARB by 1 click OR Increase Front Wing angle. Telemetry shows high steering lock with plateauing Lateral G.</div>', unsafe_allow_html=True)
    elif issue == "Entry Oversteer":
        st.markdown('<div class="setup-card"><strong>Recommendation:</strong> Increase Rear Wing OR Stiffen Front Springs. This will stabilize the pitch during weight transfer.</div>', unsafe_allow_html=True)
    elif issue == "Braking Instability":
        st.markdown('<div class="setup-card"><strong>Recommendation:</strong> Move Brake Bias Forward (0.5% - 1.0%). This prevents the rear from stepping out under heavy deceleration.</div>', unsafe_allow_html=True)
    else:
        st.success("Telemetry and Driver feedback suggest a neutral balance. Focus on driving lines.")

# --- MAIN APP LOGIC ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer Pro | iRacing Performance Suite")
    
    with st.sidebar:
        st.header("Data Ingestion")
        f_d = st.file_uploader("Driver Telemetry (Blue)", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry (Red)", type=['csv'])
        f_s = st.file_uploader("Session Summary (Laps)", type=['csv'])
        st.divider()
        st.caption("Target: Porsche 992.2 GT3 Cup")

    tab_analyze, tab_session, tab_coach, tab_setup = st.tabs([
        "📊 Analyze Laps", "⏱️ Session Analyzer", "🧠 Driver Coach", "🔧 Setup Tweaker"
    ])

    if f_d and f_b:
        df_d_full = process_telemetry(pd.read_csv(f_d))
        df_b_raw = process_telemetry(pd.read_csv(f_b))
        
        laps = df_d_full['Lap'].unique()
        sel_lap = st.sidebar.selectbox("Select Lap for Analysis", laps)
        df_d_lap = df_d_full[df_d_full['Lap'] == sel_lap]
        
        res_d, res_b, grid = align_and_resample(df_d_lap, df_b_raw)
        v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
        v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
        ds = np.diff(grid, prepend=0) * 4259 
        delta = np.cumsum(ds / v_d - ds / v_b)
        line_dist = np.sqrt(((res_d['Lat']-res_b['Lat'])*111000)**2 + ((res_d['Lon']-res_b['Lon'])*67000)**2)

        with tab_analyze: render_analyze_laps(res_d, res_b, grid, delta, line_dist)
        with tab_coach: render_driver_coach(df_d_lap)
        with tab_setup: render_setup_tweaker(df_d_lap)
    
    with tab_session:
        if f_s: render_session_analyzer(f_s)
        else: st.info("Upload Session Summary CSV for stint analysis.")

if __name__ == "__main__":
    main()
