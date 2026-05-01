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
COLOR_JONAS = '#FF4B4B' 
COLOR_LEEROY = '#00D4FF' 

st.set_page_config(page_title="iRacing PRO Mobile", layout="wide")

# --- SIDEBAR (Skjult som standard på mobil) ---
st.sidebar.header("⚙️ Indstillinger")
track_len = st.sidebar.number_input("Banelængde (m)", value=4252)
time_ref = st.sidebar.number_input("Ref Tid (s)", value=94.500, format="%.3f")
time_user = st.sidebar.number_input("Din Tid (s)", value=95.148, format="%.3f")

st.sidebar.divider()
view_range = st.sidebar.slider("Bane-sektion (%)", 0.0, 100.0, (0.0, 100.0))

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
            df.columns = [c.strip().lower() for c in df.columns]
            if 'lapdistpct' in df.columns:
                df = df.drop_duplicates(subset=['lapdistpct']).sort_values(by='lapdistpct')
                if 'gear' in df.columns:
                    df['gear'] = df['gear'].replace(0, np.nan).ffill().fillna(1)
                if 'speed' in df.columns and df['speed'].max() < 120:
                    df['speed'] = df['speed'] * 3.6
            return df
    except: return None

def analyze(df_ref, df_user, track_len, diff):
    grid = np.linspace(0, 1, 3000) # Færre punkter for hurtigere mobil-rendering
    res = {'dist': grid * 100}
    mapping = {'speed':['speed','velocity'], 'throttle':['throttle','gas'], 'brake':['brake'], 'gear':['gear'], 'steer':['steeringwheelangle'], 'tx':['trackx'], 'ty':['tracky']}
    
    for key, alts in mapping.items():
        u_col = next((c for c in df_user.columns if c in alts), None)
        if u_col: res[f'user_{key}'] = np.interp(grid, df_user['lapdistpct'], df_user[u_col])
        r_col = next((c for c in df_ref.columns if c in alts), None)
        if r_col: res[f'ref_{key}'] = np.interp(grid, df_ref['lapdistpct'], df_ref[r_col])

    if 'user_speed' in res and 'ref_speed' in res:
        u_ms, r_ms = np.maximum(res['user_speed']/3.6, 0.5), np.maximum(res['ref_speed']/3.6, 0.5)
        step = (1/3000) * track_len
        raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
        res['delta'] = raw_delta * (diff / (raw_delta[-1] if abs(raw_delta[-1]) > 0.01 else 1))
    return pd.DataFrame(res)

# --- HOVED APP ---
df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")

if df_ref is not None and df_user is not None:
    full_data = analyze(df_ref, df_user, track_len, time_user - time_ref)
    mask = (full_data['dist'] >= view_range[0]) & (full_data['dist'] <= view_range[1])
    data = full_data[mask]

    # Tabs fungerer godt på mobil
    t1, t2, t3 = st.tabs(["📊 Data", "🤖 Coach", "🔧 Garage"])

    with t1:
        # 1. KORTET I EN EXPANDER (Sparer plads!)
        with st.expander("📍 Vis Banekort", expanded=False):
            if 'user_tx' in data.columns:
                fig_map = go.Figure()
                fig_map.add_trace(go.Scatter(x=full_data['user_tx'], y=full_data['user_ty'], line=dict(color='gray', width=1), hoverinfo='skip'))
                fig_map.add_trace(go.Scatter(x=data['user_tx'], y=data['user_ty'], line=dict(color=COLOR_JONAS, width=4)))
                fig_map.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0), template="plotly_dark", xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.write("Ingen GPS data.")

        # 2. KOMPAKTE GRAFER
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                           row_heights=[0.4, 0.2, 0.2, 0.2])
        
        # Speed
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Ref", line=dict(color=COLOR_LEEROY, width=1, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Du", line=dict(color=COLOR_JONAS, width=2)), row=1, col=1)
        
        # Delta
        if 'delta' in data.columns:
            fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], fill='tozeroy', line=dict(color='white', width=1)), row=2, col=1)
        
        # Pedals
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, line=dict(color='#00FF00', width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, fill='tozeroy', line=dict(color='#FF0000', width=0)), row=3, col=1)
        
        # Gear
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], line=dict(color='orange', shape='hv')), row=4, col=1)

        # Mobil-venlig højde og minimal margin
        fig.update_layout(height=500, margin=dict(l=5, r=5, t=10, b=10), template="plotly_dark", showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with t2:
        if not data.empty and 'delta' in data.columns:
            loss = data['delta'].iloc[-1] - data['delta'].iloc[0]
            st.metric("Tidstab her", f"{loss:.3f}s")
            st.write(f"Topfart: {data['user_speed'].max():.1f} km/t")
            st.progress(min(max(view_range[1]/100, 0.0), 1.0))

    with t3:
        st.subheader("Quick Setup")
        issue = st.selectbox("Problem?", ["Understyring", "Overstyring", "Bremser"])
        if issue == "Understyring":
            st.success("Prøv: Brake Bias bagud (-1%)")

else:
    st.error("Upload Jonas.csv og Leeroy.csv til GitHub")
