import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import io
import google.generativeai as genai

# --- 1. SETUP & AI CONFIGURATION ---
st.set_page_config(page_title="iRacing Universal Coach", layout="wide")

# Din professionelle System Instruction
SYSTEM_INSTRUCTION = """
You are a professional, data-driven Race Engineer and Driver Coach. Your goal is to identify time loss and optimize driver performance across any car and track combination in iRacing.

Core Directives:
1. Data Over Emotion: Prioritize telemetry over driver 'feel'.
2. The 'Universal Fast' Principles: Analyze Braking, Corner Geometry, Minimum Speed (vMin), and Throttle Application.
3. Corner Phase Analysis: Break corners into Entry, Mid-Corner, and Exit.
4. Consistency: Identify 'spiky' inputs.
5. Benchmarking: Compare User vs. Reference input timing and intensity.

Style: Concise, technical, and honest. Separate Technical Errors from Input Issues. Use "Less brake, more roll" philosophy for high-speed corners.
"""

# Initialisering med Gemini 3 / Latest Alias
if "GOOGLE_API_KEY" in st.secrets:
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        # Vi bruger 'gemini-flash-latest' for at ramme Gemini 3 Flash automatisk
        model = genai.GenerativeModel('gemini-flash-latest', system_instruction=SYSTEM_INSTRUCTION)
    except Exception as e:
        st.error(f"Fejl ved konfiguration af AI: {e}")
        model = None
else:
    st.warning("⚠️ API nøgle (GOOGLE_API_KEY) ikke fundet i Secrets.")
    model = None

# --- 2. GITHUB CONFIG ---
USER = "barefordijegsigerdet-ux"
REPO = "iracing-engineer"
BRANCH = "main"

# --- 3. FUNKTIONER ---
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
    if model is None:
        return "AI Coach er ikke tilgængelig."
        
    prompt = f"""
    Analyse: Jonas vs. Leeroy
    Sektor: {zone_name}
    
    Data:
    Jonas: vMin={u_stats['vmin']} km/t, Peak Brake={u_stats['p_brake']}%, Throttle Start={u_stats['t_pickup']}%
    Leeroy (Ref): vMin={r_stats['vmin']} km/t, Peak Brake={r_stats['p_brake']}%, Throttle Start={r_stats['t_pickup']}%
    
    Lever en analyse opdelt i: 1. Tekniske Fejl, 2. Input Problemer og 3. Tekniske Instrukser.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Fejl fra Gemini 3: {str(e)}"

# --- 4. UI & LOGIK ---
with st.sidebar:
    st.header("📂 Data Setup")
    u_file = st.text_input("Din fil (CSV):", "jonas.csv")
    r_file = st.text_input("Reference fil (CSV):", "leeroy.csv")
    st.divider()
    sensitivity = st.slider("Coach Følsomhed", 0.05, 0.50, 0.10)
    t_len = st.number_input("Banelængde (m)", value=4252)

df_u = load_data(u_file)
df_r = load_data(r_file)

if df_u is not None and df_r is not None:
    st.title("🤖 Universal AI Coach (Gemini 3 Edition)")
    
    grid = np.linspace(0, 1, 2000)
    data = pd.DataFrame({'dist_pct': grid * 100})
    
    for k, col in [('speed','speed'), ('thr','throttle'), ('brk','brake'), ('tx','trackx'), ('ty','tracky')]:
        if col in df_u.columns: data[f'u_{k}'] = np.interp(grid, df_u['lapdistpct'], df_u[col])
        if col in df_r.columns: data[f'r_{k}'] = np.interp(grid, df_r['lapdistpct'], df_r[col])
    
    u_ms = np.maximum(data['u_speed']/3.6, 1.0)
    r_ms = np.maximum(data['r_speed']/3.6, 1.0)
    data['delta'] = np.cumsum(((1/2000)*t_len)/u_ms - ((1/2000)*t_len)/r_ms)
    data['delta_diff'] = data['delta'].diff().fillna(0)

    for i in range(0, 100, 5):
        mask = (data['dist_pct'] >= i) & (data['dist_pct'] < i+5)
        z = data[mask]
        loss = z['delta_diff'].sum()
        
        if loss > sensitivity:
            u_s = {'vmin': round(z['u_speed'].min()*3.6, 1), 'p_brake': int(z['u_brk'].max()*100), 't_pickup': i}
            r_s = {'vmin': round(z['r_speed'].min()*3.6, 1), 'p_brake': int(z['r_brk'].max()*100), 't_pickup': i}
            
            with st.expander(f"🚩 Tab i Zone {i}% - {i+5}% : {loss:.3f}s"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.metric("Din vMin", f"{u_s['vmin']} km/t")
                    st.metric("Ref vMin", f"{r_s['vmin']} km/t", delta=round(u_s['vmin'] - r_s['vmin'], 1))
                with c2:
                    if st.button(f"Kør Analyse", key=f"btn_{i}"):
                        with st.spinner("Gemini 3 tænker..."):
                            st.markdown(get_ai_analysis(u_s, r_s, f"Zone {i}%"))

    if 'u_tx' in data.columns:
        st.divider()
        map_fig = go.Figure()
        map_fig.add_trace(go.Scatter(x=data['u_tx'], y=data['u_ty'], line=dict(color='white', width=2)))
        map_fig.update_layout(template="plotly_dark", height=400, xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
        st.plotly_chart(map_fig, use_container_width=True)
else:
    st.info("Klar til data. Tjek at jonas.csv og leeroy.csv ligger i dit repo.")
