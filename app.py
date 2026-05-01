import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io

# --- KONFIGURATION ---
st.set_page_config(page_title="iRacing Engineer PRO", layout="wide")
USER = "barefordijegsigerdet-ux"
REPO = "iracing-engineer"
BRANCH = "main"
C_JONAS, C_LEEROY = '#FF4B4B', '#00D4FF'

# --- 1. HENT FILER (Forbedret fejlhåndtering) ---
@st.cache_data(ttl=60) # Opdaterer listen hvert minut
def get_all_csv_files():
    try:
        api_url = f"https://api.github.com/repos/{USER}/{REPO}/contents/"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200:
            files = [f['name'] for f in r.json() if f['name'].lower().endswith('.csv')]
            return sorted(files)
        return []
    except:
        return []

# --- 2. INDLÆS DATA ---
def load_selected_data(filename):
    if not filename: return None
    try:
        url = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{filename}"
        r = requests.get(url)
        if r.status_code != 200: return None
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Find den rigtige distance-kolonne (nogle gange hedder den LapDist eller LapDistPct)
        dist_col = next((c for c in df.columns if 'dist' in c), None)
        if dist_col:
            df = df.rename(columns={dist_col: 'lapdistpct'})
            # Hvis distancen er i meter, konverter til procent (estimat)
            if df['lapdistpct'].max() > 1.1:
                df['lapdistpct'] = (df['lapdistpct'] - df['lapdistpct'].min()) / (df['lapdistpct'].max() - df['lapdistpct'].min())
            
            df = df.drop_duplicates('lapdistpct').sort_values('lapdistpct')
            if 'speed' in df.columns and df['speed'].max() < 120: df['speed'] *= 3.6
            if 'gear' in df.columns: df['gear'] = df['gear'].replace(0, np.nan).ffill().fillna(1)
            return df
        return None
    except:
        return None

# --- SIDEBAR ---
csv_list = get_all_csv_files()

with st.sidebar:
    st.header("📂 Data Manager")
    if csv_list:
        selected_user = st.selectbox("Din fil (Jonas):", csv_list, key="user_select")
        selected_ref = st.selectbox("Reference (Leeroy):", csv_list, index=min(1, len(csv_list)-1), key="ref_select")
    else:
        st.error("⚠️ Ingen CSV-filer fundet på GitHub endnu.")
        st.info("Husk at uploade dine filer til dit repo og vent 10 sekunder.")
        selected_user = selected_ref = None

    st.divider()
    t_len = st.number_input("Banelængde (m)", value=4252)
    diff_target = st.number_input("Delta (s)", value=0.648, format="%.3f")
    zoom = st.slider("Bane-sektion (%)", 0.0, 100.0, (0.0, 100.0))

# --- MAIN ---
df_u = load_selected_data(selected_user)
df_r = load_selected_data(selected_ref)

if df_u is not None and df_r is not None:
    grid = np.linspace(0, 1, 2000)
    data = pd.DataFrame({'dist': grid * 100})
    
    mapping = [('speed','speed'), ('thr','throttle'), ('brk','brake'), ('gr','gear'), ('tx','trackx'), ('ty','tracky')]
    for k, col in mapping:
        if col in df_u.columns: data[f'u_{k}'] = np.interp(grid, df_u['lapdistpct'], df_u[col])
        if col in df_r.columns: data[f'r_{k}'] = np.interp(grid, df_r['lapdistpct'], df_r[col])
    
    # Delta Beregning
    if 'u_speed' in data and 'r_speed' in data:
        u_ms, r_ms = np.maximum(data['u_speed']/3.6, 0.5), np.maximum(data['r_speed']/3.6, 0.5)
        raw = np.cumsum(((1/2000)*t_len)/u_ms - ((1/2000)*t_len)/r_ms)
        data['delta'] = raw * (diff_target / (raw.iloc[-1] if abs(raw.iloc[-1]) > 0.01 else 1))

    view = data[(data['dist'] >= zoom[0]) & (data['dist'] <= zoom[1])]

    t1, t2 = st.tabs(["📊 Telemetri", "🤖 Coach"])

    with t1:
        with st.expander("📍 Kort"):
            if 'u_tx' in data.columns:
                m_fig = go.Figure()
                m_fig.add_trace(go.Scatter(x=data['u_tx'], y=data['u_ty'], line=dict(color='gray', width=1)))
                m_fig.add_trace(go.Scatter(x=view['u_tx'], y=view['u_ty'], line=dict(color=C_JONAS, width=4)))
                m_fig.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
                st.plotly_chart(m_fig, use_container_width=True)

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.5, 0.25, 0.25])
        fig.add_trace(go.Scatter(x=view['dist'], y=view.get('r_speed'), name="Ref", line=dict(color=C_LEEROY, width=1, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=view['dist'], y=view.get('u_speed'), name="Du", line=dict(color=C_JONAS, width=2)), row=1, col=1)
        if 'delta' in view.columns:
            fig.add_trace(go.Scatter(x=view['dist'], y=view['delta'], fill='tozeroy', line=dict(color='white', width=1)), row=2, col=1)
        fig.add_trace(go.Scatter(x=view['dist'], y=view.get('u_thr', 0)*100, line=dict(color='green', width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=view['dist'], y=view.get('u_brk', 0)*100, fill='tozeroy', line=dict(color='red', width=0)), row=3, col=1)
        fig.update_layout(height=450, margin=dict(l=5,r=5,t=5,b=5), template="plotly_dark", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})
else:
    st.info("👈 Åbn menuen og vælg filer. Hvis listen er tom, tjek at dine filer slutter på .csv på GitHub.")
