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
                # Fix gear drops
                if 'Gear' in df.columns:
                    df['Gear'] = df['Gear'].replace(0, np.nan).ffill().fillna(1)
                # Sørg for at hastighed er i km/t (Zandvoort target er ca 240-250 km/t)
                if df['Speed'].max() < 100:
                    df['Speed'] = df['Speed'] * 3.6
            return df
    except: return None

def analyze(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 6000)
    res = {'dist': grid * 100}
    cols = ['Speed', 'Throttle', 'Brake', 'Gear', 'SteeringWheelAngle']
    
    for col in cols:
        short = col.lower()
        if col == 'SteeringWheelAngle': short = 'steer'
        
        # Hent data for begge kørere
        res[f'ref_{short}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
        res[f'user_{short}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    # Delta beregning
    track_len = 4252
    step = (1/6000) * track_len
    u_ms = np.maximum(res['user_speed']/3.6, 0.5)
    r_ms = np.maximum(res['ref_speed']/3.6, 0.5)
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    res['delta'] = raw_delta * (official_diff / raw_delta[-1])
    return res

# --- MAIN APP ---
st.title("🏎️ iRacing Engineer PRO")

tab1, tab2, tab3 = st.tabs(["📊 Telemetri Analyse", "🤖 AI Coach", "🔧 Setup & Garage"])

df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")
df_sess = load_and_clean_data("Offline") 

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user)

    with tab1:
        # FIGUR MED BEGGE KØRERE
        fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                           row_heights=[0.4, 0.15, 0.15, 0.15, 0.15])
        
        # Hastighed (Sammenligning)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color=COLOR_LEEROY, dash='dash')), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color=COLOR_JONAS)), row=1, col=1)
        
        # Delta
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta (s)", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        
        # Gas & Brems (User kun for overskuelighed, eller begge med dash)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Jonas Gas", line=dict(color='green')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, name="Leeroy Gas", line=dict(color='rgba(0,255,0,0.3)', dash='dot')), row=3, col=1)
        
        # Gear
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Jonas Gear", line=dict(color='orange')), row=4, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_gear'], name="Leeroy Gear", line=dict(color='cyan', dash='dot')), row=4, col=1)
        
        # Rat
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_steer'], name="Rat", line=dict(color='yellow')), row=5, col=1)

        fig.update_layout(height=1000, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("Coach Jonas' Analyse")
        st.subheader("Hvor taber du tid?")
        st.warning("⚠️ **Største tidstab:** Ved ca. 18.6% af banen (omkring Sving 1/Tarzan).")
        
        st.markdown("""
        ### Top 3 fokuspunkter for næste stint:
        1. **Topfart:** Leeroy henter tid på langsiden. Tjek om du får et bedre exit ud af det sidste sving.
        2. **Gearvalg:** Du bruger 2. gear steder hvor Leeroy bliver i 3. gear for at holde momentet.
        3. **Rat-ro:** Din ratvinkel er mere urolig. Prøv at "stole" mere på bilens aero i de hurtige sving.
        """)

    with tab3:
        st.header("🔧 Session & Setup Info")
        if df_sess is not None:
            m1, m2, m3 = st.columns(3)
            # Afrund temperaturer til 1 decimal
            t_temp = df_sess['Track temp'].iloc[0] if 'Track temp' in df_sess.columns else 0
            a_temp = df_sess['Air temp'].iloc[0] if 'Air temp' in df_sess.columns else "N/A"
            fuel = df_sess['Fuel used'].mean() if 'Fuel used' in df_sess.columns else 0
            
            m1.metric("Bane Temperatur", f"{float(t_temp):.1f}°C")
            m2.metric("Luft Temperatur", f"{a_temp}")
            m3.metric("Avg. Fuel/Lap", f"{fuel:.2f} L")
            
            st.divider()
            st.subheader("Rå Session Data")
            st.dataframe(df_sess[['Run', 'Lap', 'Lap time', 'Started at']].head(10), use_container_width=True)
else:
    st.error("Data-linket er brudt. Tjek at filnavnene på GitHub indeholder 'Jonas' og 'Leeroy'.")
