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

# --- SIDEBAR: UNIVERSAL SETTINGS ---
st.sidebar.header("⚙️ Session Settings")
track_len = st.sidebar.number_input("Banelængde (m)", value=4252)
time_ref = st.sidebar.number_input("Ref Tid (s)", value=94.500, format="%.3f")
time_user = st.sidebar.number_input("Din Tid (s)", value=95.148, format="%.3f")
official_diff = time_user - time_ref

st.sidebar.divider()
st.sidebar.subheader("📍 Zoom & Fokus")
# Denne slider styrer synkroniseringen mellem kort og grafer
view_range = st.sidebar.slider("Vælg sektion af banen (%)", 0.0, 100.0, (0.0, 100.0))

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
                if df['Speed'].max() < 120:
                    df['Speed'] = df['Speed'] * 3.6
            return df
    except: return None

def analyze(df_ref, df_user, track_len, official_diff):
    grid = np.linspace(0, 1, 6000)
    res = {'dist': grid * 100}
    cols = ['Speed', 'Throttle', 'Brake', 'Gear', 'SteeringWheelAngle', 'TrackX', 'TrackY']
    
    for col in cols:
        if col in df_user.columns:
            short = 'steer' if col == 'SteeringWheelAngle' else col.lower()
            res[f'ref_{short}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col]) if col in df_ref.columns else np.zeros(6000)
            res[f'user_{short}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    u_ms, r_ms = np.maximum(res['user_speed']/3.6, 0.5), np.maximum(res['ref_speed']/3.6, 0.5)
    step = (1/6000) * track_len
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    res['delta'] = raw_delta * (official_diff / (raw_delta[-1] if abs(raw_delta[-1]) > 0.01 else 1))
    return pd.DataFrame(res)

# --- DATA LOAD ---
df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")
df_sess = load_and_clean_data("Offline")

if df_ref is not None and df_user is not None:
    full_data = analyze(df_ref, df_user, track_len, official_diff)
    
    # FILTRERING BASERET PÅ SLIDER
    mask = (full_data['dist'] >= view_range[0]) & (full_data['dist'] <= view_range[1])
    data = full_data[mask]

    tab1, tab2, tab3 = st.tabs(["📊 Telemetri & Trackmap", "🤖 AI Coach", "🔧 Setup"])

    with tab1:
        col_map, col_tele = st.columns([1, 2])

        with col_map:
            st.subheader("Trackmap")
            fig_map = go.Figure()
            # Hele banen som grå linje
            fig_map.add_trace(go.Scatter(x=full_data['user_trackx'], y=full_data['user_tracky'], 
                                        line=dict(color='rgba(100,100,100,0.2)', width=2), showlegend=False))
            # Highlightet sektion
            fig_map.add_trace(go.Scatter(x=data['user_trackx'], y=data['user_tracky'], 
                                        line=dict(color=COLOR_JONAS, width=5), name="Valgt Sektion"))
            fig_map.update_layout(height=400, template="plotly_dark", 
                                 xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1))
            st.plotly_chart(fig_map, use_container_width=True)
            st.caption("💡 Brug slideren i venstre side til at vælge sving.")

        with col_tele:
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                               subplot_titles=("Speed", "Delta", "Pedals", "Gear"))
            
            fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Ref", line=dict(color=COLOR_LEEROY, dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Du", line=dict(color=COLOR_JONAS)), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
            fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='green')), row=3, col=1)
            fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=3, col=1)
            fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Gear", line=dict(color='orange')), row=4, col=1)

            fig.update_layout(height=700, template="plotly_dark", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # Samme AI Coach logik, men nu baseret på det zoomede område!
        st.header("🤖 AI Coach: Sektions-analyse")
        max_speed = data['user_speed'].max()
        min_speed = data['user_speed'].min()
        st.write(f"I denne sektion er din topfart **{max_speed:.1f} km/t** og din laveste fart **{min_speed:.1f} km/t**.")
        # ... resten af coach logik

    with tab3:
        # Setup logik fra før
        st.header("🔧 Setup Justering")
        # ... setup logik
