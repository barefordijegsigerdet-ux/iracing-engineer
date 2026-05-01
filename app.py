import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- PRÆCISE FILNAVNE FRA DIT REPO ---
USER = "barefordijegsigerdet-ux"
REPO = "iracing-engineer"
BRANCH = "main"

# GitHub Raw base URL
BASE_URL = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/"

# Præcise navne (Python håndterer selv mellemrummene herfra)
FILE_JONAS = "Garage 61 - Jonas Hauerbach - Porsche 911 Cup (992.2) - Circuit Zandvoort (Grand Prix) - 01.41.980 - 01KQAKNQHNGGR7RTTC9DMD0F59.csv"
FILE_LEEROY = "Garage 61 - Leeroy Malmross - Porsche 911 Cup (992.2) - Circuit Zandvoort (Grand Prix) - 01.41.332 - 01KQ5E93PS1W2T3SH5ECRJNCF6.csv"
FILE_SESSION = "Garage 61 - Offline Testing - Export - 2026-04-29-07-31-44.csv"

st.set_page_config(page_title="iRacing Engineer: Jonas vs Leeroy", layout="wide")

@st.cache_data
def load_data(filename):
    url = BASE_URL + filename.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
    try:
        return pd.read_csv(url)
    except Exception as e:
        return None

def analyze_data(df_ref, df_user):
    common_dist = np.linspace(0, 1, 3000)
    
    # Interpolering
    ref_speed = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Speed'])
    user_speed = np.interp(common_dist, df_user['LapDistPct'], df_user['Speed'])
    
    # Delta beregning (Zandvoort ca. 4252m)
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
        'user_brake': np.interp(common_dist, df_user['LapDistPct'], df_user['Brake']),
        'ref_throttle': np.interp(common_dist, df_ref['LapDistPct'], df_ref['Throttle'])
    }

# --- UI VISNING ---
st.title("🏎️ iRacing Engineer: Jonas vs. Leeroy")
st.caption("Data hentes automatisk fra din GitHub main folder")

# Forsøg at hente data
df_ref = load_data(FILE_LEEROY)
df_user = load_data(FILE_JONAS)
df_sess = load_data(FILE_SESSION)

if df_ref is not None and df_user is not None:
    data = analyze_data(df_ref, df_user)
    
    # Dashboard
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Delta", f"+{data['delta'][-1]:.3f}s", delta_color="inverse")
    with c2:
        track_temp = df_sess["Track temp"].iloc[-1] if df_sess is not None else "N/A"
        st.metric("Bane Temperatur", f"{track_temp:.1f}°C" if isinstance(track_temp, (float, int)) else track_temp)
    with c3:
        st.metric("Max Fart (Jonas)", f"{data['user_speed'].max():.1f} km/t")

    # Grafer
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                       row_heights=[0.5, 0.2, 0.3],
                       subplot_titles=("Hastighed", "Delta", "Inputs (Gas/Brems)"))

    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan')), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red')), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='green')), row=3, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    st.success("Analyse klar! Zoom ind på graferne for at se detaljer.")
else:
    st.error("Kunne ikke finde filerne på GitHub.")
    st.write("Tjek at filnavnene i dit repo matcher præcis dem i koden.")
