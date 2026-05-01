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

st.set_page_config(page_title="iRacing Pro Engineer", layout="wide")

@st.cache_data
def get_file_list():
    api_url = f"https://api.github.com/repos/{USER}/{REPO}/contents/"
    try:
        r = requests.get(api_url)
        if r.status_code == 200: return [f['name'] for f in r.json()]
    except: return []
    return []

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
    
    # Standard kanaler
    res = {'dist': common_dist * 100}
    for col in ['Speed', 'Throttle', 'Brake', 'SteeringWheelAngle', 'Gear', 'LatAccel']:
        res[f'ref_{col.lower()}'] = np.interp(common_dist, df_ref['LapDistPct'], df_ref[col])
        res[f'user_{col.lower()}'] = np.interp(common_dist, df_user['LapDistPct'], df_user[col])
    
    # Delta beregning
    track_len = 4252
    dist_step = (1/3000) * track_len
    delta_steps = (dist_step / np.maximum(res['user_speed']/3.6, 0.5)) - (dist_step / np.maximum(res['ref_speed']/3.6, 0.5))
    res['delta'] = np.cumsum(delta_steps)
    return res

# --- UI ---
st.title("🏎️ iRacing Pro Engineer")

df_ref = load_data_by_keyword("Leeroy")
df_user = load_data_by_keyword("Jonas")
df_sess = load_data_by_keyword("Offline Testing")

if df_ref is not None and df_user is not None:
    data = analyze_data(df_ref, df_user)
    
    # Dashboard Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Delta", f"+{data['delta'][-1]:.3f}s", delta_color="inverse")
    if df_sess is not None:
        opt = df_sess['Sector 1'].min() + df_sess['Sector 2'].min() + df_sess['Sector 3'].min()
        m2.metric("Optimal Lap", f"{opt:.3f}s")
        m3.metric("Bane Temp", f"{df_sess['Track temp'].iloc[-1]:.1f}°C")
    m4.metric("Max G-Force", f"{abs(data['user_lataccel']).max()/9.81:.2f} G")

    # Tabs til forskellige analyser
    tab1, tab2, tab3 = st.tabs(["📊 Speed & Delta", "⚙️ Gear & G-Force", "🤖 Coach Analysis"])

    with tab1:
        fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.02)
        fig1.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy Speed", line=dict(color='cyan')), row=1, col=1)
        fig1.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas Speed", line=dict(color='red')), row=1, col=1)
        fig1.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        fig1.update_layout(height=600, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05)
        # Gear comparison
        fig2.add_trace(go.Scatter(x=data['dist'], y=data['ref_gear'], name="Leeroy Gear", line=dict(color='cyan', dash='dot')), row=1, col=1)
        fig2.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Jonas Gear", line=dict(color='red')), row=1, col=1)
        # G-Force (Lateral)
        fig2.add_trace(go.Scatter(x=data['dist'], y=data['user_lataccel']/9.81, name="Jonas G-Load", line=dict(color='orange')), row=2, col=1)
        fig2.update_layout(height=600, template="plotly_dark", title="Gear Selection & Cornering G's")
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.subheader("Engineer Insight")
        # Find corner with max delta loss
        loss = np.diff(data['delta'])
        worst_idx = np.argmax(loss)
        st.warning(f"Største tidstab sker ved {data['dist'][worst_idx]:.1f}% af banen.")
        
        # Check brake intensity
        if data['user_brake'].max() > 0.95:
            st.info("💡 Tip: Du rammer 100% brems. I Porsche Cup kan det ofte betale sig at stoppe ved 85-90% for at undgå ABS-indgreb, der forlænger bremselængden.")

else:
    st.error("Data ikke fundet. Tjek GitHub-forbindelsen.")
