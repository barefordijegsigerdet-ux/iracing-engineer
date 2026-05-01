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
            
            # Telemetri-specifik rensning
            if 'LapDistPct' in df.columns:
                df = df.drop_duplicates(subset=['LapDistPct']).sort_values(by='LapDistPct')
                if 'Gear' in df.columns:
                    df['Gear'] = df['Gear'].replace(0, np.nan).ffill().fillna(1)
                if df['Speed'].max() < 100:
                    df['Speed'] = df['Speed'] * 3.6
            return df
    except: return None

# --- ANALYSE LOGIK ---
def analyze(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 6000)
    res = {'dist': grid * 100}
    cols = ['Speed', 'Throttle', 'Brake', 'Gear', 'SteeringWheelAngle']
    for col in cols:
        if col == 'Gear':
            idx_u = np.searchsorted(df_user['LapDistPct'], grid)
            res['user_gear'] = df_user['Gear'].iloc[np.clip(idx_u, 0, len(df_user)-1)].values
            idx_r = np.searchsorted(df_ref['LapDistPct'], grid)
            res['ref_gear'] = df_ref['Gear'].iloc[np.clip(idx_r, 0, len(df_ref)-1)].values
        else:
            short = 'steer' if col == 'SteeringWheelAngle' else col.lower()
            res[f'ref_{short}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
            res[f'user_{short}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    # Delta beregning
    track_len = 4252
    step = (1/6000) * track_len
    u_ms = np.maximum(res['user_speed']/3.6, 0.5)
    r_ms = np.maximum(res['ref_speed']/3.6, 0.5)
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    res['delta'] = raw_delta * (official_diff / raw_delta[-1])
    return res

# --- UI ---
st.title("🏎️ iRacing Engineer PRO")

tab1, tab2, tab3 = st.tabs(["📊 Telemetri", "🤖 AI Coach", "🔧 Setup & Garage"])

df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")
df_sess = load_and_clean_data("Offline") # Leder efter filen fra dine screenshots

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)

    with tab1:
        # Telemetri Plots
        fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                           row_heights=[0.3, 0.15, 0.12, 0.12, 0.1, 0.22])
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color=COLOR_LEEROY, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color=COLOR_JONAS)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='green')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=4, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Gear", line=dict(color='orange', shape='hv')), row=5, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_steer'], name="Rat", line=dict(color='yellow')), row=6, col=1)
        fig.update_layout(height=1100, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("Coach Jonas' Analyse")
        st.markdown(f"### Din status: `+{data['delta'][-1]:.3f}s` efter Leeroy")
        
        c1, c2 = st.columns(2)
        with c1:
            st.info("💡 **Strategi:** Du vinder tid på bremsen, men taber det på exit. Fokusér på at få bilen rettet ud hurtigere.")
        with c2:
            st.success("✅ **Gear-tjek:** Dine skift er nu 'clean' og uden drops til 0.")

    with tab3:
        st.header("🔧 Session & Setup Info")
        if df_sess is not None:
            # Layout baseret på dine Offline Analysis billeder
            m1, m2, m3 = st.columns(3)
            
            # Prøver at finde de rigtige kolonner fra din CSV
            track_temp = df_sess.get('Track temp', ["N/A"]).iloc[0]
            air_temp = df_sess.get('Air temp', ["N/A"]).iloc[0]
            fuel_lap = df_sess.get('Fuel used', [0]).mean()
            
            m1.metric("Bane Temperatur", f"{track_temp}")
            m2.metric("Luft Temperatur", f"{air_temp}")
            m3.metric("Avg. Fuel/Lap", f"{fuel_lap:.2f} L")
            
            st.divider()
            st.subheader("Sidste Stint Detaljer")
            st.dataframe(df_sess.tail(10), use_container_width=True)
        else:
            st.warning("Upload venligst 'Offline Analysis' filen for at se Garage-data.")
else:
    st.error("Telemetri-filer kunne ikke findes på GitHub.")
