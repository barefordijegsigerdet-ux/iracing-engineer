import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

# --- KONFIGURATION ---
USER = "barefordijegsigerdet-ux"
REPO = "iracing-engineer"
BRANCH = "main"

st.set_page_config(page_title="iRacing Engineer", layout="wide")

@st.cache_data
def get_file_list():
    """Henter listen over alle filer i dit GitHub repo."""
    api_url = f"https://api.github.com/repos/{USER}/{REPO}/contents/"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            return [file['name'] for file in response.json()]
    except:
        return []
    return []

@st.cache_data
def load_data_by_keyword(keyword):
    """Finder en fil baseret på et søgeord og indlæser den."""
    files = get_file_list()
    target_file = next((f for f in files if keyword.lower() in f.lower() and f.endswith('.csv')), None)
    
    if target_file:
        raw_url = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{target_file}".replace(" ", "%20")
        try:
            return pd.read_csv(raw_url)
        except:
            return None
    return None

def analyze_data(df_ref, df_user):
    common_dist = np.linspace(0, 1, 3000)
    ref_speed = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Speed'])
    user_speed = np.interp(common_dist, df_user['LapDistPct'], df_user['Speed'])
    
    track_len = 4252
    dist_step = (1/3000) * track_len
    ref_ms = np.maximum(ref_speed / 3.6, 0.5)
    user_ms = np.maximum(user_speed / 3.6, 0.5)
    
    delta_steps = (dist_step / user_ms) - (dist_step / ref_ms)
    delta_time = np.cumsum(delta_steps)

    return {
        'dist': common_dist * 100,
        'ref_speed': ref_speed,
        'user_speed': user_speed,
        'delta': delta_time,
        'user_throttle': np.interp(common_dist, df_user['LapDistPct'], df_user['Throttle']),
        'user_brake': np.interp(common_dist, df_user['LapDistPct'], df_user['Brake'])
    }

# --- UI ---
st.title("🏎️ iRacing Engineer: Jonas vs. Leeroy")

# Automatisk søgning efter de rigtige filer
df_ref = load_data_by_keyword("Leeroy")
df_user = load_data_by_keyword("Jonas")
df_sess = load_data_by_keyword("Offline Testing")

if df_ref is not None and df_user is not None:
    data = analyze_data(df_ref, df_user)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Delta", f"+{data['delta'][-1]:.3f}s", delta_color="inverse")
    with c2:
        temp = "N/A"
        if df_sess is not None and "Track temp" in df_sess.columns:
            temp = f"{df_sess['Track temp'].iloc[-1]:.1f}°C"
        st.metric("Bane Temperatur", temp)
    with c3:
        st.metric("Max Fart", f"{data['user_speed'].max():.1f} km/t")

    # Grafer
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04, 
                       row_heights=[0.5, 0.2, 0.3],
                       subplot_titles=("Hastighed", "Delta", "Inputs"))

    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan')), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red')), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='green')), row=3, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Kunne ikke finde filerne i dit GitHub repo.")
    st.info("Sørg for at filerne på GitHub indeholder navnene 'Jonas', 'Leeroy' og 'Offline Testing'.")
