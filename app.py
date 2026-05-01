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

st.set_page_config(page_title="iRacing Ultimate Engineer", layout="wide")

# Sving-navne for Zandvoort (ca. baneposition i %)
CORNERS = [
    (5, "Tarzan (T1)"), (15, "Gerlach (T2)"), (22, "Hugenholtz (T3)"),
    (35, "Hunzerug (T4)"), (45, "Rob Slotemaker (T5)"), (52, "Scheivlak (T7)"),
    (65, "Masters (T9)"), (75, "Hans Ernst (T11)"), (92, "Arie Luyendyk (T14)")
]

@st.cache_data
def get_file_list():
    api_url = f"https://api.github.com/repos/{USER}/{REPO}/contents/"
    try:
        r = requests.get(api_url); return [f['name'] for f in r.json()] if r.status_code == 200 else []
    except: return []

@st.cache_data
def load_data_by_keyword(keyword):
    files = get_file_list()
    target = next((f for f in files if keyword.lower() in f.lower() and f.endswith('.csv')), None)
    if target:
        url = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{target}".replace(" ", "%20")
        return pd.read_csv(url)
    return None

def analyze_data(df_ref, df_user):
    common_dist = np.linspace(0, 1, 3000)
    res = {'dist': common_dist * 100}
    for col in ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'Gear', 'LatAccel']:
        res[f'ref_{col.lower()}'] = np.interp(common_dist, df_ref['LapDistPct'], df_ref[col])
        res[f'user_{col.lower()}'] = np.interp(common_dist, df_user['LapDistPct'], df_user[col])
    
    # Delta
    track_len = 4252
    dist_step = (1/3000) * track_len
    delta_steps = (dist_step / np.maximum(res['user_speed']/3.6, 0.5)) - (dist_step / np.maximum(res['ref_speed']/3.6, 0.5))
    res['delta'] = np.cumsum(delta_steps)
    return res

# --- UI ---
st.title("🏎️ iRacing Ultimate Engineer")

df_ref = load_data_by_keyword("Leeroy")
df_user = load_data_by_keyword("Jonas")
df_sess = load_data_by_keyword("Offline Testing")

if df_ref is not None and df_user is not None:
    data = analyze_data(df_ref, df_user)
    
    # Dashboard
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Delta til Leeroy", f"+{data['delta'][-1]:.3f}s", delta_color="inverse")
    if df_sess is not None:
        opt = df_sess['Sector 1'].min() + df_sess['Sector 2'].min() + df_sess['Sector 3'].min()
        m2.metric("Optimal Lap", f"{opt:.3f}s")
        m3.metric("Bane Temp", f"{df_sess['Track temp'].iloc[-1]:.1f}°C")
    m4.metric("Max Lateral G", f"{abs(data['user_lataccel']).max()/9.81:.2f} G")

    tabs = st.tabs(["🚀 Speed/Delta", "☸️ Steering & G's", "🎮 Pedals/Gear", "🤖 Pro Coach"])

    with tabs[0]:
        fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        fig1.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan')), row=1, col=1)
        fig1.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red')), row=1, col=1)
        fig1.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        # Tilføj sving-navne som vertikale linjer
        for pos, name in CORNERS:
            fig1.add_vline(x=pos, line_width=1, line_dash="dash", line_color="gray")
        fig1.update_layout(height=600, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig1, use_container_width=True)

    with tabs[1]:
        fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True)
        fig2.add_trace(go.Scatter(x=data['dist'], y=data['user_steeringwheelangle'], name="Ratvinkel", line=dict(color='yellow')), row=1, col=1)
        fig2.add_trace(go.Scatter(x=data['dist'], y=data['user_lataccel']/9.81, name="G-Force", line=dict(color='orange')), row=2, col=1)
        fig2.update_layout(height=600, template="plotly_dark")
        st.plotly_chart(fig2, use_container_width=True)

    with tabs[2]:
        fig3 = make_subplots(rows=2, cols=1, shared_xaxes=True)
        fig3.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='green')), row=1, col=1)
        fig3.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", line=dict(color='red')), row=1, col=1)
        fig3.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Gear", line=dict(color='white', shape='hv')), row=2, col=1)
        fig3.update_layout(height=600, template="plotly_dark")
        st.plotly_chart(fig3, use_container_width=True)

    with tabs[3]:
        st.header("🤖 Race Engineer Notes")
        loss = np.diff(data['delta'])
        worst_idx = np.argmax(loss)
        worst_pos = data['dist'][worst_idx]
        
        # Find nærmeste sving-navn
        corner_name = next((name for pos, name in reversed(CORNERS) if pos <= worst_pos), "Start/Finish")
        
        st.error(f"📍 Største tidstab fundet ved **{corner_name}**.")
        st.write(f"Du taber tid her, fordi din minimumshastighed er {data['ref_speed'][worst_idx] - data['user_speed'][worst_idx]:.1f} km/t lavere end Leeroys.")
        
        st.divider()
        st.subheader("💡 Kørestils-tip")
        if data['user_brake'].max() > 0.98:
            st.warning("Du låser ABS-systemet (100% brems). Prøv at bremse hårdt (85%), men slip bremsen gradvist tidligere (Trail braking) for at få bilen til at rotere bedre ind i svinget.")

else:
    st.info("Venter på at finde 'Jonas', 'Leeroy' og 'Offline' filer på GitHub...")
