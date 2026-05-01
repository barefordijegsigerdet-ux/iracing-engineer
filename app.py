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
                # Gear fix (ffill)
                if 'Gear' in df.columns:
                    df['Gear'] = df['Gear'].replace(0, np.nan).ffill().fillna(1)
                # Hastighed km/t
                if df['Speed'].max() < 100:
                    df['Speed'] = df['Speed'] * 3.6
            return df
    except: return None

def analyze(df_ref, df_user, official_diff=0.648):
    grid = np.linspace(0, 1, 6000)
    res = {'dist': grid * 100}
    cols = ['Speed', 'Throttle', 'Brake', 'Gear', 'SteeringWheelAngle']
    for col in cols:
        short = 'steer' if col == 'SteeringWheelAngle' else col.lower()
        res[f'ref_{short}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
        res[f'user_{short}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    # Delta beregning
    track_len = 4252
    step = (1/6000) * track_len
    u_ms, r_ms = np.maximum(res['user_speed']/3.6, 0.5), np.maximum(res['ref_speed']/3.6, 0.5)
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    res['delta'] = raw_delta * (official_diff / raw_delta[-1])
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
        # Fuld sammenligning (Overlay)
        fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                           row_heights=[0.35, 0.15, 0.15, 0.15, 0.2])
        
        # Speed Overlay
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy (Ref)", line=dict(color=COLOR_LEEROY, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas (Du)", line=dict(color=COLOR_JONAS, width=2)), row=1, col=1)
        
        # Delta
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Tidstab", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        
        # Throttle & Brake (Combined for Jonas, Shadow for Leeroy)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, name="L. Throttle", line=dict(color='rgba(0,255,0,0.15)', dash='dot')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="J. Throttle", line=dict(color='green')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="J. Brake", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=3, col=1)
        
        # Gear Overlay
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_gear'], name="L. Gear", line=dict(color=COLOR_LEEROY, dash='dot', shape='hv')), row=4, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="J. Gear", line=dict(color='orange', shape='hv')), row=4, col=1)
        
        # Steering
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_steer'], name="Ratvinkel", line=dict(color='yellow')), row=5, col=1)

        fig.update_layout(height=1000, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("🤖 AI Coach: Jonas vs Leeroy")
        # Find punktet med største tidstab
        loss_idx = np.argmax(np.gradient(data['delta']))
        loss_dist = data['dist'][loss_idx]
        
        col1, col2 = st.columns(2)
        col1.metric("Delta Total", f"+{data['delta'][-1]:.3f}s", delta="-0.648s")
        col2.warning(f"Kritisk zone identificeret ved {loss_dist:.1f}%")

        st.markdown(f"""
        ### 📋 Analyse af kørsel
        1. **Hastighedstjek:** Leeroy rammer **{np.max(data['ref_speed']):.1f} km/t** på langsiden. Du rammer **{np.max(data['user_speed']):.1f} km/t**.
        2. **Sving-Analyse:** Ved banens {loss_dist:.1f}% mærke (Sving 1/2) taber du mest tid. 
        3. **Gearvalg:** Leeroy kører i gear **{int(data['ref_gear'][loss_idx])}** her, mens du er i gear **{int(data['user_gear'][loss_idx])}**.
        4. **Input:** Du bruger i gennemsnit **{np.mean(data['user_steer']):.1f}°** rat, hvor Leeroy bruger **{np.mean(data['ref_steer']):.1f}°**. Mere rat = mere dækslid.
        """)

    with tab3:
        st.header("🔧 Garage & Session Setup")
        if df_sess is not None:
            m1, m2, m3 = st.columns(3)
            # Hent metadata fra din Offline log
            track_t = df_sess['Track temp'].iloc[0] if 'Track temp' in df_sess.columns else "N/A"
            air_t = df_sess['Air temp'].iloc[0] if 'Air temp' in df_sess.columns else "N/A"
            fuel_avg = df_sess['Fuel used'].mean() if 'Fuel used' in df_sess.columns else 0
            
            m1.metric("Bane Temperatur", f"{track_t}")
            m2.metric("Luft Temperatur", f"{air_t}")
            m3.metric("Avg Fuel/Lap", f"{fuel_avg:.2f} L")
            
            st.divider()
            st.subheader("Session Log (Sidste 10 omgange)")
            st.dataframe(df_sess[['Lap', 'Lap time', 'Fuel used', 'Started at']].tail(10), use_container_width=True)
        else:
            st.info("Ingen Offline/Session data fundet. Upload 'Offline Analysis' CSV for at se setup data.")

else:
    st.error("Kunne ikke finde Jonas.csv eller Leeroy.csv på GitHub.")
