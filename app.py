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

# --- SIDEBAR (Universelle Indstillinger) ---
st.sidebar.header("⚙️ Session Indstillinger")
st.sidebar.markdown("Tilpas disse for at matche banen og bilen.")

# Bruger-input til dynamiske variabler
track_len = st.sidebar.number_input("Banelængde (meter)", value=4252, step=100) # Standard Zandvoort
time_ref = st.sidebar.number_input("Reference Tid (sekunder)", value=94.500, format="%.3f") # Fiktiv standard
time_user = st.sidebar.number_input("Din Tid (sekunder)", value=95.148, format="%.3f")
official_diff = time_user - time_ref

st.sidebar.divider()
st.sidebar.write(f"**Beregnet Target Delta:** `+{official_diff:.3f}s`")

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
                if df['Speed'].max() < 120: # Lidt sikrere tærskel for m/s vs km/t tjek
                    df['Speed'] = df['Speed'] * 3.6
            return df
    except: return None

def analyze(df_ref, df_user, track_len, official_diff):
    grid = np.linspace(0, 1, 6000)
    res = {'dist': grid * 100}
    cols = ['Speed', 'Throttle', 'Brake', 'Gear', 'SteeringWheelAngle']
    
    for col in cols:
        short = 'steer' if col == 'SteeringWheelAngle' else col.lower()
        res[f'ref_{short}'] = np.interp(grid, df_ref['LapDistPct'], df_ref[col])
        res[f'user_{short}'] = np.interp(grid, df_user['LapDistPct'], df_user[col])
    
    # Delta beregning med dynamisk banelængde
    step = (1/6000) * track_len
    u_ms = np.maximum(res['user_speed']/3.6, 0.5)
    r_ms = np.maximum(res['ref_speed']/3.6, 0.5)
    raw_delta = np.cumsum((step/u_ms) - (step/r_ms))
    
    # Fordel diff jævnt for at undgå division med 0 eller små tal
    res['delta'] = raw_delta * (official_diff / (raw_delta[-1] if abs(raw_delta[-1]) > 0.1 else 1))
    return res

# --- DATA LOAD ---
df_ref = load_and_clean_data("Leeroy")
df_user = load_and_clean_data("Jonas")
df_sess = load_and_clean_data("Offline")

st.title("🏎️ iRacing Engineer PRO")

if df_ref is not None and df_user is not None:
    data = analyze(df_ref, df_user, track_len, official_diff)
    
    tab1, tab2, tab3 = st.tabs(["📊 Telemetri", "🤖 AI Coach", "🔧 Setup & Garage"])

    with tab1:
        fig = make_subplots(rows=6, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                           row_heights=[0.3, 0.15, 0.1, 0.1, 0.1, 0.25],
                           subplot_titles=("Hastighed (km/t)", "Delta (s)", "Gas (%)", "Brems (%)", "Gear", "Ratvinkel"))
        
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Reference", line=dict(color=COLOR_LEEROY, dash='dot', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Du", line=dict(color=COLOR_JONAS, width=2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, name="Ref Gas", line=dict(color='rgba(0,255,255,0.2)', dash='dot')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Din Gas", line=dict(color='green')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_brake']*100, name="Ref Brems", line=dict(color='rgba(0,255,255,0.2)', dash='dot')), row=4, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Din Brems", fill='tozeroy', line=dict(color='rgba(255,0,0,0.3)')), row=4, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_gear'], name="Ref Gear", line=dict(color=COLOR_LEEROY, dash='dot', shape='hv')), row=5, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_gear'], name="Dit Gear", line=dict(color='orange', shape='hv')), row=5, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_steer'], name="Ref Rat", line=dict(color='rgba(0,255,255,0.2)', dash='dot')), row=6, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_steer'], name="Dit Rat", line=dict(color='yellow')), row=6, col=1)

        fig.update_layout(height=1200, template="plotly_dark", hovermode="x unified", showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.header("🤖 AI Coach Analyse")
        diffs = np.gradient(data['delta'])
        worst_idx = np.argmax(diffs)
        
        c1, c2 = st.columns(2)
        c1.metric("Beregnet Delta", f"+{data['delta'][-1]:.3f}s", delta=f"{-official_diff:.3f}s")
        c2.warning(f"Fokus-område: {data['dist'][worst_idx]:.1f}% af banen")
        
        st.markdown(f"""
        ### 📋 Dine vigtigste fokuspunkter:
        * **Topfart:** Din topfart er **{np.max(data['user_speed']):.1f} km/t**, mens referencen rammer **{np.max(data['ref_speed']):.1f} km/t**.
        * **Sving-Analyse:** Du taber mest tid ved banens {data['dist'][worst_idx]:.1f}% mærke. 
        * **Gear-forskel:** Referencen bruger gear **{int(data['ref_gear'][worst_idx])}** i svinget, du bruger gear **{int(data['user_gear'][worst_idx])}**.
        * **Rat-input:** Du bruger i gennemsnit **{np.mean(np.abs(data['user_steer'])):.1f}°** ratvinkel. 
        """)

    with tab3:
        st.header("🔧 Race Engineer: Setup Tuning")
        st.markdown("Brug dette interaktive værktøj til at rette bilens balance. Vælg dit problem, og få ingeniørens anbefaling.")

        if df_sess is not None:
            t_temp = df_sess['Track temp'].iloc[0] if 'Track temp' in df_sess.columns else "N/A"
            st.info(f"📍 **Banetemperatur lige nu:** {t_temp} (Husk at justere dit start-dæktryk efter dette!)")

        col_prob, col_phase = st.columns(2)
        with col_prob:
            issue = st.selectbox("Hvad er bilens største problem?", [
                "Vælg problem...",
                "Understyring (Bilen vil ikke dreje ind)",
                "Overstyring (Bagenden skrider / Snap oversteer)",
                "Ustabil under hård nedbremsning"
            ])
        
        with col_phase:
            phase = st.selectbox("Hvor i svinget sker det?", [
                "Sving-indgang (Turn-in / Trailbraking)",
                "Midt i svinget (Apex / Coasting)",
                "Udgang af svinget (På gassen)"
            ])

        st.divider()

        if issue != "Vælg problem...":
            st.subheader("🛠️ Foreslåede Setup Ændringer i iRacing:")
            
            if issue == "Understyring (Bilen vil ikke dreje ind)":
                if phase == "Sving-indgang (Turn-in / Trailbraking)":
                    st.success("1. **Flyt Brake Bias bagud** (-1% til -2%). Det hjælper bagenden med at rotere.\n2. **Blødere Front ARB** (Anti-Roll Bar).\n3. Øg negativ camber foran.")
                elif phase == "Midt i svinget (Apex / Coasting)":
                    st.success("1. **Blødere front fjedre**.\n2. **Sænk front ride height** (For at give aeroen mere greb foran).\n3. Tjek front dæktryk (Er de overophedede/for højt tryk?).")
                elif phase == "Udgang af svinget (På gassen)":
                    st.success("1. **Stivere Rear ARB**.\n2. Mindsk vinkel på hækvingen (hvis det er high-speed sving).\n3. Stivere fjedre bagtil.")

            elif issue == "Overstyring (Bagenden skrider / Snap oversteer)":
                if phase == "Sving-indgang (Turn-in / Trailbraking)":
                    st.success("1. **Flyt Brake Bias fremad** (+1% til +2%). Det stabiliserer bagenden under bremsning.\n2. **Stivere Front ARB**.\n3. Hæv front ride height lidt.")
                elif phase == "Midt i svinget (Apex / Coasting)":
                    st.success("1. **Stivere front fjedre**.\n2. Blødere Rear ARB.\n3. Mere negativ camber bagtil.")
                elif phase == "Udgang af svinget (På gassen)":
                    st.success("1. **Øg Traction Control (TC)**.\n2. Blødere bagfjedre for at absorbere poweren.\n3. Lavere dæktryk på baghjulene for at give en større kontaktflade.")

            elif issue == "Ustabil under hård nedbremsning":
                st.success("1. **Flyt Brake Bias meget fremad** (+2% eller mere). Bagbremserne låser før forbremserne.\n2. Mindsk den samlede bremsekraft (Brake Pressure) hvis du kører uden ABS.\n3. Blødere front fjedre, så bilen har lettere ved at sætte sig over forhjulene.")

else:
    st.error("Data mangler. Tjek GitHub.")
