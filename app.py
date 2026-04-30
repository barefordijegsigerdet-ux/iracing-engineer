import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# --- 1. CONFIGURATION & TRACK DATABASE ---
st.set_page_config(page_title="Race Engineer Pro | iRacing", layout="wide")

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

# Initialize Session State for Garage
if 'current_setup' not in st.session_state:
    st.session_state.current_setup = {
        "Brake Bias": 50.0, "Front ARB": 5, "Rear ARB": 3, 
        "Wing Angle": 6, "TC Map": 4, "ABS Map": 4
    }

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 20px; margin-bottom: 15px; font-family: 'Courier New'; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff4b4b; padding: 20px; margin-bottom: 15px; }
        .setup-card { background-color: #1c2128; border-left: 5px solid #ff8c00; padding: 20px; margin-bottom: 15px; }
        </style>
    """, unsafe_allow_html=True)

# --- 2. CORE PHYSICS ENGINE ---

def process_telemetry(df: pd.DataFrame, track_length: int) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    
    # Unit Normalization (m/s² to G)
    mapping = {'LatAccel': 'LatG', 'LongAccel': 'LonG', 'LonAccel': 'LonG'}
    for src, dest in mapping.items():
        if src in df.columns:
            df[dest] = pd.to_numeric(df[src], errors='coerce').fillna(0) / 9.81
    
    if 'LatG' not in df.columns: df['LatG'] = 0.0
    if 'LonG' not in df.columns: df['LonG'] = 0.0
    df['GSum'] = np.sqrt(df['LatG']**2 + df['LonG']**2)

    # Speed & Distance
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6
    
    if 'LapDist' not in df.columns and 'LapDistPct' in df.columns:
        pct = pd.to_numeric(df['LapDistPct'], errors='coerce').fillna(0)
        if pct.max() > 1.1: pct /= 100.0
        df['LapDist'] = pct * track_length

    for col in ['Throttle', 'Brake']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            if df[col].max() <= 1.1: df[col] *= 100.0
            
    if 'Lap' not in df.columns:
        df['Lap'] = (df['LapDist'].diff() < -100).cumsum()

    return df.sort_values(by='LapDist').drop_duplicates(subset=['LapDist'])

def align_and_resample(df_d, df_b, points=5000):
    max_dist = df_b['LapDist'].max()
    grid_meters = np.linspace(0, max_dist, points)
    
    def interp_lap(df):
        out = pd.DataFrame({'LapDist': grid_meters})
        # Linear Interpolation for Continuous Channels
        cont = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'GSum', 'RPM', 'Lat', 'Lon', 'ABSActive', 'TCActive']
        for col in cont:
            if col in df.columns: out[col] = np.interp(grid_meters, df['LapDist'], df[col])
        
        # Zero-Order Hold for Discrete Channels (Gear)
        if 'Gear' in df.columns:
            idx = np.searchsorted(df['LapDist'], grid_meters, side='right') - 1
            out['Gear'] = df['Gear'].iloc[np.clip(idx, 0, len(df)-1)].values
        return out

    res_d, res_b = interp_lap(df_d), interp_lap(df_b)
    res_d['SteeringSmooth'] = res_d['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    res_b['SteeringSmooth'] = res_b['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    return res_d, res_b, grid_meters

def calculate_physics(res_d, res_b, grid_m):
    # Time Delta (dt = ds / v)
    v_d, v_b = np.maximum(res_d['Speed'].values / 3.6, 1.0), np.maximum(res_b['Speed'].values / 3.6, 1.0)
    delta = np.cumsum(np.diff(grid_m, prepend=0) / v_d - np.diff(grid_m, prepend=0) / v_b)
    delta = delta - delta[0]
    
    # Signed Line Distance (Cross Product for Left/Right)
    tx, ty = np.gradient(res_b['Lon']), np.gradient(res_b['Lat'])
    ux, uy = res_d['Lon'] - res_b['Lon'], res_d['Lat'] - res_b['Lat']
    direction = np.sign(tx * uy - ty * ux)
    magnitude = np.sqrt(((res_d['Lat']-res_b['Lat'])*111000)**2 + ((res_d['Lon']-res_b['Lon'])*75000)**2)
    
    return delta, magnitude * direction

# --- 3. UI MODULES ---

def render_analyze_laps(res_d, res_b, grid_m, delta, line_dist):
    fig = make_subplots(rows=8, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("Speed (km/h)", "Throttle (%)", "Brake (%)", "Gear", "RPM", "Steering Angle", "Line Distance (m)", "Time Delta (s)"))
    c_b, c_d = '#ff3344', '#00a2ff'
    
    # Helper for dual traces
    def add_dual(row, col, is_step=False):
        # Benchmark (Solid Red)
        fig.add_trace(go.Scatter(x=grid_m, y=res_b[col], 
                                 line=dict(color=c_b, width=1, shape='hv' if is_step else None), 
                                 name="Bench"), row=row, col=1)
        # Driver (Solid Blue)
        fig.add_trace(go.Scatter(x=grid_m, y=res_d[col], 
                                 line=dict(color=c_d, width=1.8, shape='hv' if is_step else None), 
                                 name="Driver"), row=row, col=1)

    add_dual(1, 'Speed'); add_dual(2, 'Throttle'); add_dual(3, 'Brake')
    add_dual(4, 'Gear', is_step=True); add_dual(5, 'RPM'); add_dual(6, 'SteeringSmooth')
    
    # Line Distance (G61 Style Signed Deviation)
    fig.add_hline(y=0, line_color=c_b, line_width=1, row=7, col=1)
    fig.add_trace(go.Scatter(x=grid_m, y=line_dist, line=dict(color=c_d, width=1.5)), row=7, col=1)
    
    # Delta
    fig.add_trace(go.Scatter(x=grid_m, y=delta, line=dict(color=c_d, width=2)), row=8, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="grey", row=8, col=1)

    fig.update_xaxes(showticklabels=True, title_text="Distance (m)", gridcolor='#30363d', griddash='dash')
    fig.update_yaxes(gridcolor='#30363d', griddash='dash')
    fig.update_layout(height=1800, template="plotly_dark", showlegend=False, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

def render_driver_coach(res_d, res_b, grid, delta):
    st.header("🧠 Physics-Based Driver Coach")
    # Heuristic: Throttle Stabbing
    t_roll_max = res_d['Throttle'].rolling(window=50).max()
    t_roll_min = res_d['Throttle'].rolling(window=50).min()
    if ((t_roll_max > 80) & (t_roll_min < 20)).any():
        st.markdown('<div class="coach-card"><strong>Unstable Platform:</strong> Stop stabbing the throttle. Squeeze the pedal to load the rear tires.</div>', unsafe_allow_html=True)
    
    # Heuristic: ABS Overshoot
    if ((res_d['ABSActive'] > 0.5) & (res_d['Brake'] < 30)).any():
        st.markdown('<div class="critical-card"><strong>ABS Over-reliance:</strong> You are triggering ABS during turn-in. Reduce brake pressure to allow rotation.</div>', unsafe_allow_html=True)

def render_setup_tweaker(res_d, issue, setup_type):
    st.header(f"🔧 Setup Tweaker | {setup_type} Mode")
    curr = st.session_state.current_setup
    
    if setup_type == "Fixed":
        st.warning("Fixed Setup: Mechanicals locked. Adjust Brake Bias or Electronic Maps.")
        braking = res_d[res_d['Brake']>5]
        if not braking.empty:
            abs_duty = (braking['ABSActive'] > 0.5).mean()
            if abs_duty > 0.5:
                st.error(f"Suggestion: Move Brake Bias Forward. Current: {curr['Brake Bias']}% -> Target: {curr['Brake Bias']+0.5}%")
        return

    # Open Setup: Balance Signature Check
    mask = (res_d['Speed'] > 60) & (res_d['Brake'] < 5)
    sig = res_d[mask]
    if not sig.empty:
        fig = px.scatter(sig, x=sig['LatG'].abs(), y=sig['SteeringSmooth'].abs(), color='Speed', template="plotly_dark", title="Balance Signature")
        st.plotly_chart(fig, use_container_width=True)
    
    if issue == "Mid-Corner Understeer":
        st.markdown(f'<div class="setup-card"><strong>Recommendation:</strong> Soften Front ARB (Current: {curr["Front ARB"]} -> Target: {curr["Front ARB"]-1})</div>', unsafe_allow_html=True)

def render_garage():
    st.header("🛠️ Garage | Vehicle Configuration")
    cols = st.columns(3)
    for i, (k, v) in enumerate(st.session_state.current_setup.items()):
        with cols[i % 3]:
            st.session_state.current_setup[k] = st.number_input(f"Current {k}", value=float(v))

# --- 4. MAIN APP LOOP ---

def main():
    apply_custom_css()
    with st.sidebar:
        st.title("🛠️ Config")
        track = st.selectbox("Track", list(TRACK_DB.keys()))
        setup_mode = st.radio("Setup Rule", ["Open", "Fixed"])
        st.divider()
        f_d = st.file_uploader("Driver Telemetry", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry", type=['csv'])
        f_s = st.file_uploader("Session Summary", type=['csv'])
        issue = st.selectbox("Reported Issue", ["None", "Mid-Corner Understeer", "Braking Instability"])

    t1, t2, t3, t4, t5 = st.tabs(["📊 Analyze Laps", "⏱️ Session Analyzer", "🧠 Driver Coach", "🔧 Setup Tweaker", "🛠️ Garage"])

    with t5: render_garage()

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d), TRACK_DB[track])
        df_b = process_telemetry(pd.read_csv(f_b), TRACK_DB[track])
        
        laps = df_d['Lap'].unique()
        sel_lap = st.sidebar.selectbox("Select Telemetry Lap", laps)
        res_d, res_b, grid_m = align_and_resample(df_d[df_d['Lap']==sel_lap], df_b)
        delta, line_dist = calculate_physics(res_d, res_b, grid_m)

        with t1: render_analyze_laps(res_d, res_b, grid_m, delta, line_dist)
        with t3: render_driver_coach(res_d, res_b, grid_m, delta)
        with t4: render_setup_tweaker(res_d, issue, setup_mode)
    
    with t2:
        if f_s:
            df_s = pd.read_csv(f_s)
            st.plotly_chart(px.line(df_s, x='Lap', y='Fuel level', template="plotly_dark", title="Fuel Stint"), use_container_width=True)
        else: st.info("Upload Session Summary for stint analysis.")

if __name__ == "__main__":
    main()
