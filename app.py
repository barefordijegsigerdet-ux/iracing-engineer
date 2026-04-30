import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CONFIGURATION ---
st.set_page_config(page_title="Race Engineer Pro | Physics Suite", layout="wide")

def apply_custom_css():
    st.markdown("""
        <style>
        .main { background-color: #0e1117; color: #e0e0e0; }
        .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 8px; }
        .coach-card { background-color: #1c2128; border-left: 5px solid #00a2ff; padding: 20px; margin-bottom: 15px; }
        .critical-card { background-color: #2d1b1e; border-left: 5px solid #ff4b4b; padding: 20px; margin-bottom: 15px; }
        .setup-card { background-color: #1c2128; border-left: 5px solid #ff8c00; padding: 20px; margin-bottom: 15px; }
        </style>
    """, unsafe_allow_html=True)

# --- ENGINE: DATA PROCESSING & UNIT NORMALIZATION ---

def process_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    
    # 1. Map Acceleration Columns (Handle 'LongAccel' vs 'LonAccel')
    mapping = {'LatAccel': 'LatG', 'LongAccel': 'LonG', 'LonAccel': 'LonG'}
    for src, dest in mapping.items():
        if src in df.columns:
            df[dest] = pd.to_numeric(df[src], errors='coerce').fillna(0) / 9.81
    
    # Ensure both exist for GSum
    if 'LatG' not in df.columns: df['LatG'] = 0.0
    if 'LonG' not in df.columns: df['LonG'] = 0.0
    df['GSum'] = np.sqrt(df['LatG']**2 + df['LonG']**2)

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
            
    return df.sort_values(by='LapDistPct').drop_duplicates(subset=['LapDistPct'])

def align_and_resample(df_d, df_b, points=5000):
    grid = np.linspace(0, 1, points)
    
    def interp_channel(df):
        out = pd.DataFrame({'LapDistPct': grid})
        channels = ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'LatG', 'LonG', 'ABSActive', 'GSum', 'Lat', 'Lon']
        for col in channels:
            if col in df.columns:
                out[col] = np.interp(grid, df['LapDistPct'], df[col])
            else:
                out[col] = 0.0
        return out

    res_d = interp_channel(df_d)
    res_b = interp_channel(df_b)
    
    # Smoothing (Ghost Coach Fix)
    res_d['SteeringSmooth'] = res_d['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    res_b['SteeringSmooth'] = res_b['SteeringWheelAngle'].rolling(window=20, center=True).mean().ffill().bfill()
    
    return res_d, res_b, grid

def calculate_physics(res_d, res_b, grid):
    v_d = np.maximum(res_d['Speed'].values / 3.6, 1.0)
    v_b = np.maximum(res_b['Speed'].values / 3.6, 1.0)
    ds = np.diff(grid, prepend=0) * 4000 # Proxy track length
    delta = np.cumsum(ds / v_d - ds / v_b)
    delta = delta - delta[0] # Alignment Reset
    return pd.Series(delta).rolling(window=20, center=True).mean().ffill().bfill().values

# --- ENGINE: EVENT DETECTION ---

def detect_events(res_d, threshold=15):
    is_event = np.abs(res_d['SteeringSmooth']) > threshold
    event_ids = (is_event != pd.Series(is_event).shift()).cumsum()
    events = []
    for eid in event_ids.unique():
        idx = event_ids == eid
        if is_event[idx].iloc[0] and len(res_d[idx]) > 25: # 0.5s duration gate
            events.append(res_d.index[idx])
    if not events and threshold > 10: return detect_events(res_d, 10)
    return events

# --- MODULES: COACH & SETUP ---

def render_driver_coach(res_d, res_b, grid, delta):
    st.header("🧠 Physics-Based Driver Coach")
    events = detect_events(res_d)
    
    event_diagnostics = []
    for ev_idx in events:
        loss = delta[ev_idx[-1]] - delta[ev_idx[0]]
        d_ev, b_ev, g_ev = res_d.loc[ev_idx], res_b.loc[ev_idx], grid[ev_idx]
        
        flags = []
        # 1. Entry: Brake Release Derivative
        d_br = np.gradient(d_ev['Brake'], g_ev).min()
        b_br = np.gradient(b_ev['Brake'], g_ev).min()
        if d_br < b_br * 1.2:
            flags.append("Rapid Pitch Recovery: Releasing brake too fast; nose lifting, losing front grip.")
            
        # 2. Mid: V-Min Displacement
        if np.argmin(d_ev['Speed'].values) < np.argmin(b_ev['Speed'].values) - 20:
            flags.append("Early Over-slowing: Reaching V-Min too early. Carry more entry speed.")
            
        # 3. Exit: Traction Circle Conflict
        if np.any((np.gradient(d_ev['Throttle']) > 2) & (np.gradient(np.abs(d_ev['SteeringSmooth'])) >= 0)):
            flags.append("Understeer Inducement: Asking for power before unwinding the wheel.")
            
        # 4. G-Sum Transition
        peak_b = d_ev['Brake'].idxmax()
        peak_l = d_ev['LatG'].abs().idxmax()
        if peak_l > peak_b:
            trans_g = d_ev.loc[peak_b:peak_l, 'GSum'].mean()
            bench_g = b_ev.loc[peak_b:peak_l, 'GSum'].mean()
            if trans_g < bench_g * 0.85:
                flags.append("Inefficient Transition: Not blending braking and turning effectively.")

        # 5. Porsche 992 ABS
        if np.any((d_ev['ABSActive'] > 0.5) & (np.abs(d_ev['SteeringSmooth']) > 15)):
            flags.append("CRITICAL: ABS-Induced Understeer. Turning while on ABS is locking the platform.")

        event_diagnostics.append({"start": grid[ev_idx[0]]*100, "loss": loss, "flags": flags})

    top_3 = sorted(event_diagnostics, key=lambda x: x['loss'], reverse=True)[:3]
    for i, ev in enumerate(top_3, 1):
        with st.container():
            st.subheader(f"Event {i} at {ev['start']:.1f}% | Loss: {ev['loss']:.3f}s")
            for f in ev['flags']:
                style = "critical-card" if "CRITICAL" in f else "coach-card"
                st.markdown(f'<div class="{style}">{f}</div>', unsafe_allow_html=True)

def render_setup_tweaker(res_d, driver_issue):
    st.header("🔧 Setup Tweaker")
    mask = (res_d['Speed'] > 60) & (res_d['Brake'] < 5)
    sig_data = res_d[mask]
    
    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sig_data['LatG'].abs(), y=sig_data['SteeringSmooth'].abs(), mode='markers', marker=dict(color=sig_data['Speed'], size=4, colorscale='Viridis')))
        fig.update_layout(template="plotly_dark", title="Balance Signature (Filtered)", xaxis=dict(title="Lateral G", range=[0, 2.2]), yaxis=dict(title="Steering Angle", range=[0, 120]))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        if driver_issue == "Understeer":
            high_g = sig_data[sig_data['LatG'].abs() > 1.2]
            if not high_g.empty and (high_g['SteeringSmooth'].max() - high_g['SteeringSmooth'].min() > 30):
                st.error("VALIDATED: Mechanical Understeer. LatG plateaued while Steering increased.")
                st.markdown("- **Action:** Soften Front ARB or Increase Front Wing.")
            else:
                st.warning("OVERRIDE: Balance is linear. You are scrubbing the tires by over-turning.")
                st.markdown("- **Action:** Reduce steering input; wait for the nose to hook.")

# --- MAIN ---

def main():
    apply_custom_css()
    st.title("🏎️ Race Engineer Pro | Physics Suite")
    
    with st.sidebar:
        f_d = st.file_uploader("Driver Telemetry", type=['csv'])
        f_b = st.file_uploader("Benchmark Telemetry", type=['csv'])
        f_s = st.file_uploader("Session Summary", type=['csv'])
        issue = st.selectbox("Reported Issue", ["None", "Understeer", "Oversteer"])

    if f_d and f_b:
        df_d = process_telemetry(pd.read_csv(f_d))
        df_b = process_telemetry(pd.read_csv(f_b))
        res_d, res_b, grid = align_and_resample(df_d, df_b)
        delta = calculate_physics(res_d, res_b, grid)

        t1, t2, t3, t4 = st.tabs(["📊 Analyze Laps", "⏱️ Session Analyzer", "🧠 Driver Coach", "🔧 Setup Tweaker"])
        
        with t1:
            fig = make_subplots(rows=8, cols=1, shared_xaxes=True, vertical_spacing=0.01, subplot_titles=("Speed", "Throttle", "Brake", "Gear", "RPM", "Steering", "Line Distance", "Time Delta"))
            x = grid * 100
            for i, col in enumerate(['Speed', 'Throttle', 'Brake', 'Gear', 'RPM', 'SteeringSmooth'], 1):
                fig.add_trace(go.Scatter(x=x, y=res_b[col], line=dict(color='#ff3344', width=1)), row=i, col=1)
                fig.add_trace(go.Scatter(x=x, y=res_d[col], line=dict(color='#00a2ff', width=1.5)), row=i, col=1)
            fig.add_trace(go.Scatter(x=x, y=delta, line=dict(color='#00a2ff', width=2)), row=8, col=1)
            fig.update_layout(height=1400, template="plotly_dark", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with t2:
            if f_s:
                df_s = pd.read_csv(f_s)
                st.plotly_chart(px.line(df_s, x='Lap', y='Fuel level', template="plotly_dark", title="Fuel Stint Analysis"), use_container_width=True)
            else: st.info("Upload Session Summary for stint analysis.")
            
        with t3: render_driver_coach(res_d, res_b, grid, delta)
        with t4: render_setup_tweaker(res_d, issue)

if __name__ == "__main__":
    main()
