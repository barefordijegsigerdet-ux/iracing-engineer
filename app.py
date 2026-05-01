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
                
                # --- GEAR FIX: Fjern 0-taller under skift ---
                # Vi erstatter 0 med 'NaN' og bruger ffill (forward fill) til at lukke hullerne
                if 'Gear' in df.columns:
                    df['Gear'] = df['Gear'].replace(0, np.nan).ffill().fillna(1)
            return df
    except: return None

def analyze(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 5000)
    res = {'dist': grid * 100}
    cols = ['Speed', 'Throttle', 'Brake', 'Gear', 'SteeringWheelAngle']
    
    for col in cols:
        if col == 'Gear':
            # Bruger 'nearest' for at holde de digitale trin rene
            idx_u = np.searchsorted(df_user['LapDistPct'], grid)
            res['user_gear'] = df_user['Gear'].iloc[np.clip(idx_u, 0, len(df_user)-1)].values
            idx_r = np.searchsorted(df_ref['LapDistPct'], grid)
            res['ref_gear'] = df_ref['Gear'].iloc[np.clip(idx_r, 0, len(df_ref)-1)].values
        else:
            short = 'steer' if col == 'SteeringWheelAngle' else col.lower()
            res[f'ref_{short}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
            res[f'user_{short}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    # Delta fixet til de 0.648s
    track_len = 4252
    step = (1/5000) * track_len
    raw_delta = np.cumsum((step/np.maximum(res['user_speed']/3.6, 0.5)) - (step/np.maximum(res['ref_speed']/3.6, 0.5)))
    res['delta'] = raw_delta * (official_diff / raw_delta[-1])
    return res

# --- UI ---
st.title("🏎️ iRacing Telemetry: Gear Shift Fix")

df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)
    
    fig = make_subplots(
        rows=6, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03,
        row_heights=[0.3, 0.15, 0.1, 0.1, 0.15, 0.2],
        subplot_titles=("Hastighed", "Delta", "Gas", "Brems", "Gear (No Drops)", "Ratvinkel")
    )

    # Plotting
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
    
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='green')), row=3, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=4, col=1)

    # Gear med 'hv' form og fixet mod 0-drops
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_gear'], name="Leeroy Gear", line=dict(color='rgba(0,255,255,0.3)', dash='dot', shape='hv')), row=5, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Jonas Gear", line=dict(color='orange', shape='hv')), row=5, col=1)

    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_steer'], name="Rat", line=dict(color='yellow')), row=6, col=1)

    fig.update_layout(height=1100, template="plotly_dark", hovermode="x unified")
    fig.update_yaxes(range=[-5, 105], row=3, col=1)
    fig.update_yaxes(range=[-5, 105], row=4, col=1)
    fig.update_yaxes(range=[0.8, 6.2], dtick=1, row=5, col=1) # Låser y-aksen til gear 1-6
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Henter data fra GitHub...")
