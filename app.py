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

st.set_page_config(page_title="iRacing Pro Coach", layout="wide")

@st.cache_data
def get_file_list():
    api_url = f"https://api.github.com/repos/{USER}/{REPO}/contents/"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            return [file['name'] for file in response.json()]
    except: return []
    return []

@st.cache_data
def load_data_by_keyword(keyword):
    files = get_file_list()
    target_file = next((f for f in files if keyword.lower() in f.lower() and f.endswith('.csv')), None)
    if target_file:
        raw_url = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{target_file}".replace(" ", "%20")
        try: return pd.read_csv(raw_url)
        except: return None
    return None

def analyze_data(df_ref, df_user):
    common_dist = np.linspace(0, 1, 3000)
    ref_speed = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Speed'])
    user_speed = np.interp(common_dist, df_user['LapDistPct'], df_user['Speed'])
    
    track_len = 4252
    dist_step = (1/3000) * track_len
    ref_ms = np.maximum(ref_speed / 3.6, 0.5)
    user_ms = np.maximum(user_speed / 3.6, 0.5)
    
    delta_steps = (dist_step / user_ms) - (dist_step / ref_ms)
    delta_time = np.cumsum(delta_steps)

    return {
        'dist': common_dist * 100,
        'ref_speed': ref_speed,
        'user_speed': user_speed,
        'delta': delta_time,
        'user_throttle': np.interp(common_dist, df_user['LapDistPct'], df_user['Throttle']),
        'user_brake': np.interp(common_dist, df_user['LapDistPct'], df_user['Brake']),
        'ref_throttle': np.interp(common_dist, df_ref['LapDistPct'], df_ref['Throttle']),
        'ref_brake': np.interp(common_dist, df_ref['LapDistPct'], df_ref['Brake'])
    }

# --- UI START ---
st.title("🏎️ iRacing Pro Engineer")

df_ref = load_data_by_keyword("Leeroy")
df_user = load_data_by_keyword("Jonas")
df_sess = load_data_by_keyword("Offline Testing")

if df_ref is not None and df_user is not None:
    data = analyze_data(df_ref, df_user)
    
    # 1. TOP DASHBOARD (METRICS)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Delta", f"+{data['delta'][-1]:.3f}s", delta_color="inverse")
    with c2:
        # Beregn Optimal Lap fra session data
        if df_sess is not None:
            opt_lap = df_sess['Sector 1'].min() + df_sess['Sector 2'].min() + df_sess['Sector 3'].min()
            st.metric("Din Optimal Lap", f"{opt_lap:.3f}s")
        else: st.metric("Din Optimal Lap", "N/A")
    with c3:
        temp = f"{df_sess['Track temp'].iloc[-1]:.1f}°C" if df_sess is not None else "N/A"
        st.metric("Bane Temp", temp)
    with c4:
        st.metric("Topfart", f"{data['user_speed'].max():.1f} km/t")

    # 2. TELEMETRI GRAFER
    tab1, tab2 = st.tabs(["📊 Grafer", "🤖 Coach Feedback"])
    
    with tab1:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04, 
                           row_heights=[0.5, 0.2, 0.3],
                           subplot_titles=("Hastighed (km/t)", "Delta (Tid tabt/vundet)", "Pedal Arbejde"))

        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        
        # Gas/Brems sammenligning
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Jonas Gas", line=dict(color='green')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, name="Leeroy Gas", line=dict(color='rgba(0,255,0,0.2)', dash='dot')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Jonas Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=3, col=1)

        fig.update_layout(height=800, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("🤖 Coach Analyse")
        
        # Find hvor der tabes mest tid (største delta-stigning)
        delta_diff = np.diff(data['delta'])
        worst_idx = np.argmax(delta_diff)
        worst_pct = data['dist'][worst_idx]
        
        col_coach1, col_coach2 = st.columns(2)
        with col_coach1:
            st.subheader("Her taber du mest!")
            st.error(f"Ved {worst_pct:.1f}% af banen stiger din delta hurtigt.")
            st.write("Kig på grafen: Leeroy bærer typisk mere fart gennem midten af svinget her.")
            
        with col_coach2:
            st.subheader("Input Teknik")
            # Tjek for Coasting (Hverken gas eller brems)
            coasting = np.sum((data['user_throttle'] < 0.05) & (data['user_brake'] < 0.05))
            if coasting > 100:
                st.warning("⚠️ Du 'coaster' for meget. Du er hverken på gas eller brems i længere tid.")
            else:
                st.success("✅ God aggressivitet. Du skifter hurtigt mellem pedalerne.")

else:
    st.error("Kunne ikke indlæse telemetri. Tjek dine filer på GitHub.")
