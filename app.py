import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- KONFIGURATION: Dine specifikke GitHub links ---
USER = "barefordijegsigerdet-ux"
REPO = "iracing-engineer"

# Links til Raw data
URL_REF = f"https://raw.githubusercontent.com/{USER}/{REPO}/main/leeroy_zandvoort.csv"
URL_USER = f"https://raw.githubusercontent.com/{USER}/{REPO}/main/jonas_zandvoort.csv"
URL_SESS = f"https://raw.githubusercontent.com/{USER}/{REPO}/main/session_data.csv"

# --- Sideopsætning ---
st.set_page_config(page_title="iRacing Engineer: Jonas vs Leeroy", layout="wide")

@st.cache_data
def load_data(url):
    try:
        return pd.read_csv(url)
    except:
        return None

def analyze_data(df_ref, df_user):
    common_dist = np.linspace(0, 1, 3000)
    
    # Interpolering af hastighed (m/s)
    ref_speed_ms = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Speed']) / 3.6
    user_speed_ms = np.interp(common_dist, df_user['LapDistPct'], df_user['Speed']) / 3.6
    
    data = {
        'dist': common_dist * 100,
        'ref_speed': ref_speed_ms * 3.6,
        'user_speed': user_speed_ms * 3.6,
        'ref_brake': np.interp(common_dist, df_ref['LapDistPct'], df_ref['Brake']),
        'user_brake': np.interp(common_dist, df_user['LapDistPct'], df_user['Brake']),
        'ref_throttle': np.interp(common_dist, df_ref['LapDistPct'], df_ref['Throttle']),
        'user_throttle': np.interp(common_dist, df_user['LapDistPct'], df_user['Throttle']),
        'user_steer': np.interp(common_dist, df_user['LapDistPct'], df_user['SteeringWheelAngle']),
    }

    # Delta beregning (Zandvoort ca. 4252m)
    track_len = 4252
    dist_step = (1/3000) * track_len
    delta_steps = (dist_step / np.maximum(user_speed_ms, 0.5)) - (dist_step / np.maximum(ref_speed_ms, 0.5))
    data['delta'] = np.cumsum(delta_steps)
    return data

# --- UI ---
st.title("🏎️ iRacing Engineer: Jonas vs. Leeroy")
st.caption(f"Data hentes fra: {USER}/{REPO}")

# Forsøg at hente data automatisk
df_ref = load_data(URL_REF)
df_user = load_data(URL_USER)
df_sess = load_data(URL_SESS)

# Hvis data ikke findes, så vis fejlkode og manuel upload
if df_ref is None or df_user is None:
    st.error("Kunne ikke hente data fra GitHub. Tjek venligst:")
    st.write(f"1. At dine filer hedder præcis: `leeroy_zandvoort.csv`, `jonas_zandvoort.csv` og `session_data.csv` i dit repo.")
    st.write(f"2. At de ligger direkte på forsiden (main branch).")
    
    st.divider()
    st.subheader("Manuel Upload (Backup)")
    u1, u2 = st.columns(2)
    with u1:
        ref_file = st.file_uploader("Upload Leeroy CSV", type="csv")
    with u2:
        user_file = st.file_uploader("Upload Jonas CSV", type="csv")
    
    if ref_file: df_ref = pd.read_csv(ref_file)
    if user_file: df_user = pd.read_csv(user_file)

# Når data er klar
if df_ref is not None and df_user is not None:
    data = analyze_data(df_ref, df_user)
    
    # Top Stats
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Delta", f"+{data['delta'][-1]:.3f}s", delta_color="inverse")
    with c2:
        track_temp = df_sess["Track temp"].iloc[-1] if df_sess is not None else "N/A"
        st.metric("Bane Temperatur", f"{track_temp:.1f}°C" if isinstance(track_temp, (float, int)) else track_temp)
    with c3:
        st.metric("Max Hastighed", f"{data['user_speed'].max():.1f} km/t")

    # Grafer
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.2, 0.3])
    
    # Speed
    fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan')), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red')), row=1, col=1)
    
    # Delta
    fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
    
    # Pedals
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='green')), row=3, col=1)
    fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=3, col=1)

    fig.update_layout(height=750, template="plotly_dark", hovermode="x unified", margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Venter på data. Tjek dine links i koden eller upload manuelt.")
