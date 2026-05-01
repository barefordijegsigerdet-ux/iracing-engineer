import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Konfiguration af siden ---
st.set_page_config(page_title="Pro Sim Racing Coach", layout="wide")

def analyze_data(df_ref, df_user):
    """
    Interpolerer data og beregner delta-tid baseret på distancetrin.
    """
    # Vi bruger 2000 punkter for at få høj opløsning på omgangen
    common_dist = np.linspace(0, 1, 2000)
    
    # Interpolering af hastighed (konverteret til m/s for præcis delta-beregning)
    ref_speed_ms = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Speed']) / 3.6
    user_speed_ms = np.interp(common_dist, df_user['LapDistPct'], df_user['Speed']) / 3.6
    
    # Øvrige telemetri-kanaler
    ref_brake = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Brake'])
    user_brake = np.interp(common_dist, df_user['LapDistPct'], df_user['Brake'])
    ref_throttle = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Throttle'])
    user_throttle = np.interp(common_dist, df_user['LapDistPct'], df_user['Throttle'])
    user_steer = np.interp(common_dist, df_user['LapDistPct'], df_user['SteeringWheelAngle'])

    # Estimer banelængde (f.eks. Zandvoort er ca. 4252m)
    # I en fuld app kan dette hentes fra banens metadata
    track_length = 4252 
    dist_step = (1 / 2000) * track_length
    
    # Beregn delta tid (akkumuleret tidsforskel i sekunder)
    # Formel: tid = distance / hastighed
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
        "delta": delta_time
    }

# --- UI Layout ---
st.title("🏎️ Pro Sim Racing Coach")
st.markdown("Analysér din kørsel og få forslag til setup-rettelser.")

# Sidebar
st.sidebar.header("Konfiguration")
selected_car = st.sidebar.selectbox("Bil", ["Porsche 911 Cup (992.2)", "GT3 Class", "F4"])
selected_track = st.sidebar.selectbox("Bane", ["Circuit Zandvoort", "Spa-Francorchamps", "Monza"])
setup_mode = st.sidebar.radio("Setup Mode", ["Fixed", "Open"])

st.sidebar.divider()
ref_file = st.sidebar.file_uploader("Upload Reference CSV (Garage 61)", type=["csv"])
user_file = st.sidebar.file_uploader("Upload Din Session CSV (Garage 61)", type=["csv"])

if ref_file and user_file:
    # Indlæs data
    df_ref = pd.read_csv(ref_file)
    df_user = pd.read_csv(user_file)
    
    # Kør analyse
    data = analyze_data(df_ref, df_user)
    
    # Tabs
    tab_telemetry, tab_coach, tab_setup = st.tabs(["📊 Telemetri", "🤖 Driver Coach", "🔧 Setup Forslag"])

    with tab_telemetry:
        # Grafer med Plotly
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.03, 
                           subplot_titles=("Hastighed (km/t)", "Delta (Sekunder)", "Pedaler (%)"),
                           row_heights=[0.5, 0.25, 0.25])

        # Hastighed
        fig.add_trace(go.Scatter(x=data['dist'], y=data['ref_speed'], name="Reference Speed", line=dict(color='cyan')), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_speed'], name="Din Speed", line=dict(color='red')), row=1, col=1)

        # Delta
        delta_color = 'red' if data['delta'][-1] > 0 else 'green'
        fig.add_trace(go.Scatter(x=data['dist'], y=data['delta'], name="Delta Time", fill='tozeroy', line=dict(color='white')), row=2, col=1)

        # Pedaler
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_brake']*100, name="Din Brems", line=dict(color='indianred')), row=3, col=1)
        fig.add_trace(go.Scatter(x=data['dist'], y=data['user_throttle']*100, name="Din Gas", line=dict(color='lightgreen')), row=3, col=1)

        fig.update_layout(height=800, template="plotly_dark", hovermode="x unified", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab_coach:
        st.header("🤖 Din Personlige Driver Coach")
        
        # Beregn overordnede stats
        time_lost = data['delta'][-1]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total tidsforskel", f"{time_lost:.3f} s", delta=None)
            
            # Analyse af sving-entries (Eksempel logik)
            if data['user_brake'].mean() > data['ref_brake'].mean() * 1.15:
                st.error("⚠️ Over-bremsning: Du bruger bremsen for hårdt eller for længe i sving-entry. Prøv at fokusere på mere trail-braking.")
            
            # Analyse af exit
            if data['user_throttle'].mean() < data['ref_throttle'].mean() * 0.95:
                st.warning("⚠️ Langsom Exit: Du er senere på gassen end referencen. Prøv at rotere bilen færdig tidligere.")

        with col2:
            # Find største tidstab
            max_loss_idx = np.argmax(np.gradient(data['delta']))
            st.subheader("Fokusområde")
            st.write(f"Du taber mest tid omkring {data['dist'][max_loss_idx]:.1f}% af banen.")
            st.info("💡 Tip: Sammenlign din 'Minimum Speed' med referencen i dette område.")

    with tab_setup:
        st.header(f"🔧 Setup Analyse ({selected_car})")
        
        if setup_mode == "Fixed":
            st.info("Denne session er 'Fixed Setup'. Du kan ikke ændre bilens mekaniske opsætning, men du kan optimere din kørsel.")
        else:
            # Simpel logik baseret på ratudslag vs hastighed (Understyringstest)
            avg_steer = np.abs(data['user_steer']).mean()
            
            col_setup1, col_setup2 = st.columns(2)
            
            with col_setup1:
                st.subheader("Balance Analyse")
                if avg_steer > 0.15:
                    st.error("Tendens fundet: Understyring")
                    st.write("Du bruger meget ratudslag for at få bilen rundt.")
                    st.markdown("### Forslag til rettelser:")
                    st.write("1. Sænk Front ARB (Anti-Roll Bar)")
                    st.write("2. Blødgør de forreste fjedre")
                    st.write("3. Øg din Rear Ride Height for mere 'rake'")
                else:
                    st.success("Bilens balance virker neutral og effektiv.")

            with col_setup2:
                st.subheader("Dæktryk & Temp")
                st.write("Tjek din 'Session CSV' for track temps.")
                # Her kan vi senere trække data fra din Offline Testing CSV
                st.write("Optimale dæktryk for Cup-bilen er typisk ~150 kPa (21.5-22 psi) varm.")

else:
    st.info("👋 Velkommen! Start med at uploade dine CSV-filer fra Garage 61 i venstre side.")
    st.image("https://images.unsplash.com/photo-1547394765-185e1e68f34e?auto=format&fit=crop&q=80&w=1000", caption="Klar til at optimere din laptime?")

