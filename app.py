import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io

# --- SETUP & TEMA ---
st.set_page_config(page_title="iRacing Engineer", layout="wide")
USER, REPO, BRANCH = "barefordijegsigerdet-ux", "iracing-engineer", "main"
C_JONAS, C_LEEROY = '#FF4B4B', '#00D4FF'

# --- DATA INDLÆSNING ---
@st.cache_data
def get_data(name):
    try:
        url = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{name}.csv".replace(" ", "%20")
        r = requests.get(url)
        if r.status_code != 200: return None
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip().lower() for c in df.columns]
        if 'lapdistpct' in df.columns:
            df = df.drop_duplicates('lapdistpct').sort_values('lapdistpct')
            if 'speed' in df.columns and df['speed'].max() < 120: df['speed'] *= 3.6
            if 'gear' in df.columns: df['gear'] = df['gear'].replace(0, np.nan).ffill().fillna(1)
        return df
    except: return None

# --- SIDEBAR (Kompakt) ---
with st.sidebar:
    st.header("⚙️ Setup")
    t_len = st.number_input("Bane (m)", value=4252)
    diff = st.number_input("Delta (s)", value=0.648, format="%.3f")
    st.divider()
    zoom = st.slider("Zoom %", 0.0, 100.0, (0.0, 100.0))

# --- LOGIK ---
df_ref = get_data("Leeroy")
df_user = get_data("Jonas")

if df_ref is not None and df_user is not None:
    # Interpolering
    grid = np.linspace(0, 1, 2000)
    data = pd.DataFrame({'dist': grid * 100})
    
    for k, col in [('speed','speed'), ('thr','throttle'), ('brk','brake'), ('gr','gear'), ('tx','trackx'), ('ty','tracky')]:
        if col in df_user.columns: data[f'u_{k}'] = np.interp(grid, df_user['lapdistpct'], df_user[col])
        if col in df_ref.columns: data[f'r_{k}'] = np.interp(grid, df_ref['lapdistpct'], df_ref[col])
    
    # Delta
    if 'u_speed' in data and 'r_speed' in data:
        u_ms, r_ms = np.maximum(data['u_speed']/3.6, 0.5), np.maximum(data['r_speed']/3.6, 0.5)
        raw = np.cumsum(((1/2000)*t_len)/u_ms - ((1/2000)*t_len)/r_ms)
        data['delta'] = raw * (diff / (raw.iloc[-1] if abs(raw.iloc[-1]) > 0.01 else 1))

    # Filtrering
    view = data[(data['dist'] >= zoom[0]) & (data['dist'] <= zoom[1])]

    # --- UI ---
    t1, t2 = st.tabs(["📊 Telemetri", "🤖 Coach"])

    with t1:
        # Mini-kort (kun hvis data findes)
        if 'u_tx' in view.columns:
            with st.expander("📍 Vis kort"):
                m_fig = go.Figure()
                m_fig.add_trace(go.Scatter(x=data.get('u_tx'), y=data.get('u_ty'), line=dict(color='gray', width=1)))
                m_fig.add_trace(go.Scatter(x=view['u_tx'], y=view['u_ty'], line=dict(color=C_JONAS, width=4)))
                m_fig.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
                st.plotly_chart(m_fig, use_container_width=True, config={'staticPlot': True})

        # Kompakt Telemetri
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.5, 0.25, 0.25])
        
        # Speed & Delta
        fig.add_trace(go.Scatter(x=view['dist'], y=view.get('r_speed'), name="Ref", line=dict(color=C_LEEROY, width=1, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=view['dist'], y=view.get('u_speed'), name="Du", line=dict(color=C_JONAS, width=2)), row=1, col=1)
        if 'delta' in view.columns:
            fig.add_trace(go.Scatter(x=view['dist'], y=view['delta'], name="Delta", fill='tozeroy', line=dict(color='white', width=1)), row=2, col=1)
        
        # Pedaler (Sammensmeltet for at spare plads)
        fig.add_trace(go.Scatter(x=view['dist'], y=view.get('u_thr', 0)*100, name="Gas", line=dict(color='green', width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=view['dist'], y=view.get('u_brk', 0)*100, name="Brems", fill='tozeroy', line=dict(color='red', width=0)), row=3, col=1)

        fig.update_layout(height=450, margin=dict(l=5,r=5,t=5,b=5), template="plotly_dark", showlegend=False)
        # VIGTIGT: staticPlot=False men scrollZoom=False gør at man kan scrolle siden med fingeren ovenpå grafen
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})

    with t2:
        if 'delta' in view.columns:
            loss = view['delta'].iloc[-1] - view['delta'].iloc[0]
            st.metric("Tid tabt her", f"{loss:.3f}s")
            st.write(f"Topfart: {view['u_speed'].max():.1f} km/t")

else:
    st.error("Fandt ikke Jonas.csv eller Leeroy.csv på GitHub.")
