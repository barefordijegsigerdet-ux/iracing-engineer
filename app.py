import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff4b4b; padding: 20px; margin-bottom: 15px; font-family: 'Courier New'; }
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
        cont = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'GSum', 'RPM', 'Lat', 'Lon', 'ABSActive']
        for col in cont:
            if col in df.columns: out[col] = np.interp(grid_meters, df['LapDist'], df[col])
        if 'Gear' in df.columns:
            idx = np.searchsorted(df['LapDist'], grid_meters, side='right') - 1
            out['Gear'] = df['Gear'].iloc[np.clip(idx, 0, len(df)-1)].values
        return out

    res_d, res_b = interp_lap(df_d), interp_lap(df_b)
    res_d['SteeringSmooth'] = res_d['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    res_b['SteeringSmooth'] = res_b['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    return res_d, res_b, grid_meters

def calculate_physics(res_d, res_b, grid_m):
    v_d, v_b = np.maximum(res_d['Speed'].values / 3.6, 1.0), np.maximum(res_b['Speed'].values / 3.6, 1.0)
    delta = np.cumsum(np.diff(grid_m, prepend=0) / v_d - np.diff(grid_m, prepend=0) / v_b)
    delta = delta - delta[0]
    
    tx, ty = np.gradient(res_b['Lon']), np.gradient(res_b['Lat'])
    ux, uy = res_d['Lon'] - res_b['Lon'], res_d['Lat'] - res_b['Lat']
    direction = np.sign(tx * uy - ty * ux)
    magnitude = np.sqrt(((res_d['Lat']-res_b['Lat'])*111000)**2 + ((res_d['Lon']-res_b['Lon'])*75000)**2)
    
    return delta, magnitude * direction

# --- 3. CLINICAL COACHING ENGINE ---

def detect_corners(res_d, threshold=15):
    is_event = np.abs(res_d['SteeringSmooth']) > threshold
    event_ids = (is_event != pd.Series(is_event).shift()).cumsum()
    events = []
    for eid in event_ids.unique():
        idx = event_ids == eid
        if is_event[idx].iloc[0] and len(res_d[idx]) > 25:
            events.append(res_d.index[idx])
    return events

def render_driver_coach(res_d, res_b, grid_m, delta):
    st.header("🧠 Clinical Performance Audit")
    corners = detect_corners(res_d)
    
    if not corners:
        st.info("No significant cornering events detected for audit.")
        return

    for i, idx in enumerate(corners, 1):
        d_ev, b_ev, g_ev = res_d.loc[idx], res_b.loc[idx], grid_m[idx]
        
        # 1. ENTRY: ABS Saturated Turn-In
        abs_turn_in = (d_ev['Brake'] > 5) & (np.abs(d_ev['SteeringSmooth']) > 15) & (d_ev['ABSActive'] > 0.5)
        if abs_turn_in.any():
            abs_pct = abs_turn_in.mean() * 100
            st.error(f"**EVENT {i} | WHAT:** ABS Saturated Turn-In. **WHERE:** Corner Entry. **WHY:** ABS active for {abs_pct:.1f}% of the zone while steering > 15°. **IMPACT:** You are asking front tires to do two jobs. This kills rotation and results in heavy mid-corner understeer.")

        # 2. MID: Early Over-Slowing
        d_vmin_idx = d_ev['Speed'].idxmin()
        b_vmin_idx = b_ev['Speed'].idxmin()
        dist_diff = grid_m[d_vmin_idx] - grid_m[b_vmin_idx]
        if dist_diff < -3.0:
            st.warning(f"**EVENT {i} | WHAT:** Early Over-Slowing. **WHERE:** Mid-Corner. **WHY:** V-Min reached {abs(dist_diff):.1f}m before benchmark apex. **IMPACT:** You are 'parking the car' at the center. This kills rolling speed and exit momentum.")

        # 3. EXIT: Unstable Platform (Sawtooth)
        exit_df = d_ev.loc[d_vmin_idx:]
        if len(exit_df) > 30:
            t_diff = np.diff(exit_df['Throttle'].values)
            stabs = np.sum(np.diff(np.sign(t_diff[np.abs(t_diff) > 1.0])) != 0) // 2
            if stabs >= 2:
                st.error(f"**EVENT {i} | WHAT:** Unstable Platform (Sawtooth Throttle). **WHERE:** Corner Exit. **WHY:** {stabs} distinct throttle stabs detected. **IMPACT:** Pitch oscillations prevent rear tires from finding a stable contact patch, forcing corrective steering and killing top speed.")

# --- 4. UI & TELEMETRY STACK ---

def render_analyze_laps(res_d, res_b, grid_m, delta, line_dist):
    fig = make_subplots(rows=8, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=("Speed (km/h)", "Throttle (%)", "Brake (%)", "Gear", "RPM", "Steering Angle", "Line Distance (m)", "Time Delta (s)"))
    c_b, c_d = '#ff3344', '#00a2ff'
    
    def add_dual(row, col, is_step=False):
        fig.add_trace(go.Scatter(x=grid_m, y=res_b[col], line=dict(color=c_b, width=1, shape='hv' if is_step else None)), row=row, col=1)
        fig.add_trace(go.Scatter(x=grid_m, y=res_d[col], line=dict(color=c_d, width=1.8, shape='hv' if is_step else None)), row=row, col=1)

    add_dual(1, 'Speed'); add_dual(2, 'Throttle'); add_dual(3, 'Brake')
    add_dual(4, 'Gear', True); add_dual(5, 'RPM'); add_dual(6, 'SteeringSmooth')
    
    fig.add_hline(y=0, line_color=c_b, line_width=1, row=7, col=1)
    fig.add_trace(go.Scatter(x=grid_m, y=line_dist, line=dict(color=c_d, width=1.5)), row=7, col=1)
    fig.add_trace(go.Scatter(x=grid_m, y=delta, line=dict(color=c_d, width=2)), row=8, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="grey", row=8, col=1)

    fig.update_xaxes(showticklabels=True, title_text="Distance (m)", gridcolor='#30363d', griddash='dash')
    fig.update_yaxes(gridcolor='#30363d', griddash='dash')
    fig.update_layout(height=1800, template="plotly_dark", showlegend=False, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# --- 5. MAIN LOOP ---

def main():
    apply_custom_css()
    with st.sidebar:
        st.title("🛠️ Config")
        track = st.selectbox("Track", list(TRACK_DB.keys()))
        setup_mode = st.radio("Setup Rule", ["Open", "Fixed"])
        st.divider()
        f_d = st.file_uploader("Driver Telemetry", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry", type=['csv'])
        issue = st.selectbox("Reported Issue", ["None", "Mid-Corner Understeer", "Braking Instability"])

    t1, t2, t3, t4 = st.tabs(["📊 Analyze Laps", "🧠 Driver Coach", "🔧 Setup Tweaker", "🛠️ Garage"])

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d), TRACK_DB[track])
        df_b = process_telemetry(pd.read_csv(f_b), TRACK_DB[track])
        
        laps = df_d['Lap'].unique()
        sel_lap = st.sidebar.selectbox("Select Telemetry Lap", laps)
        res_d, res_b, grid_m = align_and_resample(df_d[df_d['Lap']==sel_lap], df_b)
        delta, line_dist = calculate_physics(res_d, res_b, grid_m)

        with t1: render_analyze_laps(res_d, res_b, grid_m, delta, line_dist)
        with t2: render_driver_coach(res_d, res_b, grid_m, delta)
        with t3: 
            st.header("🔧 Setup Tweaker")
            if setup_mode == "Fixed":
                st.warning("Fixed Setup: Adjust Brake Bias only.")
            else:
                st.info("Open Setup: Mechanical validation active.")
        with t4:
            st.header("🛠️ Garage")
            for k, v in st.session_state.current_setup.items():
                st.session_state.current_setup[k] = st.number_input(f"Current {k}", value=float(v))
    else:
        st.info("Awaiting telemetry files.")

if __name__ == "__main__":
    main()
