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

st.set_page_config(page_title="iRacing Telemetry: 247 km/t Calibration", layout="wide")

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
                # Gear fix (ffill for at undgå 0-værdier under skift)
                if 'Gear' in df.columns:
                    df['Gear'] = df['Gear'].replace(0, np.nan).ffill().fillna(1)
                
                # SIKRING AF ENHED: Hvis Speed er i m/s (typisk omkring 60-70), konverterer vi til km/t
                if df['Speed'].max() < 100:
                    df['Speed'] = df['Speed'] * 3.6
            return df
    except: return None

def analyze(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 6000) # Højere opløsning til høj fart
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
    
    # Delta (baseret på km/t -> m/s konvertering for præcis tid)
    track_len = 4252
    step = (1/6000) * track_len
    u_ms = np.maximum(res['user_speed']/3.6, 0.5)
    r_ms = np.maximum(res['ref_speed']/3.6, 0.5)
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    res['delta'] = raw_delta * (official_diff / raw_delta[-1])
    return res

# --- UI ---
st.title("🏎️ High Speed Telemetry: 247 km/t Target")

df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)
    
    # Grafer i fuld højde
    fig = make_subplots(
        rows=6, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.02,
        row_heights=[0.3, 0.12, 0.12, 0.12, 0.1, 0.22],
        subplot_titles=("Hastighed (km/t)", "Tid Delta (s)", "Gas (%)", "Brems (%)", "Gear", "Ratvinkel")
    )

    # 1. HASTIGHED (Nu kalibreret til 247+ km/t)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy (247kph target)", line=dict(color=COLOR_LEEROY, width=1, dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color=COLOR_JONAS, width=2)), row=1, col=1)

    # 2. DELTA
    fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white', width=1)), row=2, col=1)

    # 3. THROTTLE
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, line=dict(color=COLOR_LEEROY, width=1, dash='dot'), showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='green', width=2)), row=3, col=1)

    # 4. BRAKE
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_brake']*100, line=dict(color=COLOR_LEEROY, width=1, dash='dot'), showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(255, 0, 0, 0.3)', width=2)), row=4, col=1)

    # 5. GEAR
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_gear'], name="Leeroy Gear", line=dict(color=COLOR_LEEROY, width=1, dash='dot', shape='hv')), row=5, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Jonas Gear", line=dict(color='orange', shape='hv')), row=5, col=1)

    # 6. STEERING
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_steer'], line=dict(color=COLOR_LEEROY, width=1, dash='dot'), showlegend=False), row=6, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_steer'], name="Rat", line=dict(color='yellow', width=2)), row=6, col=1)

    fig.update_layout(height=1200, template="plotly_dark", hovermode="x unified", showlegend=True)
    fig.update_yaxes(range=[0, 260], row=1, col=1) # Sætter loftet til 260 km/t
    fig.update_yaxes(range=[-5, 105], row=3, col=1)
    fig.update_yaxes(range=[-5, 105], row=4, col=1)
    fig.update_yaxes(dtick=1, row=5, col=1)
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Henter og kalibrerer data...")
