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
            response = requests.get(url)
            
            # Hvis det er 'Offline Testing' (Session Log), skal vi håndtere headeren
            if "testing" in keyword.lower() or "export" in keyword.lower():
                df = pd.read_csv(io.StringIO(response.text))
                return df
            
            # For telemetri (Jonas/Leeroy)
            df = pd.read_csv(io.StringIO(response.text))
            df = df.drop_duplicates(subset=['LapDistPct']).sort_values(by='LapDistPct')
            return df
    except: return None
    return None

def analyze(df_ref, df_user):
    grid = np.linspace(0, 1, 5000)
    res = {'dist': grid * 100}
    for col in ['Speed', 'Throttle', 'Brake', 'Gear']:
        if col in df_ref.columns and col in df_user.columns:
            res[f'ref_{col.lower()}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
            res[f'user_{col.lower()}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    # Delta (Zandvoort 4252m)
    track_len = 4252
    step = (1/5000) * track_len
    u_ms = np.maximum(res['user_speed']/3.6, 0.5)
    r_ms = np.maximum(res['ref_speed']/3.6, 0.5)
    res['delta'] = np.cumsum((step/u_ms) - (step/r_ms))
    return res

# --- UI ---
st.title("🏎️ iRacing Telemetry: Jonas vs. Leeroy")

# Vi bruger keywords der passer på dine filer
df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")
df_sess = load_and_clean_data("Offline")

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)
    
    # Metrics - Vi tjekker specifikt efter de rigtige kolonnenavne fra dit billede
    c1, c2, c3 = st.columns(3)
    c1.metric("Delta til Leeroy", f"+{data['delta'][-1]:.3f}s", delta_color="inverse")
    
    if df_sess is not None:
        # Henter track temp fra den første gyldige række
        temp = df_sess['Track temp'].iloc[0] if 'Track temp' in df_sess.columns else "N/A"
        c2.metric("Bane Temp", f"{temp:.1f}°C" if isinstance(temp, float) else temp)
        
        # Finder den hurtigste omgang i sessionen (Lap time kolonnen)
        if 'Lap time' in df_sess.columns:
            best_lap = df_sess['Lap time'].min()
            c3.metric("Session Best", f"{best_lap:.3f}s")

    # Grafer (Hastighed, Delta, Pedaler)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                       row_heights=[0.5, 0.2, 0.3])

    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='#2ecc71')), row=3, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(231, 76, 60, 0.5)')), row=3, col=1)
    
    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified", showlegend=True)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Kunne ikke matche Jonas/Leeroy telemetri-filer. Tjek GitHub.")
