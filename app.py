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
COLOR_JONAS = '#FF4B4B' # Rød
COLOR_LEEROY = '#00D4FF' # Cyan

st.set_page_config(page_title="iRacing Engineer PRO", layout="wide")

# --- SIDEBAR: KONTROL PANEL ---
st.sidebar.header("⚙️ Session Kontrol")
track_len = st.sidebar.number_input("Banelængde (meter)", value=4252)
time_ref = st.sidebar.number_input("Reference Tid (sekunder)", value=94.500, format="%.3f")
time_user = st.sidebar.number_input("Din Tid (sekunder)", value=95.148, format="%.3f")

st.sidebar.divider()
st.sidebar.subheader("📍 Zoom & Fokus")
st.sidebar.info("Highlight en sektion af banen herunder for at zoome ind på telemetrien.")
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
            # Normaliser kolonnenavne (fjern mellemrum og gør små)
            df.columns = [c.strip().lower() for c in df.columns]
            
            if 'lapdistpct' in df.columns:
                df = df.drop_duplicates(subset=['lapdistpct']).sort_values(by='lapdistpct')
                if 'gear' in df.columns:
                    df['gear'] = df['gear'].replace(0, np.nan).ffill().fillna(1)
                if 'speed' in df.columns and df['speed'].max() < 120:
                    df['speed'] = df['speed'] * 3.6
            return df
    except Exception as e:
        return None

def analyze(df_ref, df_user, track_len, diff):
    grid = np.linspace(0, 1, 6000)
    res = {'dist': grid * 100}
    
    # Mapping af potentielle kolonnenavne
    mapping = {
        'speed': ['speed', 'velocity', 'v'],
        'throttle': ['throttle', 'gas', 'throttle_raw'],
        'brake': ['brake', 'brake_raw'],
        'gear': ['gear'],
        'steer': ['steeringwheelangle', 'steer', 'steering'],
        'tx': ['trackx', 'pos_x', 'lat'],
        'ty': ['tracky', 'pos_y', 'lon']
    }
    
    for key, alts in mapping.items():
        # Find bedste match for Jonas
        u_col = next((c for c in df_user.columns if c in alts), None)
        if u_col:
            res[f'user_{key}'] = np.interp(grid, df_user['lapdistpct'], df_user[u_col])
        
        # Find bedste match for Leeroy
        r_col = next((c for c in df_ref.columns if c in alts), None)
        if r_col:
            res[f'ref_{key}'] = np.interp(grid, df_ref['lapdistpct'], df_ref[r_col])

    # Beregn Delta
    if 'user_speed' in res and 'ref_speed' in res:
        u_ms, r_ms = np.maximum(res['user_speed']/3.6, 0.5), np.maximum(res['ref_speed']/3.6, 0.5)
        step = (1/6000) * track_len
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

    t1, t2, t3 = st.tabs(["📊 Synkroniseret Telemetri", "🤖 AI Coach", "🔧 Garage"])

    with t1:
        col_map, col_graphs = st.columns([1, 2])
        
        with col_map:
            st.subheader("📍 Track Position")
            if 'user_tx' in data.columns and 'user_ty' in data.columns:
                fig_map = go.Figure()
                # Hele banen (baggrund)
                fig_map.add_trace(go.Scatter(x=full_data['user_tx'], y=full_data['user_ty'], 
                                            line=dict(color='rgba(255,255,255,0.1)', width=2), hoverinfo='skip'))
                # Valgt sektion (highlight)
                fig_map.add_trace(go.Scatter(x=data['user_tx'], y=data['user_ty'], 
                                            line=dict(color=COLOR_JONAS, width=6), name="Valgt Sektion"))
                fig_map.update_layout(height=450, template="plotly_dark", showlegend=False,
                                     xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1))
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                # Fallback hvis GPS mangler
                st.warning("GPS data ikke fundet i CSV.")
                st.info("Brug slideren til venstre for at navigere på banen via distancen.")
                # Vis en progress bar som 'mini-kort'
                st.write(f"Aktuelt fokus: **{view_range[0]}% - {view_range[1]}%**")
                st.progress(view_range[1]/100)

        with col_graphs:
            fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                               row_heights=[0.4, 0.2, 0.2, 0.2])
            
            # Hastighed
            fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Ref", line=dict(color=COLOR_LEEROY, dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Du", line=dict(color=COLOR_JONAS, width=3)), row=1, col=1)
            
            # Delta
            if 'delta' in data.columns:
                fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white', width=1)), row=2, col=1)
            
            # Pedaler
            fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Gas", line=dict(color='#00FF00', width=2)), row=3, col=1)
            fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Brems", fill='tozeroy', line=dict(color='#FF0000', width=0)), row=3, col=1)
            
            # Gear
            fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Gear", line=dict(color='orange', shape='hv')), row=4, col=1)

            fig.update_layout(height=700, template="plotly_dark", hovermode="x unified", showlegend=False,
                             margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.header("🤖 AI Coach: Fokusområde")
        # Find værste punkt i det valgte område
        if not data.empty and 'delta' in data.columns:
            local_loss = data['delta'].iloc[-1] - data['delta'].iloc[0]
            st.metric("Tidstab i denne sektion", f"{local_loss:.3f}s")
            
            st.markdown(f"""
            ### Analyse af {view_range[0]}% til {view_range[1]}%
            * **Topfart:** Du rammer {data['user_speed'].max():.1f} km/t her.
            * **Minimumfart:** Din laveste fart i svinget er {data['user_speed'].min():.1f} km/t.
            * **Input:** Din maksimale bremsestyrke er {(data['user_brake'].max()*100):.0f}%.
            """)
else:
    st.error("Kunne ikke indlæse Jonas.csv eller Leeroy.csv. Tjek dine filnavne på GitHub.")
