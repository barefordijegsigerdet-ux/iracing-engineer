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
            
            # Sørg for at vi har LapDistPct til interpolation
            if 'LapDistPct' in df.columns:
                df = df.drop_duplicates(subset=['LapDistPct']).sort_values(by='LapDistPct')
                # Fix Gear
                if 'Gear' in df.columns:
                    df['Gear'] = df['Gear'].replace(0, np.nan).ffill().fillna(1)
                # Hastighedskonvertering hvis nødvendigt
                if df['Speed'].max() < 100:
                    df['Speed'] = df['Speed'] * 3.6
            return df
    except: return None

def analyze(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 6000)
    res = {'dist': grid * 100}
    # Kolonner vi forventer i filerne
    cols = ['Speed', 'Throttle', 'Brake', 'Gear', 'SteeringWheelAngle']
    
    for col in cols:
        short = 'steer' if col == 'SteeringWheelAngle' else col.lower()
        # Vi tvinger interpolation for BEGGE kørere her
        res[f'ref_{short}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
        res[f'user_{short}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    # Delta beregning (Zandvoort baseline)
    track_len = 4252
    step = (1/6000) * track_len
    u_ms = np.maximum(res['user_speed']/3.6, 0.5)
    r_ms = np.maximum(res['ref_speed']/3.6, 0.5)
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    res['delta'] = raw_delta * (official_diff / (raw_delta[-1] if raw_delta[-1] != 0 else 1))
    return res

# --- DATA LOAD ---
df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")
df_sess = load_and_clean_data("Offline")

st.title("🏎️ iRacing Engineer PRO")

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)
    
    tab1, tab2, tab3 = st.tabs(["📊 Telemetri", "🤖 AI Coach", "🔧 Garage & Setup"])

    with tab1:
        # 6 separate rækker men med overlay på de relevante
        fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                           row_heights=[0.3, 0.15, 0.1, 0.1, 0.1, 0.25],
                           subplot_titles=("Hastighed (km/t)", "Delta (s)", "Gas (%)", "Brems (%)", "Gear", "Ratvinkel"))
        
        # 1. Speed Overlay
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy (Ref)", line=dict(color=COLOR_LEEROY, dash='dot', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas (Du)", line=dict(color=COLOR_JONAS, width=2)), row=1, col=1)
        
        # 2. Delta
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        
        # 3. Gas Overlay
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, name="Leeroy Gas", line=dict(color='rgba(0,255,255,0.2)', dash='dot')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Jonas Gas", line=dict(color='green')), row=3, col=1)
        
        # 4. Brems Overlay
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_brake']*100, name="Leeroy Brems", line=dict(color='rgba(0,255,255,0.2)', dash='dot')), row=4, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Jonas Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=4, col=1)
        
        # 5. Gear Overlay
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_gear'], name="Leeroy Gear", line=dict(color=COLOR_LEEROY, dash='dot', shape='hv')), row=5, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Jonas Gear", line=dict(color='orange', shape='hv')), row=5, col=1)
        
        # 6. Ratvinkel
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_steer'], name="Leeroy Rat", line=dict(color='rgba(0,255,255,0.2)', dash='dot')), row=6, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_steer'], name="Jonas Rat", line=dict(color='yellow')), row=6, col=1)

        fig.update_layout(height=1200, template="plotly_dark", hovermode="x unified", showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("🤖 AI Coach Analyse")
        # Beregn tidstabspunkter
        diffs = np.gradient(data['delta'])
        worst_idx = np.argmax(diffs)
        
        c1, c2 = st.columns(2)
        c1.metric("Current Delta", f"+{data['delta'][-1]:.3f}s", delta="-0.648s")
        c2.warning(f"Fokus-område: {data['dist'][worst_idx]:.1f}% af banen")
        
        st.markdown(f"""
        ### 📋 Dine vigtigste fokuspunkter:
        * **Topfart:** Din topfart er **{np.max(data['user_speed']):.1f} km/t**, mens Leeroy rammer **{np.max(data['ref_speed']):.1f} km/t**.
        * **Sving-Analyse:** Du taber mest tid ved banens {data['dist'][worst_idx]:.1f}% mærke. 
        * **Gear-forskel:** Leeroy bruger gear **{int(data['ref_gear'][worst_idx])}** i svinget, du bruger gear **{int(data['user_gear'][worst_idx])}**.
        * **Rat-input:** Du bruger i gennemsnit **{np.mean(np.abs(data['user_steer'])):.1f}°** ratvinkel. Prøv at mindske dette for at undgå understyring.
        """)

    with tab3:
        st.header("🔧 Garage & Setup")
        if df_sess is not None:
            # Metadata fra Offline filen
            m1, m2, m3 = st.columns(3)
            t_temp = df_sess['Track temp'].iloc[0] if 'Track temp' in df_sess.columns else "N/A"
            a_temp = df_sess['Air temp'].iloc[0] if 'Air temp' in df_sess.columns else "N/A"
            fuel = df_sess['Fuel used'].mean() if 'Fuel used' in df_sess.columns else 0
            
            m1.metric("Bane Temperatur", f"{t_temp}")
            m2.metric("Luft Temperatur", f"{a_temp}")
            m3.metric("Avg. Fuel/Lap", f"{fuel:.2f} L")
            
            st.divider()
            st.subheader("Sidste 5 Session Laps")
            st.dataframe(df_sess[['Lap', 'Lap time', 'Fuel used']].tail(5), use_container_width=True)
        else:
            st.info("Ingen session-log fundet (Offline fil).")
else:
    st.error("Kunne ikke finde Jonas.csv og Leeroy.csv. Tjek filnavne på GitHub.")
