import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io

# --- KONFIGURATION ---
USER = "barefordijegsigerdet-ux"
REPO = "iracing-engineer"
BRANCH = "main"
COLOR_JONAS = 'red'
COLOR_LEEROY = 'cyan'

st.set_page_config(page_title="iRacing Engineer PRO", layout="wide")

@st.cache_data
def load_and_clean_data(keyword):
    api_url = f"https://api.github.com/repos/{USER}/{REPO}/contents/"
    try:
        r = requests.get(api_url)
        files = [f['name'] for f in r.json()]
        target = next((f for f in files if keyword.lower() in f.lower() and f.endswith('.csv')), None)
        if target:
            url = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{target}".replace(" ", "%20")
            df = pd.read_csv(io.StringIO(requests.get(url).text))
            if 'LapDistPct' in df.columns:
                df = df.drop_duplicates(subset=['LapDistPct']).sort_values(by='LapDistPct')
                if 'Gear' in df.columns:
                    df['Gear'] = df['Gear'].replace(0, np.nan).ffill().fillna(1)
                if df['Speed'].max() < 100:
                    df['Speed'] = df['Speed'] * 3.6
            return df
    except: return None

def analyze(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 6000)
    res = {'dist': grid * 100}
    cols = ['Speed', 'Throttle', 'Brake', 'Gear', 'SteeringWheelAngle']
    for col in cols:
        short = 'steer' if col == 'SteeringWheelAngle' else col.lower()
        res[f'ref_{short}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
        res[f'user_{short}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    track_len = 4252
    step = (1/6000) * track_len
    u_ms, r_ms = np.maximum(res['user_speed']/3.6, 0.5), np.maximum(res['ref_speed']/3.6, 0.5)
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    res['delta'] = raw_delta * (official_diff / raw_delta[-1])
    return res

# --- MAIN APP ---
df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")
df_sess = load_and_clean_data("Offline")

tab1, tab2, tab3 = st.tabs(["📊 Telemetri", "🤖 AI Coach", "🔧 Garage"])

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)

    with tab1:
        fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                           row_heights=[0.3, 0.15, 0.1, 0.1, 0.1, 0.25])
        
        # Speed & Delta
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color=COLOR_LEEROY, dash='dot', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color=COLOR_JONAS, width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        
        # Pedaler (Begge kørere nu!)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, name="L. Gas", line=dict(color='rgba(0,255,0,0.2)')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="J. Gas", line=dict(color='green')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="J. Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.4)')), row=4, col=1)
        
        # Gear & Rat
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_gear'], name="L. Gear", line=dict(color='cyan', dash='dot', shape='hv')), row=5, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="J. Gear", line=dict(color='orange', shape='hv')), row=5, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_steer'], name="Rat Jonas", line=dict(color='yellow')), row=6, col=1)

        fig.update_layout(height=1200, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("🤖 AI Coach: Jonas vs Leeroy")
        # Find hvor deltaen stiger mest (tidstab)
        loss_idx = np.argmax(np.gradient(data['delta']))
        loss_pct = data['dist'][loss_idx]
        
        c1, c2 = st.columns(2)
        c1.metric("Total Tidstab", f"+{data['delta'][-1]:.3f}s", delta="-0.648s", delta_color="inverse")
        c2.error(f"Kritisk Tidstab: {loss_pct:.1f}% af banen")
        
        st.markdown(f"""
        ### 📋 Handlingsplan
        * **Sving Analyse:** Du taber mest tid ved **{loss_pct:.1f}%**. Her bremser du enten for tidligt eller har et dårligt exit.
        * **Gear-forskel:** Leeroy bruger gear **{int(data['ref_gear'][loss_idx])}** her, mens du bruger **{int(data['user_gear'][loss_idx])}**.
        * **Ratvinkel:** Din maksimale ratvinkel er {np.max(np.abs(data['user_steer'])):.1f}°, Leeroy bruger {np.max(np.abs(data['ref_steer'])):.1f}°.
        """)

    with tab3:
        if df_sess is not None:
            st.header("🔧 Garage & Setup Status")
            # Trækker de faktiske værdier fra dine screenshots
            t_temp = df_sess['Track temp'].iloc[-1] if 'Track temp' in df_sess.columns else "N/A"
            fuel = df_sess['Fuel used'].iloc[-1] if 'Fuel used' in df_sess.columns else 0
            
            col1, col2 = st.columns(2)
            col1.metric("Bane Temperatur", f"{t_temp}°C")
            col2.metric("Fuel i tanken", f"{fuel:.2f} L")
            
            st.subheader("Omgangs-tider fra Session")
            st.dataframe(df_sess[['Lap', 'Lap time', 'Fuel used']].tail(5), use_container_width=True)
else:
    st.error("Data mangler. Tjek GitHub for Jonas.csv og Leeroy.csv")
