import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Pro Sim Coach", layout="wide")

st.title("🏎️ Pro Sim Racing Coach v2.0")

# --- Sidebar ---
st.sidebar.header("Konfiguration")
car = st.sidebar.selectbox("Vælg bil", ["Porsche 911 Cup (992.2)", "GT3 Class", "F4"])
track = st.sidebar.selectbox("Bane", ["Zandvoort", "Spa", "Monza"])
setup_type = st.sidebar.radio("Setup Type", ["Fixed", "Open"])

st.sidebar.divider()
ref_file = st.sidebar.file_uploader("Upload Reference CSV", type=["csv"])
user_file = st.sidebar.file_uploader("Upload Din CSV", type=["csv"])

def analyze_data(df_ref, df_user):
    # Interpolering for at sikre at vi sammenligner de samme punkter på banen
    common_dist = np.linspace(0, 1, 2000) # 2000 punkter rundt på banen
    
    ref_speed = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Speed'])
    user_speed = np.interp(common_dist, df_user['LapDistPct'], df_user['Speed'])
    
    ref_brake = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Brake'])
    user_brake = np.interp(common_dist, df_user['LapDistPct'], df_user['Brake'])

    ref_throttle = np.interp(common_dist, df_ref['LapDistPct'], df_ref['Throttle'])
    user_throttle = np.interp(common_dist, df_user['LapDistPct'], df_user['Throttle'])

    # Delta Time Beregning (simpel version: tid = distance / fart)
    # Vi antager banelængde er ens. Delta viser akkumuleret tidsforskel.
    delta_v = (1/user_speed) - (1/ref_speed)
    delta_time = np.cumsum(delta_v) 
    delta_time = delta_time - delta_time[0] # Nulstil start

    return common_dist, ref_speed, user_speed, ref_brake, user_brake, ref_throttle, user_throttle, delta_time

if ref_file and user_file:
    df_ref = pd.read_csv(ref_file)
    df_user = pd.read_csv(user_file)
    
    dist, r_spd, u_spd, r_brk, u_brk, r_thr, u_thr, delta = analyze_data(df_ref, df_user)

    tab1, tab2 = st.tabs(["📊 Telemetri & Coach", "🔧 Setup Tab"])

    with tab1:
        # Opret grafer (Speed, Throttle/Brake, Delta)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, 
                           subplot_titles=("Hastighed (km/t)", "Delta Time (Sekunder)", "Pedaler"),
                           row_heights=[0.5, 0.25, 0.25])

        # Speed
        fig.add_trace(go.Scatter(x=dist, y=r_spd, name="Ref Speed", line=dict(color='blue')), row=1, col=1)
        fig.add_trace(go.Scatter(x=dist, y=u_spd, name="Din Speed", line=dict(color='red')), row=1, col=1)

        # Delta
        fig.add_trace(go.Scatter(x=dist, y=delta, name="Delta", fill='tozeroy', line=dict(color='white')), row=2, col=1)

        # Pedals
        fig.add_trace(go.Scatter(x=dist, y=u_brk, name="Din Brems", line=dict(color='indianred', dash='dash')), row=3, col=1)
        fig.add_trace(go.Scatter(x=dist, y=u_thr, name="Din Gas", line=dict(color='lightgreen')), row=3, col=1)

        fig.update_layout(height=800, template="plotly_dark", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # DRIVER COACH LOGIK
        st.header("🤖 Driver Coach Analyse")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Hvor taber du tid?")
            max_delta_idx = np.argmax(delta)
            st.warning(f"Du taber mest tid ved {dist[max_delta_idx]*100:.1f}% af banen. Her er din fart {r_spd[max_delta_idx] - u_spd[max_delta_idx]:.1f} km/t lavere end referencen.")
            
            # Tjek brems
            if u_brk.mean() > r_brk.mean() * 1.2:
                st.info("💡 Tip: Du "over-bremser" generelt. Prøv at rulle mere fart ind i svingene (Trail braking).")

        with col2:
            st.subheader("Styrker")
            if u_spd.max() >= r_spd.max() * 0.98:
                st.success("✅ Din topfart er på niveau med referencen. Dine gearskift og exit ser gode ud.")

    with tab2:
        st.header("🔧 Setup Justeringer")
        if setup_type == "Fixed":
            st.write("Dette er en fixed session. Ingen setup ændringer mulige.")
        else:
            st.write(f"Analyse af {car} på {track}:")
            
            # Eksempel på setup logik (baseret på telemetri tendenser)
            avg_steer = df_user['SteeringWheelAngle'].abs().mean()
            if avg_steer > 0.2: # Simpelt eksempel: meget ratudslag kan indikere understyring
                st.error("Tendens: Understyring fundet")
                st.markdown("- **Forslag:** Blødgør Front ARB (Anti-Roll Bar)")
                st.markdown("- **Forslag:** Øg Rear Ride Height (+1mm)")
            else:
                st.success("Bilens balance ser stabil ud.")

else:
    st.info("Upload CSV-filer for at starte analysen.")
