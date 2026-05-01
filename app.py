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
                if 'Gear' in df.columns:
                    df['Gear'] = df['Gear'].replace(0, np.nan).ffill().fillna(1)
                if df['Speed'].max() < 100: # Auto-konverter m/s til km/t
                    df['Speed'] = df['Speed'] * 3.6
            return df
    except: return None

def analyze(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 6000)
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
    
    track_len = 4252
    step = (1/6000) * track_len
    u_ms = np.maximum(res['user_speed']/3.6, 0.5)
    r_ms = np.maximum(res['ref_speed']/3.6, 0.5)
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    res['delta'] = raw_delta * (official_diff / raw_delta[-1])
    return res

# --- MAIN APP STRUCTURE ---
st.title("🏎️ iRacing Engineer PRO")

# Sidebar for hurtig info
st.sidebar.header("Session Info")
st.sidebar.info("Bane: Zandvoort\nBil: GT3\nTarget Delta: +0.648s")

# Opretter tabs
tab1, tab2 = st.tabs(["📊 Telemetri Analyse", "🤖 AI Coach"])

df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)

    with tab1:
        fig = make_subplots(
            rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.02,
            row_heights=[0.3, 0.15, 0.12, 0.12, 0.1, 0.22],
            subplot_titles=("Hastighed (km/t)", "Delta (s)", "Gas (%)", "Brems (%)", "Gear", "Ratvinkel")
        )
        
        # Plotting (samme logik som før)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color=COLOR_LEEROY, width=1, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color=COLOR_JONAS, width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, line=dict(color=COLOR_LEEROY, dash='dot'), showlegend=False), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='green')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=4, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Gear", line=dict(color='orange', shape='hv')), row=5, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_steer'], name="Rat", line=dict(color='yellow')), row=6, col=1)

        fig.update_layout(height=1100, template="plotly_dark", hovermode="x unified")
        fig.update_yaxes(range=[0, 260], row=1, col=1)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("Coach Jonas' Analyse")
        
        # Simpel logik-baseret coaching
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Hvor taber du tid?")
            max_delta_pos = data['dist'][np.argmax(np.gradient(data['delta']))]
            st.write(f"⚠️ **Største tidstab:** Ved ca. {max_delta_pos:.1f}% af banen (omkring Sving 1/Tarzan).")
            st.write("💡 *Tip: Prøv at bremse 5 meter tidligere, men løsn bremsen hurtigere (trail braking).*")

        with c2:
            st.subheader("Input Kvalitet")
            avg_throttle = np.mean(data['user_throttle'])
            ref_throttle = np.mean(data['ref_throttle'])
            if avg_throttle < ref_throttle:
                st.warning("Du er for forsigtig på gassen sammenlignet med Leeroy.")
            else:
                st.success("Din gas-applikation matcher referencen godt!")

        st.divider()
        st.write("### Top 3 fokuspunkter for næste stint:")
        st.markdown("""
        1. **Topfart:** Leeroy henter tid på langsiden. Tjek om du får et bedre exit ud af det sidste sving.
        2. **Gearvalg:** Du bruger 2. gear steder hvor Leeroy bliver i 3. gear for at holde momentet.
        3. **Rat-ro:** Din ratvinkel er mere urolig. Prøv at "stole" mere på bilens aero i de hurtige sving.
        """)

else:
    st.error("Upload venligst telemetri-filer for at aktivere analysen.")
