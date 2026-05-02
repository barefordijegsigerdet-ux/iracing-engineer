import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io
import google.generativeai as genai

# --- KONFIGURATION & AI SETUP ---
st.set_page_config(page_title="iRacing Universal Coach", layout="wide")

# Hent API nøgle fra Streamlit Secrets
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    # Her indsætter vi din system instruction
    SYSTEM_INSTRUCTION = """
    You are a professional, data-driven Race Engineer and Driver Coach. Your goal is to identify time loss and optimize driver performance across any car and track combination in iRacing.
    
    Core Directives:
    1. Data Over Emotion: Prioritize telemetry over driver 'feel'.
    2. The 'Universal Fast' Principles: Analyze Braking, Corner Geometry, Minimum Speed (vMin), and Throttle Application.
    3. Corner Phase Analysis: Break corners into Entry, Mid-Corner, and Exit.
    4. Consistency: Identify 'spiky' inputs.
    5. Benchmarking: Compare User vs. Reference input timing and intensity.
    
    Style: Concise, technical, and honest. Separate Technical Errors from Input Issues.
    """
    model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_INSTRUCTION)
else:
    st.warning("⚠️ API nøgle ikke fundet. Tilføj GOOGLE_API_KEY i Streamlit Cloud Secrets for at aktivere AI Coach.")

# --- GITHUB CONFIG ---
USER = "barefordijegsigerdet-ux"
REPO = "iracing-engineer"
BRANCH = "main"

# --- FUNKTIONER ---
@st.cache_data
def load_data(name):
    if not name: return None
    url = f"https://raw.githubusercontent.com/{USER}/{REPO}/{BRANCH}/{name}"
    try:
        r = requests.get(url)
        if r.status_code != 200: return None
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip().lower() for c in df.columns]
        d_col = next((c for c in df.columns if 'dist' in c), None)
        if d_col:
            df = df.rename(columns={d_col: 'lapdistpct'})
            if df['lapdistpct'].max() > 1.1:
                df['lapdistpct'] = (df['lapdistpct'] - df['lapdistpct'].min()) / (df['lapdistpct'].max() - df['lapdistpct'].min())
            df = df.drop_duplicates('lapdistpct').sort_values('lapdistpct')
        return df
    except: return None

def get_ai_analysis(u_stats, r_stats, zone_name):
    prompt = f"""
    Analyse af {zone_name}:
    Bruger (Jonas): vMin={u_stats['vmin']} km/t, Peak Brake={u_stats['p_brake']}%, Throttle Pickup={u_stats['t_pickup']}% af zonen.
    Reference (Leeroy): vMin={r_stats['vmin']} km/t, Peak Brake={r_stats['p_brake']}%, Throttle Pickup={r_stats['t_pickup']}% af zonen.
    
    Forklar hvorfor Jonas taber tid, og giv præcis teknisk instruks.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI Coach er i øjeblikket optaget. Tjek din API nøgle."

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Data Setup")
    u_file = st.text_input("Din fil (CSV):", "jonas.csv")
    r_file = st.text_input("Reference fil (CSV):", "leeroy.csv")
    st.divider()
    sensitivity = st.slider("Coach Følsomhed (tidstab)", 0.05, 0.50, 0.10)
    t_len = st.number_input("Banelængde (m)", value=4252)

# --- ANALYSE LOGIK ---
df_u = load_data(u_file)
df_r = load_data(r_file)

if df_u is not None and df_r is not None:
    # Interpolation
    grid = np.linspace(0, 1, 2000)
    data = pd.DataFrame({'dist_pct': grid * 100})
    
    for k, col in [('speed','speed'), ('thr','throttle'), ('brk','brake'), ('tx','trackx'), ('ty','tracky')]:
        if col in df_u.columns: data[f'u_{k}'] = np.interp(grid, df_u['lapdistpct'], df_u[col])
        if col in df_r.columns: data[f'r_{k}'] = np.interp(grid, df_r['lapdistpct'], df_r[col])
    
    # Delta
    u_ms = np.maximum(data['u_speed']/3.6, 1.0)
    r_ms = np.maximum(data['r_speed']/3.6, 1.0)
    data['delta'] = np.cumsum(((1/2000)*t_len)/u_ms - ((1/2000)*t_len)/r_ms)
    data['delta_diff'] = data['delta'].diff().fillna(0)

    # --- UI ---
    st.title("🤖 Universal AI Coach")
    
    # Sektor analyse
    zones = []
    for i in range(0, 100, 5): # Tjekker hver 5% af banen
        mask = (data['dist_pct'] >= i) & (data['dist_pct'] < i+5)
        z = data[mask]
        loss = z['delta_diff'].sum()
        
        if loss > sensitivity:
            # Ekstraher stats til AI
            u_stats = {'vmin': round(z['u_speed'].min()*3.6, 1), 'p_brake': int(z['u_brk'].max()*100), 't_pickup': i}
            r_stats = {'vmin': round(z['r_speed'].min()*3.6, 1), 'p_brake': int(z['r_brk'].max()*100), 't_pickup': i}
            
            with st.expander(f"🚩 Tab i Zone {i}% - {i+5}% : {loss:.3f}s"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.write(f"**Din vMin:** {u_stats['vmin']} km/t")
                    st.write(f"**Ref vMin:** {r_stats['vmin']} km/t")
                with col2:
                    if st.button(f"Få AI Analyse af svinget", key=f"btn_{i}"):
                        with st.spinner("Coach analyserer..."):
                            advice = get_ai_analysis(u_stats, r_stats, f"Sektor ved {i}%")
                            st.info(advice)
                            
    # Track Map (Statisk Plotly)
    if 'u_tx' in data.columns:
        st.divider()
        st.subheader("📍 Bane Oversigt")
        map_fig = go.Figure()
        map_fig.add_trace(go.Scatter(x=data['u_tx'], y=data['u_ty'], line=dict(color='gray', width=1), hoverinfo='skip'))
        st.plotly_chart(map_fig, use_container_width=True)

else:
    st.info("👋 Hej! Jeg er din coach. Sørg for at dine CSV-filer ligger i dit GitHub repo og at det er sat til 'Public'.")
    st.write(f"Leder efter: `{USER}/{REPO}/main/`")
