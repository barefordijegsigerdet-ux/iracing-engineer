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

st.set_page_config(page_title="iRacing Engineer PRO", layout="wide")

@st.cache_data
def load_and_clean_data(keyword):
    """Finder, renser og sorterer telemetri-data."""
    api_url = f"https://api.github.com/repos/{USER}/{REPO}/contents/"
    try:
        r = requests.get(api_url)
        files = [f['name'] for f in r.json()]
        target = next((f for f in files if keyword.lower() in f.lower() and f.endswith('.csv')), None)
        
        if target:
            url = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{target}".replace(" ", "%20")
            df = pd.read_csv(url)
            
            # --- VIGTIG RENSNING ---
            # 1. Fjern dubletter i baneposition
            df = df.drop_duplicates(subset=['LapDistPct'])
            # 2. Sorter efter baneposition (så grafen ikke hopper tilbage)
            df = df.sort_values(by='LapDistPct')
            # 3. Fjern rækker med fejl i farten
            df = df[df['Speed'] > 0]
            
            return df
    except: return None
    return None

def analyze(df_ref, df_user):
    # Lav et ultra-rent grid med 5000 punkter
    grid = np.linspace(0, 1, 5000)
    
    # Interpolér alle kanaler så de passer sammen
    res = {'dist': grid * 100}
    for col in ['Speed', 'Throttle', 'Brake', 'Gear']:
        res[f'ref_{col.lower()}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
        res[f'user_{col.lower()}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    # Præcis Delta (Zandvoort 4252m)
    track_len = 4252
    step = (1/5000) * track_len
    u_ms = np.maximum(res['user_speed']/3.6, 0.5)
    r_ms = np.maximum(res['ref_speed']/3.6, 0.5)
    res['delta'] = np.cumsum((step/u_ms) - (step/r_ms))
    
    return res

# --- UI ---
st.title("🏎️ iRacing Telemetry: Jonas vs. Leeroy")

df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")
df_sess = load_and_clean_data("Offline Testing")

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Delta til Leeroy", f"+{data['delta'][-1]:.3f}s", delta_color="inverse")
    if df_sess is not None and 'Sector 1' in df_sess.columns:
        opt = df_sess['Sector 1'].min() + df_sess['Sector 2'].min() + df_sess['Sector 3'].min()
        c2.metric("Din Optimal Lap", f"{opt:.3f}s")
    c3.metric("Bane Temp", f"{df_sess['Track temp'].iloc[-1] if df_sess is not None else 'N/A'}°C")

    # Grafer
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                       row_heights=[0.5, 0.2, 0.3],
                       subplot_titles=("Hastighed (km/t)", "Tid Tabt/Vundet (s)", "Pedaler & Gear"))

    # Hastighed
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red', width=2)), row=1, col=1)
    
    # Delta
    fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
    
    # Pedaler
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='#2ecc71')), row=3, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(231, 76, 60, 0.5)')), row=3, col=1)
    
    # Gear (skaleret så det passer i bunden af pedal-grafen)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear']*10, name="Gear (x10)", line=dict(color='white', dash='dot')), row=3, col=1)

    fig.update_layout(height=800, template="plotly_dark", hovermode="x unified", showlegend=False)
    fig.update_yaxes(range=[0, 105], row=3, col=1)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Finder filer på GitHub... Sørg for at 'Jonas' og 'Leeroy' csv-filerne er uploadet.")
