import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. SYSTEM CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Porsche 992.2 Cup", layout="wide")

# Replace these strings with your exact local filenames for "No-Upload" mode
DEFAULT_DRIVER = "Garage_61_-_Jonas_Hauerbach_-_Porsche_911_Cup__992_2__-_Circuit_Zandvoort__Grand_Prix__-_01_41_980_-_01KQAKNQHNGGR7RTTC9DMD0F59.csv"
DEFAULT_BENCHMARK = "Garage_61_-_Leeroy_Malmross_-_Porsche_911_Cup__992_2__-_Circuit_Zandvoort__Grand_Prix__-_01_41_332_-_01KQ5E93PS1W2T3SH5ECRJNCF6.csv"

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 15px; margin-bottom: 10px; border-radius: 4px; border: 1px solid #30363d; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff3344; padding: 15px; margin-bottom: 10px; border-radius: 4px; border: 1px solid #4d1b1e; }
        .setup-card { background-color: #1c2128; border-left: 5px solid #ff8c00; padding: 15px; margin-bottom: 10px; border-radius: 4px; }
        </style>
    """, unsafe_allow_html=True)

if 'garage' not in st.session_state:
    st.session_state.garage = {"Brake Bias": 54.0, "TC Map": 4, "ABS Map": 4, "ARB F/R": "5/3"}

# --- 2. CORE PHYSICS ENGINE ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    
    # Physics Normalization: m/s² to G (The 9.81 Fix)
    for src, dest in {'LatAccel': 'LatG', 'LongAccel': 'LonG', 'LonAccel': 'LonG'}.items():
        if src in df.columns:
            df[dest] = pd.to_numeric(df[src], errors='coerce').fillna(0) / 9.81
    
    if 'LatG' in df.columns and 'LonG' in df.columns:
        df['GSum'] = np.sqrt(df['LatG']**2 + df['LonG']**2)

    # Convert ABS Strings
    if 'ABSActive' in df.columns:
        df['ABSActive'] = df['ABSActive'].map({'true': 1, 'false': 0, 1: 1, 0: 0}).fillna(0)

    # Normalize Speed to km/h
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6 
    
    # Distance handling
    dist_col = 'Distance' if 'Distance' in df.columns else ('LapDist' if 'LapDist' in df.columns else None)
    if dist_col:
        df['Dist'] = pd.to_numeric(df[dist_col], errors='coerce')
    
    return df.sort_values('Dist') if 'Dist' in df.columns else df

def align_and_resample(df_d, df_b, points=5000):
    # Anchor to Benchmark Distance to fix +0.1s Delta Error
    max_dist = df_b['Dist'].max()
    grid = np.linspace(0, max_dist, points)

    def interp_lap(df):
        out = pd.DataFrame({'Dist': grid})
        for col in ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'GSum', 'ABSActive']:
            if col in df.columns:
                out[col] = np.interp(grid, df['Dist'], df[col])
        return out

    res_d, res_b = interp_lap(df_d), interp_lap(df_b)
    
    # Precise Time Delta Calculation (dt = ds/v)
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    ds = np.diff(grid, prepend=0)
    delta = np.cumsum(ds / v_d - ds / v_b)
    
    return res_d, res_b, grid, delta

# --- 3. THE PHYSICS COACH (Heuristics) ---

def render_driver_coach(res_d, res_b, grid, delta):
    st.header("🧠 Driver Coach: Physics Audit")
    
    # Segment by Steering Lock > 15 deg
    is_corner = np.abs(res_d['SteeringWheelAngle']) > 15
    events = (is_corner != pd.Series(is_corner).shift()).cumsum()
    corner_count = 0

    for eid in events.unique():
        idx = events == eid
        if is_corner[idx].iloc[0] and len(res_d[idx]) > 40:
            corner_count += 1
            d_ev, b_ev = res_d[idx], res_b[idx]
            
            # PHASE 1: ENTRY (ABS Saturation)
            abs_entry = (d_ev['ABSActive'] > 0.5) & (np.abs(d_ev['SteeringWheelAngle']) > 20)
            if abs_entry.any():
                st.markdown(f"""<div class="critical-card">
                    <strong>EVENT {corner_count} | Entry:</strong> ABS Saturated Turn-In.<br>
                    <strong>Why:</strong> ABS triggered during steer-loading. <strong>Impact:</strong> Front tires saturated; rotation killed.
                </div>""", unsafe_allow_html=True)

            # PHASE 2: MID (V-Min Displacement)
            d_vmin_m = grid[d_ev['Speed'].idxmin()]
            b_vmin_m = grid[b_ev['Speed'].idxmin()]
            if (d_vmin_m - b_vmin_m) < -4.0:
                st.markdown(f"""<div class="coach-card">
                    <strong>EVENT {corner_count} | Mid:</strong> Early Over-Slowing.<br>
                    <strong>Why:</strong> V-Min reached {abs(d_vmin_m-b_vmin_m):.1f}m too early. <strong>Impact:</strong> Lost rolling momentum.
                </div>""", unsafe_allow_html=True)

            # PHASE 3: EXIT (Sawtooth Smoothness)
            t_rate = np.abs(np.gradient(d_ev['Throttle']))
            if np.sum(t_rate > 40) > 8:
                st.markdown(f"""<div class="critical-card">
                    <strong>EVENT {corner_count} | Exit:</strong> Sawtooth Throttle Detected.<br>
                    <strong>Why:</strong> Rapid pedal oscillations. <strong>Impact:</strong> Pitch instability ruining rear traction.
                </div>""", unsafe_allow_html=True)

# --- 4. MAIN INTERFACE ---

def main():
    apply_custom_css()
    st.sidebar.title("🛠️ Config")
    setup_mode = st.sidebar.radio("Setup Rule", ["Fixed", "Open"])
    
    f_d = st.sidebar.file_uploader("Driver CSV", type=['csv'])
    f_b = st.sidebar.file_uploader("Benchmark CSV", type=['csv'])

    try:
        if f_d and f_b:
            df_d, df_b = process_telemetry(pd.read_csv(f_d)), process_telemetry(pd.read_csv(f_b))
        else:
            df_d, df_b = process_telemetry(pd.read_csv(DEFAULT_DRIVER)), process_telemetry(pd.read_csv(DEFAULT_BENCHMARK))
            st.sidebar.success("Using Default Zandvoort Laps")
    except Exception as e:
        st.error(f"Waiting for Data Ingestion... Error: {e}")
        return

    res_d, res_b, grid, delta = align_and_resample(df_d, df_b)
    
    t1, t2, t3 = st.tabs(["📊 Analyze Laps", "🧠 Driver Coach", "🔧 Setup Tweaker"])
    
    with t1:
        st.metric("Total Time Delta", f"{delta[-1]:.3f}s", delta_color="inverse")
        fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02)
        fig.add_trace(go.Scatter(x=grid, y=res_b['Speed'], name="Bench", line=dict(color='#ff3344')), row=1, col=1)
        fig.add_trace(go.Scatter(x=grid, y=res_d['Speed'], name="Driver", line=dict(color='#00a2ff')), row=1, col=1)
        fig.add_trace(go.Scatter(x=grid, y=res_d['Throttle'], name="Throttle", line=dict(color='#00ff88')), row=2, col=1)
        fig.add_trace(go.Scatter(x=grid, y=res_d['Brake'], name="Brake", line=dict(color='#ff3344')), row=3, col=1)
        fig.add_trace(go.Scatter(x=grid, y=res_d['SteeringWheelAngle'], name="Steer", line=dict(color='white')), row=4, col=1)
        fig.add_trace(go.Scatter(x=grid, y=delta, name="Delta", fill='tozeroy', line=dict(color='yellow')), row=5, col=1)
        fig.update_layout(height=1200, template="plotly_dark", showlegend=False, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with t2: render_driver_coach(res_d, res_b, grid, delta)

    with t3:
        st.header("🔧 Setup Tweaker")
        issue = st.selectbox("Issue", ["None", "Mid-Corner Understeer", "Braking Instability"])
        if setup_mode == "Fixed":
            st.warning("Fixed Setup Mode: Limited to Brake Bias / Electronic Maps.")
            if issue == "Braking Instability":
                st.success("Recommendation: Move Brake Bias Forward (Current: 54.0%) to stabilize entry.")
        else:
            st.info("Open Setup Mode: Full mechanical validation active.")

if __name__ == "__main__":
    main()
