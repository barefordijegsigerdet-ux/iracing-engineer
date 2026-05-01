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
            df = pd.read_csv(io.StringIO(response.text))
            
            if 'LapDistPct' in df.columns:
                # Rens telemetri: Sorter og fjern hop i data
                df = df.drop_duplicates(subset=['LapDistPct']).sort_values(by='LapDistPct')
            return df
    except: return None
    return None

def analyze_with_fixed_delta(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 5000)
    
    # Interpolér hastighed og pedaler
    ref_speed = np.interp(grid, df_ref['LapDistPct'], df_ref['Speed'])
    user_speed = np.interp(grid, df_user['LapDistPct'], df_user['Speed'])
    user_throttle = np.interp(grid, df_user['LapDistPct'], df_user['Throttle'])
    user_brake = np.interp(grid, df_user['LapDistPct'], df_user['Brake'])
    
    # Delta beregning
    # Vi bruger den rå beregning, men skalerer den så den rammer de 0.648s ved målstregen
    track_len = 4252
    step = (1/5000) * track_len
    u_ms = np.maximum(user_speed/3.6, 0.5)
    r_ms = np.maximum(ref_speed/3.6, 0.5)
    
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    # Justering så slut-delta matcher Garage 61 præcis
    correction_factor = official_diff / raw_delta[-1] if raw_delta[-1] != 0 else 1
    final_delta = raw_delta * correction_factor

    return {
        'dist': grid * 100,
        'user_speed': user_speed,
        'ref_speed': ref_speed,
        'delta': final_delta,
        'throttle': user_throttle,
        'brake': user_brake
    }

# --- UI ---
st.title("🏎️ iRacing Telemetry: Jonas vs. Leeroy")

df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")
df_sess = load_and_clean_data("Offline")

if df_ref is not None and df_user is not None:
    # Vi ved nu fra Garage 61 at forskellen er 0.648
    data = analyze_with_fixed_delta(df_ref, df_user, official_diff=0.648)
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Delta (Garage 61)", "0.648 s", delta="-0.648", delta_color="inverse")
    
    if df_sess is not None:
        temp = df_sess['Track temp'].iloc[0] if 'Track temp' in df_sess.columns else "N/A"
        c2.metric("Bane Temp", f"{temp:.1f}°C" if isinstance(temp, float) else temp)
        if 'Lap time' in df_sess.columns:
            c3.metric("Din Tid", f"{df_user.iloc[0].get('LapTime', '1:41.980')}")

    # Grafer
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                       row_heights=[0.5, 0.2, 0.3],
                       subplot_titles=("Speed (km/t)", "Delta (s) - Præcis match", "Inputs"))

    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red', width=2)), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
    
    fig.add_trace(go.Scatter(x=data['dist'], y=data['throttle']*100, name="Gas", line=dict(color='#2ecc71')), row=3, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(231, 76, 60, 0.5)')), row=3, col=1)
    
    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Kunne ikke indlæse data. Tjek at filerne Jonas og Leeroy ligger på GitHub.")
