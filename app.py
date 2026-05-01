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
            return df
    except: return None

def analyze(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 5000)
    res = {'dist': grid * 100}
    cols = ['Speed', 'Throttle', 'Brake', 'Gear', 'SteeringWheelAngle']
    for col in cols:
        res[f'ref_{col.lower()}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
        res[f'user_{col.lower()}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    # Delta fixet til de 0.648s
    track_len = 4252
    step = (1/5000) * track_len
    raw_delta = np.cumsum((step/np.maximum(res['user_speed']/3.6, 0.5)) - (step/np.maximum(res['ref_speed']/3.6, 0.5)))
    res['delta'] = raw_delta * (official_diff / raw_delta[-1])
    return res

# --- UI ---
st.title("🏎️ iRacing Telemetry: Garage 61 Layout")

df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)
    
    # Præcis 5-rækket subplot layout
    fig = make_subplots(
        rows=5, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.02,
        row_heights=[0.35, 0.15, 0.15, 0.15, 0.2], # Gør speed størst
        subplot_titles=("Speed (km/t)", "Time Delta (s)", "Throttle (%)", "Brake (%)", "Gear & Steering")
    )

    # 1. SPEED
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red', width=2)), row=1, col=1)

    # 2. DELTA
    fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)

    # 3. THROTTLE (Grøn)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, name="Ref Gas", line=dict(color='rgba(0,255,0,0.2)', dash='dot')), row=3, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Din Gas", line=dict(color='green')), row=3, col=1)

    # 4. BRAKE (Rød)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_brake']*100, name="Ref Brems", line=dict(color='rgba(255,0,0,0.2)', dash='dot')), row=4, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Din Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.4)')), row=4, col=1)

    # 5. GEAR & STEER (Secondary data)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Gear", line=dict(color='orange', shape='hv')), row=5, col=1)
    
    # Layout styling
    fig.update_layout(height=1000, template="plotly_dark", hovermode="x unified", showlegend=False)
    fig.update_yaxes(range=[-5, 105], row=3, col=1) # Lås Throttle
    fig.update_yaxes(range=[-5, 105], row=4, col=1) # Lås Brake
    
    st.plotly_chart(fig, use_container_width=True)
    st.success(f"Viser nu Delta: +0.648s (Fixed)")
else:
    st.error("Kunne ikke indlæse filer fra GitHub.")
