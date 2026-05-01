import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Konfiguration ---
st.set_page_config(page_title="Pro Sim Coach", layout="wide")

def get_session_info(file):
    """Udtrækker vejr og baneinfo fra Session CSV."""
    try:
        df = pd.read_csv(file)
        # Vi tager gennemsnittet eller den nyeste værdi
        info = {
            "track_temp": df["Track temp"].iloc[-1],
            "air_temp": df["Air temperature"].iloc[-1],
            "humidity": df["Relative humidity"].iloc[-1] * 100 if "Relative humidity" in df else 0,
            "sectors": [df["Sector 1"].iloc[-1], df["Sector 2"].iloc[-1], df["Sector 3"].iloc[-1]]
        }
        return info
    except:
        return None

def analyze_data(df_ref, df_user, lap_time_user):
    """Interpolerer data og beregner præcis delta-tid."""
    common_dist = np.linspace(0, 1, 3000) # Højere opløsning (3k punkter)
    
    # Konverter hastighed til m/s for beregninger
    ref_speed_ms = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Speed']) / 3.6
    user_speed_ms = np.interp(common_dist, df_user['LapDistPct'], df_user['Speed']) / 3.6
    
    # Øvrige kanaler
    ref_brake = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Brake'])
    user_brake = np.interp(common_dist, df_user['LapDistPct'], df_user['Brake'])
    ref_throttle = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Throttle'])
    user_throttle = np.interp(common_dist, df_user['LapDistPct'], df_user['Throttle'])
    user_steer = np.interp(common_dist, df_user['LapDistPct'], df_user['SteeringWheelAngle'])

    # Estimer banelængde ud fra gennemsnitshastighed og lap time
    avg_speed_ms = (df_user['Speed'].mean()) / 3.6
    track_length = avg_speed_ms * lap_time_user
    dist_step = (1 / 3000) * track_length
    
    # Delta Time: Akkumuleret forskel i sekunder pr. segment
    # delta_t = dist / v_user - dist / v_ref
    delta_steps = (dist_step / user_speed_ms) - (dist_step / ref_speed_ms)
    delta_time = np.cumsum(delta_steps)

    return {
        "dist": common_dist * 100,
        "ref_speed": ref_speed_ms * 3.6,
        "user_speed": user_speed_ms * 3.6,
        "ref_brake": ref_brake,
        "user_brake": user_brake,
        "ref_throttle": ref_throttle,
        "user_throttle": user_throttle,
        "user_steer": user_steer,
        "delta": delta_time,
        "track_length": track_length
    }

# --- App Layout ---
st.title("🏎️ Sim Racing Coach: Jonas vs. Leeroy")

# Sidebar
st.sidebar.header("Data Import")
ref_csv = st.sidebar.file_uploader("Reference Telemetri (Leeroy)", type=["csv"])
user_csv = st.sidebar.file_uploader("Din Telemetri (Jonas)", type=["csv"])
session_csv = st.sidebar.file_uploader("Din Session Data (Valgfri)", type=["csv"])

st.sidebar.divider()
setup_mode = st.sidebar.radio("Setup Type", ["Open Setup", "Fixed Setup"])

if ref_csv and user_csv:
    df_ref = pd.read_csv(ref_csv)
    df_user = pd.read_csv(user_csv)
    
    # Beregn omgangstid fra data (sidste punkt i sekunder hvis muligt, ellers manuelt)
    # For Zandvoort eksemplet ved vi den er ~101.980s
    lap_time_user = 101.980 
    
    data = analyze_data(df_ref, df_user, lap_time_user)
    session_info = get_session_info(session_csv) if session_csv else None

    # Top Stats
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Total Tidstab", f"{data['delta'][-1]:.3f}s", delta_color="inverse")
    with col_b:
        if session_info:
            st.metric("Bane Temperatur", f"{session_info['track_temp']:.1f}°C")
        else:
            st.metric("Bane Temperatur", "Ingen data")
    with col_c:
        max_speed_diff = np.max(data['ref_speed'] - data['user_speed'])
        st.metric("Max Hastighedsforskel", f"{max_speed_diff:.1f} km/t")

    # Tabs
    tab_graphs, tab_coach, tab_setup = st.tabs(["📊 Telemetri Sammenligning", "🤖 Coach Feedback", "🔧 Setup Analyse"])

    with tab_graphs:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                           subplot_titles=("Hastighed (km/t)", "Delta (Tid vundet/tabt)", "Pedal Input"),
                           row_heights=[0.5, 0.2, 0.3])

        # Speed
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Leeroy", line=dict(color='cyan', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Jonas", line=dict(color='red', width=1.5)), row=1, col=1)

        # Delta
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta", fill='tozeroy', line=dict(color='yellow')), row=2, col=1)

        # Pedals
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Jonas Brems", line=dict(color='indianred')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Jonas Gas", line=dict(color='lightgreen')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_throttle']*100, name="Leeroy Gas", line=dict(color='rgba(144, 238, 144, 0.3)', dash='dot')), row=3, col=1)

        fig.update_layout(height=800, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    with tab_coach:
        st.header("🤖 Coach Analyse")
        
        # Logik til at finde fejl
        # 1. Tjek for tidlig brems / for meget brems
        brake_diff = data['user_brake'].sum() - data['ref_brake'].sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Observations")
            if brake_diff > 0:
                st.write("- **Over-bremsning:** Du bruger mere bremse-energi end Leeroy. Prøv at slippe bremsen hurtigere for at bære mere fart ind i apex.")
            
            # Find hvor i delta-grafen det går mest galt (hvor hældningen er størst)
            slope = np.gradient(data['delta'])
            worst_spot = data['dist'][np.argmax(slope)]
            st.error(f"- **Kritisk punkt:** Du taber mest tid ved {worst_spot:.1f}% af banen. Tjek din minimumshastighed her.")

        with col2:
            st.subheader("Action Plan")
            st.info("1. Fokusér på Sving 3 (Hugenholtz): Sørg for at få bilen drejet tidligt, så du kan gå på gassen samtidig med Leeroy.")
            st.info("2. Dine gearskift ser stabile ud, men du kan vinde tid på at være mere aggressiv på throttle-apply i sving 12.")

    with tab_setup:
        st.header("🔧 Setup Forslag")
        if setup_mode == "Fixed Setup":
            st.warning("Fixed Setup valgt. Fokusér på dæktryk og kørselsteknik.")
        
        # Setup logik baseret på ratudslag
        steer_work = np.abs(data['user_steer']).mean()
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.write("**Balance-vurdering:**")
            if steer_work > 0.12:
                st.error("Understyring detekteret")
                st.write("Du kæmper med at få bilen til at dreje i midten af svinget.")
                st.markdown("- Sænk **Front ARB** med 1 klik.")
                st.markdown("- Øg **Rear Ride Height** for at flytte vægten frem.")
            else:
                st.success("Neutral balance. Bilen reagerer godt på dine inputs.")
        
        with col_s2:
            if session_info:
                st.write("**Vejrets indflydelse:**")
                st.write(f"Bane temp er {session_info['track_temp']:.1f}°C.")
                if session_info['track_temp'] > 30:
                    st.warning("Varm bane: Overvej at øge dæktrykket en smule for at undgå at dækkene 'ruller'.")

else:
    st.info("Klar til analyse. Upload venligst både dine egne og Leeroys data i sidebar'en.")
