import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Physics Engine V3", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 20px; margin-bottom: 15px; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff4b4b; padding: 20px; margin-bottom: 15px; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING & UNIT NORMALIZATION ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    
    # 1. Unit Normalization (m/s² to G)
    accel_cols = ['LatAccel', 'LongAccel']
    for col in accel_cols:
        if col in df.columns:
            # Create G columns and normalize
            df[col.replace('Accel', 'G')] = pd.to_numeric(df[col], errors='coerce').fillna(0) / 9.81
    
    # 2. Standard Normalization
    if 'Speed' in df.columns:
        df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
        if df['Speed'].max() < 100: df['Speed'] *= 3.6
        
    if 'LapDistPct' in df.columns:
        df['LapDistPct'] = pd.to_numeric(df['LapDistPct'], errors='coerce').fillna(0)
        if df['LapDistPct'].max() > 1.1: df['LapDistPct'] /= 100.0

    for col in ['Throttle', 'Brake']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            if df[col].max() <= 1.1: df[col] *= 100.0
            
    # 3. Math Channel: G-Sum
    df['GSum'] = np.sqrt(df['LatG']**2 + df['LonG']**2)
    
    return df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])

def align_and_resample(df_d, df_b, points=5000):
    """Ensures both laps start at the exact same track coordinate."""
    grid = np.linspace(0, 1, points)
    
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'ABSActive', 'GSum']
        for col in channels:
            if col in df.columns:
                out[col] = np.interp(grid, df['LapDistPct'], df[col])
            else:
                out[col] = 0.0
        return out

    res_d = interp_channel(df_d)
    res_b = interp_channel(df_b)
    
    # Data Smoothing (Ghost Coach Fix)
    res_d['SteeringSmooth'] = res_d['SteeringWheelAngle'].rolling(window=15, center=True).min().ffill().bfill()
    res_d['SteeringSmooth'] = res_d['SteeringWheelAngle'].rolling(window=15, center=True).mean().ffill().bfill()
    
    return res_d, res_b, grid

def calculate_physics(res_d, res_b, grid):
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    
    # Spatial Integration for Delta
    ds = np.diff(grid, prepend=0) * 4000 # Proxy track length
    delta = np.cumsum(ds / v_d - ds / v_b)
    
    # Alignment Reset: Force delta to start at 0
    delta = delta - delta[0]
    
    # Smoothing Delta
    delta_smooth = pd.Series(delta).rolling(window=20, center=True).mean().ffill().bfill().values
    
    return delta_smooth

# --- ENGINE: EVENT DETECTION ---

def detect_events(res_d, threshold=15):
    """Identifies corners: Steering > threshold for > 0.5s (approx 25 samples)."""
    is_event = np.abs(res_d['SteeringSmooth']) > threshold
    event_ids = (is_event != pd.Series(is_event).shift()).cumsum()
    
    events = []
    for eid in event_ids.unique():
        idx = event_ids == eid
        # Duration check: 5000 points / 100s lap = 50Hz. 0.5s = 25 samples.
        if is_event[idx].iloc[0] and len(res_d[idx]) > 25:
            events.append(res_d.index[idx])
            
    # Fallback if no events found
    if not events and threshold > 10:
        return detect_events(res_d, threshold=10)
        
    return events

# --- MODULES: COACH & SETUP ---

def render_driver_coach(res_d, res_b, grid, delta):
    st.header("🧠 Physics-Based Coaching")
    events = detect_events(res_d)
    
    if not events:
        st.warning("No significant cornering events detected. Check steering telemetry.")
        return

    # Find Top 3 Time Loss Events
    event_losses = []
    for ev_idx in events:
        loss = delta[ev_idx[-1]] - delta[ev_idx[0]]
        event_losses.append((ev_idx, loss))
    
    top_3 = sorted(event_losses, key=lambda x: x[1], reverse=True)[:3]

    for i, (ev_idx, loss) in enumerate(top_3, 1):
        d_ev = res_d.loc[ev_idx]
        b_ev = res_b.loc[ev_idx]
        g_ev = grid[ev_idx]
        
        with st.container():
            st.subheader(f"Event {i}: Corner at {grid[ev_idx[0]]*100:.1f}% | Loss: {loss:.3f}s")
            
            # 1. Entry: Brake Release
            d_br = np.gradient(d_ev['Brake'], g_ev).min()
            b_br = np.gradient(b_ev['Brake'], g_ev).min()
            if d_br < b_br * 1.2:
                st.markdown('<div class="coach-card"><strong>Rapid Pitch Recovery:</strong> Releasing brake too fast. Nose lifting, losing front grip.</div>', unsafe_allow_html=True)
            
            # 2. Mid: V-Min Displacement
            if np.argmin(d_ev['Speed'].values) < np.argmin(b_ev['Speed'].values) - 25:
                st.markdown('<div class="coach-card"><strong>Early Over-slowing:</strong> Reaching V-Min too early. Carry more entry speed.</div>', unsafe_allow_html=True)
            
            # 3. Porsche 992 ABS Check
            if np.any((d_ev['ABSActive'] > 0.5) & (np.abs(d_ev['SteeringSmooth']) > 15)):
                st.markdown('<div class="critical-card"><strong>ABS-Induced Understeer:</strong> Heavy ABS usage while turning is locking the platform.</div>', unsafe_allow_html=True)

def render_setup_tweaker(res_d, driver_issue):
    st.header("🔧 Setup Tweaker")
    
    # 4. Balance Signature Filtering
    # Only Speed > 60 and Brake < 5%
    mask = (res_d['Speed'] > 60) & (res_d['Brake'] < 5)
    sig_data = res_d[mask]
    
    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sig_data['LatG'].abs(), y=sig_data['SteeringSmooth'].abs(), 
                                 mode='markers', marker=dict(color=sig_data['Speed'], size=4, colorscale='Viridis')))
        fig.update_layout(template="plotly_dark", title="Balance Signature (Filtered)", 
                          xaxis=dict(title="Lateral G", range=[0, 2.5]), 
                          yaxis=dict(title="Steering Angle", range=[0, 120]))
        st.plotly_chart(fig, use_container_width=True)
        
    with col2:
        if driver_issue == "Understeer":
            # Check for plateau
            high_g = sig_data[sig_data['LatG'].abs() > 1.2]
            if not high_g.empty and (high_g['SteeringSmooth'].max() - high_g['SteeringSmooth'].min() > 30):
                st.error("VALIDATED: Mechanical Understeer. LatG plateaued while Steering increased.")
            else:
                st.warning("OVERRIDE: Balance is linear. You are scrubbing the tires by over-turning.")

# --- MAIN ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer Pro | Physics Engine V3")
    
    with st.sidebar:
        f_d = st.file_uploader("Driver Telemetry", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry", type=['csv'])
        issue = st.selectbox("Reported Issue", ["None", "Understeer", "Oversteer"])

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d))
        df_b = process_telemetry(pd.read_csv(f_b))
        res_d, res_b, grid = align_and_resample(df_d, df_b)
        delta = calculate_physics(res_d, res_b, grid)

        t1, t2, t3 = st.tabs(["📊 Telemetry", "🧠 Physics Coach", "🔧 Setup Tweaker"])
        
        with t1:
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True)
            fig.add_trace(go.Scatter(x=grid*100, y=delta, name="Delta", line=dict(color='red')), row=1, col=1)
            fig.add_trace(go.Scatter(x=grid*100, y=res_d['LatG'], name="LatG", line=dict(color='cyan')), row=2, col=1)
            fig.add_trace(go.Scatter(x=grid*100, y=res_d['SteeringSmooth'], name="Steering", line=dict(color='white')), row=3, col=1)
            fig.update_layout(height=800, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
            
        with t2: render_driver_coach(res_d, res_b, grid, delta)
        with t3: render_setup_tweaker(res_d, issue)

if __name__ == "__main__":
    main()
