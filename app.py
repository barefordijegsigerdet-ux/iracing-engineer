import streamlit as st
import pandas as pd
import numpy as np
import requests
import io

# --- SETUP ---
st.set_page_config(page_title="iRacing AI Coach", layout="wide")
USER, REPO, BRANCH = "barefordijegsigerdet-ux", "iracing-engineer", "main"

st.title("🤖 Din Personlige iRacing Coach")
st.info("Jeg analyserer dine filer og finder de steder, hvor du taber mest tid til Leeroy.")

# --- DATA INDLÆSNING ---
@st.cache_data
def load_data(name):
    url = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{name}"
    try:
        r = requests.get(url)
        if r.status_code != 200: return None
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip().lower() for c in df.columns]
        # Find dist-kolonne
        d_col = next((c for c in df.columns if 'dist' in c), None)
        if d_col:
            df = df.rename(columns={d_col: 'lapdistpct'})
            if df['lapdistpct'].max() > 1.1:
                df['lapdistpct'] = (df['lapdistpct'] - df['lapdistpct'].min()) / (df['lapdistpct'].max() - df['lapdistpct'].min())
        return df
    except: return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏁 Analyse Setup")
    u_file = st.text_input("Din fil (Jonas):", "Jonas.csv")
    r_file = st.text_input("Reference (Leeroy):", "Leeroy.csv")
    st.divider()
    sensitivity = st.slider("Coach Følsomhed (s)", 0.05, 0.50, 0.10)

df_u = load_data(u_file)
df_r = load_data(r_file)

if df_u is not None and df_r is not None:
    # Interpolation til præcis analyse
    grid = np.linspace(0, 1, 2000)
    data = pd.DataFrame({'dist_pct': grid * 100})
    
    for k, col in [('speed','speed'), ('thr','throttle'), ('brk','brake')]:
        if col in df_u.columns: data[f'u_{k}'] = np.interp(grid, df_u['lapdistpct'], df_u[col])
        if col in df_r.columns: data[f'r_{k}'] = np.interp(grid, df_r['lapdistpct'], df_r[col])
    
    # Beregn Delta
    t_len = 4252 # Standard Zandvoort, kan gøres dynamisk
    u_ms, r_ms = np.maximum(data['u_speed']/3.6, 1.0), np.maximum(data['r_speed']/3.6, 1.0)
    data['delta'] = np.cumsum(((1/2000)*t_len)/u_ms - ((1/2000)*t_len)/r_ms)
    
    # --- COACH LOGIK ---
    st.subheader("📋 Sektor Analyse")
    
    # Find områder med størst tidstab
    data['delta_change'] = data['delta'].diff().fillna(0)
    
    # Gruppér tab i zoner (hver 5% af banen)
    zones = []
    for i in range(0, 100, 5):
        mask = (data['dist_pct'] >= i) & (data['dist_pct'] < i+5)
        zone_data = data[mask]
        time_lost = zone_data['delta_change'].sum()
        
        if time_lost > sensitivity:
            # Analysér hvorfor
            avg_u_thr = zone_data['u_thr'].mean()
            avg_r_thr = zone_data['r_thr'].mean()
            max_u_brk = zone_data['u_brk'].max()
            max_r_brk = zone_data['r_brk'].max()
            
            reason = "Generelt lavere fart"
            if avg_u_thr < avg_r_thr - 0.1: reason = "Du tøver på gassen (Exit)"
            if max_u_brk > max_r_brk + 0.1: reason = "Du bremser for hårdt/overshoot"
            
            zones.append({
                "Zone": f"{i}% - {i+5}%",
                "Tab (sek)": round(time_lost, 3),
                "Coach Råd": reason
            })

    if zones:
        st.table(pd.DataFrame(zones))
    else:
        st.success("Ingen store tidstab fundet! Du kører tæt på referencen.")

    # --- TOP 3 CRITICAL ISSUES ---
    st.divider()
    st.subheader("🎯 Top 3 ting du skal fokusere på")
    
    # 1. Exit Speed tjek
    if data['u_speed'].mean() < data['r_speed'].mean() - 2:
        st.error("**1. Corner Exit:** Din gennemsnitlige fart er markant lavere. Fokusér på at få bilen drejet færdig tidligere, så du kan gå på 100% gas før Leeroy.")
    
    # 2. Bremsestabilitet
    if data['u_brk'].std() > data['r_brk'].std() * 1.2:
        st.warning("**2. Bremse-input:** Dine bremsetryk er meget urolige. Arbejd på din 'Trail Braking' – vær mere progressiv, når du slipper bremsen ind i svinget.")

    # 3. Delta trend
    total_loss = data['delta'].iloc[-1]
    st.metric("Total tid efter Leeroy", f"{total_loss:.3f} s")

else:
    st.warning("Venter på korrekte .csv filer fra GitHub for at starte coachingen...")
