"""
Garage 61 · Telemetry Coach
CSV format: Speed, LapDistPct, Brake, Throttle, RPM,
            SteeringWheelAngle, Gear, LatAccel, LongAccel, ABSActive, …
"""

import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime, io

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Garage 61 | Telemetry Coach",
    page_icon="🏎️", layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html,body,[class*="css"]{background:#0D0D0D;color:#F0F0F0;font-family:'Inter',sans-serif}
.stApp{background:#0D0D0D}
section[data-testid="stSidebar"]{background:#111;border-right:1px solid #1e1e1e}
.block-container{padding-top:1.1rem}
h1{color:#FF6B00;letter-spacing:.04em}
.stTabs [data-baseweb="tab-list"]{gap:5px;background:#161616;border-radius:8px;padding:4px}
.stTabs [data-baseweb="tab"]{background:transparent;color:#666;border-radius:6px;
  padding:8px 18px;font-weight:600;font-size:.84rem}
.stTabs [aria-selected="true"]{background:#FF6B00!important;color:#fff!important}
.stButton>button{background:#FF6B00;color:#fff;border:none;border-radius:6px;
  font-weight:700;padding:10px 24px;width:100%}
.stButton>button:hover{background:#e05e00}
div[data-testid="metric-container"]{background:#1A1A1A;border:1px solid #252525;
  border-left:3px solid #FF6B00;border-radius:6px;padding:12px 16px}
.card{background:#1A1A1A;border:1px solid #222;border-left:3px solid #FF6B00;
  border-radius:6px;padding:12px 16px;margin:8px 0;font-size:.86rem;color:#bbb}
.learn-card{background:#1A1A1A;border:1px solid #222;border-radius:8px;
  padding:16px 20px;margin:10px 0}
.learn-card h4{color:#FF6B00;margin:0 0 8px;font-size:.95rem}
.learn-card p{color:#999;font-size:.84rem;margin:0;line-height:1.65}
</style>
""", unsafe_allow_html=True)

# ── Colours ───────────────────────────────────────────────────────────────────
C_SPEED    = "#4FC3F7"
C_THROTTLE = "#00C48C"
C_BRAKE    = "#FF3B3B"
C_ORANGE   = "#FF6B00"
C_YELLOW   = "#FFD600"
C_PURPLE   = "#CE93D8"
C_GREEN    = "#00C48C"

LAYOUT_BASE = dict(
    paper_bgcolor="#0D0D0D", plot_bgcolor="#111",
    font=dict(color="#F0F0F0", family="Inter"),
    legend=dict(bgcolor="#0D0D0D", bordercolor="#333", borderwidth=1),
    margin=dict(l=50, r=20, t=40, b=40),
)

# ── AI prompts ────────────────────────────────────────────────────────────────
LEVEL = {
    "🟢 Begynder": (
        "Brugeren har aldrig læst telemetri før. Forklar ALT i hverdagsord. "
        "Ingen fagtermer uden forklaring. Brug analogier. Vær opmuntrende og positiv."
    ),
    "🟡 Mellemniveau": (
        "Brugeren forstår grundlæggende telemetri. Du kan bruge termer som trail-braking, "
        "apex og throttle ramp, men forklar dem kort første gang."
    ),
    "🔴 Avanceret": (
        "Brugeren er erfaren. Vær teknisk og præcis. Brug termer som overlap-zone, "
        "brake pressure curve og throttle ramp-rate uden forklaring."
    ),
}
FOCUS = {
    "🔍 Alt":         "Analysér alle aspekter af kørstilen.",
    "🛑 Bremse":      "Fokuser primært på bremseteknik: bremsepunkt, tryk og frigivelse.",
    "⚡ Gas":         "Fokuser primært på gasgivning: tidspunkt for indsats og ramp-up.",
    "📈 Speed trace": "Fokuser på minimum-hastighed i sving og exit-hastighed.",
}

# ── CSV loader ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_csv(data: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(data))
    for col in ["Throttle","Brake","Speed","RPM","Gear","LapDistPct",
                "LatAccel","LongAccel","SteeringWheelAngle"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["ThrottlePct"] = df["Throttle"] * 100
    df["BrakePct"]    = df["Brake"]    * 100
    # iRacing exports Speed in m/s → convert to km/h
    df["Speed"]       = df["Speed"] * 3.6
    # Accelerations in m/s² → convert to G
    if "LatAccel" in df.columns:
        df["LatAccel"]  = df["LatAccel"]  / 9.81
    if "LongAccel" in df.columns:
        df["LongAccel"] = df["LongAccel"] / 9.81
    if "ABSActive" in df.columns:
        df["ABSActive"] = df["ABSActive"].astype(str).str.lower() == "true"
    return df.sort_values("LapDistPct").reset_index(drop=True)


def resample_to(df: pd.DataFrame, n: int = 2000) -> pd.DataFrame:
    dist = np.linspace(df["LapDistPct"].min(), df["LapDistPct"].max(), n)
    out  = pd.DataFrame({"LapDistPct": dist})
    for col in ["Speed","ThrottlePct","BrakePct","Gear","RPM","LatAccel","LongAccel"]:
        if col in df.columns:
            out[col] = np.interp(dist, df["LapDistPct"].values, df[col].values)
    return out

# ── Metrics ───────────────────────────────────────────────────────────────────
def compute_metrics(df: pd.DataFrame) -> dict:
    m   = {}
    spd = df["Speed"]
    thr = df["ThrottlePct"]
    brk = df["BrakePct"]

    m["speed_max"]         = round(spd.max(), 1)
    m["speed_mean"]        = round(spd.mean(), 1)
    low = spd < spd.max() * 0.65
    m["corner_speed_min"]  = round(spd[low].min(),  1) if low.any() else 0
    m["corner_speed_mean"] = round(spd[low].mean(), 1) if low.any() else 0

    m["throttle_full_pct"]    = round((thr >= 95).mean() * 100, 1)
    m["throttle_zero_pct"]    = round((thr <= 5).mean()  * 100, 1)
    m["throttle_mean"]        = round(thr.mean(), 1)

    m["brake_max"]            = round(brk.max(), 1)
    m["brake_active_pct"]     = round((brk > 5).mean() * 100, 1)
    m["brake_mean_active"]    = round(brk[brk > 5].mean(), 1) if (brk > 5).any() else 0

    m["overlap_pct"]          = round(((thr > 10) & (brk > 10)).mean() * 100, 1)
    m["gear_max"]             = int(df["Gear"].max())
    m["gear_changes"]         = int(df["Gear"].diff().abs().fillna(0).astype(bool).sum())

    if "ABSActive" in df.columns:
        m["abs_interventions"] = int(df["ABSActive"].astype(int).diff().clip(lower=0).sum())
    else:
        m["abs_interventions"] = "N/A"

    m["lat_g_max"]  = round(df["LatAccel"].abs().max(), 2)
    m["long_g_min"] = round(df["LongAccel"].min(), 2)
    return m


def metrics_text(m: dict, label: str = "") -> str:
    return "\n".join([
        f"=== Nøgletal {label} ===",
        f"Tophastighed: {m['speed_max']} km/h | Snit: {m['speed_mean']} km/h",
        f"Min. svinghastighed: {m['corner_speed_min']} km/h | Snit i sving: {m['corner_speed_mean']} km/h",
        f"Gas — fuld gas: {m['throttle_full_pct']}% af runden | nul gas: {m['throttle_zero_pct']}% | snit: {m['throttle_mean']}%",
        f"Bremse — max tryk: {m['brake_max']}% | aktiv: {m['brake_active_pct']}% | snit under bremse: {m['brake_mean_active']}%",
        f"Gas+bremse overlap: {m['overlap_pct']}% af runden",
        f"ABS-indgreb: {m['abs_interventions']}",
        f"Max lateral G: {m['lat_g_max']} | Hårdest bremse-G: {m['long_g_min']}",
        f"Gear skift: {m['gear_changes']} | Højeste gear: {m['gear_max']}",
    ])

# ── Charts ────────────────────────────────────────────────────────────────────
def main_chart(df: pd.DataFrame, title: str = "") -> go.Figure:
    x   = df["LapDistPct"].values * 100
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.40, 0.25, 0.15, 0.20],
        vertical_spacing=0.03,
        subplot_titles=["Speed (km/h)", "Throttle & Brake (%)", "Gear", "G-kræfter"],
    )
    fig.add_trace(go.Scatter(x=x, y=df["Speed"], name="Speed",
        line=dict(color=C_SPEED, width=1.5)), row=1, col=1)

    if "ABSActive" in df.columns and df["ABSActive"].any():
        abs_x = df.loc[df["ABSActive"], "LapDistPct"].values * 100
        abs_y = df.loc[df["ABSActive"], "Speed"].values
        fig.add_trace(go.Scatter(x=abs_x, y=abs_y, mode="markers",
            name="ABS aktiv", marker=dict(color=C_YELLOW, size=4)), row=1, col=1)

    fig.add_trace(go.Scatter(x=x, y=df["ThrottlePct"], name="Gas",
        line=dict(color=C_THROTTLE, width=1.3),
        fill="tozeroy", fillcolor="rgba(0,196,140,0.12)"), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=df["BrakePct"], name="Bremse",
        line=dict(color=C_BRAKE, width=1.3),
        fill="tozeroy", fillcolor="rgba(255,59,59,0.12)"), row=2, col=1)

    fig.add_trace(go.Scatter(x=x, y=df["Gear"], name="Gear",
        line=dict(color=C_ORANGE, width=1.5)), row=3, col=1)

    fig.add_trace(go.Scatter(x=x, y=df["LongAccel"], name="Long-G",
        line=dict(color=C_PURPLE, width=1)), row=4, col=1)
    fig.add_trace(go.Scatter(x=x, y=df["LatAccel"], name="Lat-G",
        line=dict(color=C_YELLOW, width=1)), row=4, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#444", row=4, col=1)

    layout = dict(**LAYOUT_BASE)
    layout["title"]  = dict(text=title, font=dict(color=C_ORANGE, size=14))
    layout["height"] = 700
    fig.update_layout(**layout)
    for r in range(1, 5):
        fig.update_xaxes(gridcolor="#1e1e1e", zerolinecolor="#333", row=r, col=1)
        fig.update_yaxes(gridcolor="#1e1e1e", zerolinecolor="#333", row=r, col=1)
    fig.update_xaxes(title_text="Rundeposition (%)", row=4, col=1)
    return fig


def compare_chart(dfa: pd.DataFrame, dfb: pd.DataFrame,
                  la: str, lb: str) -> go.Figure:
    ra = resample_to(dfa)
    rb = resample_to(dfb)
    x  = ra["LapDistPct"].values * 100

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.45, 0.30, 0.25],
        vertical_spacing=0.04,
        subplot_titles=[
            "Speed overlay (km/h)",
            "Throttle & Brake (%)",
            f"Δ Speed: {lb} − {la}  (positivt = {lb} hurtigere)",
        ],
    )
    fig.add_trace(go.Scatter(x=x, y=ra["Speed"], name=f"Speed — {la}",
        line=dict(color=C_SPEED, width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=rb["Speed"], name=f"Speed — {lb}",
        line=dict(color=C_ORANGE, width=1.5, dash="dash")), row=1, col=1)

    fig.add_trace(go.Scatter(x=x, y=ra["ThrottlePct"], name=f"Gas — {la}",
        line=dict(color=C_THROTTLE, width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=rb["ThrottlePct"], name=f"Gas — {lb}",
        line=dict(color=C_THROTTLE, width=1.2, dash="dash")), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=ra["BrakePct"], name=f"Bremse — {la}",
        line=dict(color=C_BRAKE, width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=rb["BrakePct"], name=f"Bremse — {lb}",
        line=dict(color=C_BRAKE, width=1.2, dash="dash")), row=2, col=1)

    delta  = rb["Speed"].values - ra["Speed"].values
    colors = [C_GREEN if d >= 0 else C_BRAKE for d in delta]
    fig.add_trace(go.Bar(x=x, y=delta, name="Δ Speed",
        marker_color=colors, marker_line_width=0), row=3, col=1)
    fig.add_hline(y=0, line_color="#444", row=3, col=1)

    layout = dict(**LAYOUT_BASE)
    layout["height"] = 750
    fig.update_layout(**layout)
    for r in range(1, 4):
        fig.update_xaxes(gridcolor="#1e1e1e", zerolinecolor="#333", row=r, col=1)
        fig.update_yaxes(gridcolor="#1e1e1e", zerolinecolor="#333", row=r, col=1)
    fig.update_xaxes(title_text="Rundeposition (%)", row=3, col=1)
    return fig

# ── Claude ────────────────────────────────────────────────────────────────────
def call_gemini(system: str, user: str) -> str:
    try:
        key = st.secrets["GEMINI_API_KEY"]
    except KeyError:
        st.error("❌ Mangler 'GEMINI_API_KEY' i Streamlit Secrets!")
        st.stop()
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        model_name="gemini-3.1-flash-lite",
        system_instruction=system,
    )
    resp = model.generate_content(user)
    return resp.text

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏎️ Garage 61")
    st.markdown("---")
    st.subheader("🌤️ Baneforhold")
    sky       = st.selectbox("Sky", ["Clear skies","Partly cloudy","Mostly cloudy","Overcast"])
    ca, cb    = st.columns(2)
    t_temp    = ca.number_input("Bane (°C)", value=38.3, step=0.1)
    a_temp    = cb.number_input("Luft (°C)", value=21.0, step=0.1)
    cw, cd    = st.columns([2,1])
    w_spd     = cw.number_input("Vind (km/h)", value=4)
    w_dir     = cd.selectbox("Dir", ["N","NE","E","SE","S","SW","W","NW"])
    humidity  = st.slider("Fugt (%)", 0, 100, 82)
    precip    = st.slider("Regn (%)", 0, 100, 0)
    t_state   = st.selectbox("Bane-state",
        ["Clean","Low usage","Moderately low usage","Moderate","Heavy","Greasy"], index=2)
    fuel      = st.number_input("Brændstof (L)", value=40.9, step=0.1)
    cond_str  = (f"Sky: {sky}, Bane: {t_temp}°C, Luft: {a_temp}°C, "
                 f"Vind: {w_spd} km/h {w_dir}, Fugt: {humidity}%, "
                 f"Regn: {precip}%, Bane-state: {t_state}, Brændstof: {fuel}L")

    st.markdown("---")
    st.subheader("⚙️ Coaching")
    skill = st.selectbox("Niveau", list(LEVEL.keys()))
    focus = st.selectbox("Fokus",  list(FOCUS.keys()))
    car   = st.selectbox("Bil", [
        "Porsche 911 Cup (992.2)","Porsche 911 GT3 R (992)",
        "GT3 Class","F4","LMP2","GTP","Andet"])
    track = st.text_input("Bane", placeholder="f.eks. Le Mans, Navarra…")
    st.markdown("---")
    st.caption(f"© {datetime.date.today().year} Garage 61 · Claude-powered")

# ── Session state ─────────────────────────────────────────────────────────────
if "log" not in st.session_state:
    st.session_state.log = []

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🏎️ Garage 61 · Telemetry Coach")
st.markdown(
    f"<div class='card'>Bil: <b>{car}</b> &nbsp;·&nbsp; "
    f"Bane: <b>{track or '—'}</b> &nbsp;·&nbsp; "
    f"Niveau: <b>{skill}</b> &nbsp;·&nbsp; Fokus: <b>{focus}</b></div>",
    unsafe_allow_html=True)

t1, t2, t3, t4 = st.tabs([
    "🏁 Enkelt omgang", "🔀 Sammenlign omgange", "📖 Lær telemetri", "📋 Session log"
])

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 · SINGLE LAP
# ══════════════════════════════════════════════════════════════════════════════
with t1:
    up = st.file_uploader("Upload CSV fra Garage 61 (én omgang)", type=["csv"], key="t1")
    if up:
        with st.spinner("Indlæser data…"):
            df = load_csv(up.read())
        m = compute_metrics(df)

        st.markdown("### 📊 Nøgletal")
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("Tophastighed",        f"{m['speed_max']} km/h")
        c2.metric("Fuld gas",            f"{m['throttle_full_pct']}%",
                  help="Andel af runden hvor throttle > 95%")
        c3.metric("Bremse aktiv",        f"{m['brake_active_pct']}%")
        c4.metric("Max bremsetryk",      f"{m['brake_max']}%")
        c5.metric("ABS-indgreb",         str(m['abs_interventions']))
        c6.metric("Gas+bremse overlap",  f"{m['overlap_pct']}%",
                  help="Andel af runden med begge pedaler aktive")

        st.markdown("### 📈 Telemetri-trace")
        st.plotly_chart(main_chart(df, f"{car} · {track or 'ukendt bane'}"),
                        use_container_width=True)

        st.markdown("### 🤖 AI Coaching")
        if st.button("🚀 Analysér med AI", key="btn1"):
            sys_p = f"""Du er en erfaren iRacing race engineer og driver coach fra Garage 61.
Du modtager præcise telemetri-nøgletal beregnet direkte fra CSV-data.

NIVEAU: {LEVEL[skill]}
FOKUS: {FOCUS[focus]}

Svar ALTID på dansk. Strukturér svaret præcis sådan:

## 📊 Hvad fortæller tallene
[Fortolk nøgletallene — hvad ser vi samlet set?]

## ✅ Det går godt
[1-2 konkrete styrker baseret på tallene]

## ⚠️ Her er tid at hente
[2-3 konkrete svagheder med forklaring af HVORFOR det koster tid]

## 🎯 Øvelser til næste stint
[3 nummererede, meget konkrete øvelser — hvad skal man gøre anderledes og præcis HVORDAN]
"""
            user_msg = f"Bil: {car}\nBane: {track or 'ukendt'}\nForhold: {cond_str}\n\n{metrics_text(m)}"
            with st.spinner("Coachen analyserer…"):
                result = call_gemini(sys_p, user_msg)
            st.session_state.log.append({
                "time": datetime.datetime.now().strftime("%H:%M"),
                "type": "Enkelt omgang", "track": track or "—", "content": result,
            })
            st.markdown(result)
    else:
        st.markdown("<div class='card'>Upload en CSV-fil eksporteret direkte fra Garage 61.</div>",
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 · LAP COMPARISON
# ══════════════════════════════════════════════════════════════════════════════
with t2:
    st.markdown("Upload to CSV-filer for at sammenligne speed, pedaler og delta direkte.")
    ca2, cb2 = st.columns(2, gap="large")
    with ca2:
        st.markdown("#### 🔵 Omgang A — dit lap")
        fa   = st.file_uploader("CSV — lap A", type=["csv"], key="t2a")
        la   = st.text_input("Navn", value="Mit lap", key="la")
    with cb2:
        st.markdown("#### 🟠 Omgang B — reference")
        fb   = st.file_uploader("CSV — lap B", type=["csv"], key="t2b")
        lb   = st.text_input("Navn", value="Reference", key="lb")

    if fa and fb:
        with st.spinner("Indlæser begge laps…"):
            dfa = load_csv(fa.read())
            dfb = load_csv(fb.read())
        ma = compute_metrics(dfa)
        mb = compute_metrics(dfb)

        st.markdown("### 📊 Sammenligning")
        c1,c2,c3,c4 = st.columns(4)
        def d(a, b): s = round(b-a, 1); return f"{'+' if s>0 else ''}{s}"
        c1.metric("Tophastighed",
                  f"{ma['speed_max']} / {mb['speed_max']} km/h", d(ma['speed_max'], mb['speed_max']))
        c2.metric("Min. svinghastighed",
                  f"{ma['corner_speed_min']} / {mb['corner_speed_min']} km/h",
                  d(ma['corner_speed_min'], mb['corner_speed_min']))
        c3.metric("Fuld gas-andel",
                  f"{ma['throttle_full_pct']} / {mb['throttle_full_pct']}%",
                  d(ma['throttle_full_pct'], mb['throttle_full_pct']))
        c4.metric("Overlap",
                  f"{ma['overlap_pct']} / {mb['overlap_pct']}%",
                  d(ma['overlap_pct'], mb['overlap_pct']))

        st.markdown("### 📈 Overlay")
        st.plotly_chart(compare_chart(dfa, dfb, la, lb), use_container_width=True)

        st.markdown("### 🤖 AI Delta-analyse")
        if st.button("🔀 Analysér forskel med AI", key="btn2"):
            sys_p = f"""Du er en erfaren iRacing race engineer og driver coach fra Garage 61.
Du modtager nøgletal fra TO omgange og skal forklare præcis hvad der er anderledes.

NIVEAU: {LEVEL[skill]}
FOKUS: {FOCUS[focus]}

Svar ALTID på dansk. Strukturér svaret præcis sådan:

## 🔍 De vigtigste forskelle
[Beskriv de 3 mest betydningsfulde forskelle og hvad de koster]

## 📍 Hvor hentes tidsforskellen
[Beskriv hvilke dele af runden der er afgørende]

## 🎯 Hvad skal {la} arbejde på
[3 meget konkrete, nummererede øvelser til næste stint]
"""
            user_msg = (
                f"Bil: {car}\nBane: {track or 'ukendt'}\nForhold: {cond_str}\n\n"
                + metrics_text(ma, f"({la})") + "\n\n"
                + metrics_text(mb, f"({lb})")
            )
            with st.spinner("Sammenligner…"):
                result = call_gemini(sys_p, user_msg)
            st.session_state.log.append({
                "time": datetime.datetime.now().strftime("%H:%M"),
                "type": f"Sammenligning: {la} vs {lb}", "track": track or "—", "content": result,
            })
            st.markdown(result)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 · LEARN
# ══════════════════════════════════════════════════════════════════════════════
with t3:
    st.markdown("### 📖 Hvad betyder telemetrien?")
    for title, text in [
        ("🔵 Speed (km/h)",
         "Bilens aktuelle hastighed. Speed trace'et afslører ALT — bremsepunkter ses som kraftige fald, "
         "apex som lavpunktet i svingen, og exit som stigningen bagefter. "
         "Minimum-hastighed i apex er typisk den vigtigste enkelt-metrik for et sving."),
        ("🟢 Throttle (0 → 100%)",
         "Gasspjældet. 100% = pedal i bund. Ideelt vil du se en ren stigning fra apex — "
         "ingen hakken eller usikkerhed. Jo tidligere du kan åbne fuld gas, jo hurtigere er "
         "exit-hastigheden og dermed hele den efterfølgende strækning."),
        ("🔴 Brake (0 → 100%)",
         "Bremsepedaltryk. Gode bremser starter med højt tryk (threshold braking) og slipper "
         "progressivt mens bilen drejer ind mod apex (trail-braking). "
         "Et pludseligt slip kan destabilisere bagende."),
        ("🟠 Gear",
         "Gearvalg. Forkert gear til apex påvirker direkte exit-acceleration. "
         "For lavt gear = for mange omdrejninger, for højt = for lidt træk ud af svingen."),
        ("🟣 LongAccel (longitudinal G)",
         "Accelerations-kraft frem og tilbage. Negative værdier = du bremser. "
         "Jo mere negativ, jo hårdere bremser du. Den blødeste overgang fra negativ til positiv "
         "= det bedste trail-braking-punkt."),
        ("🟡 LatAccel (lateral G)",
         "Sidelæns G-kraft — hvor meget bilen skubbes i svingen. "
         "Høj lateral G = god kurveudnyttelse. Hvis den falder mens du giver gas, "
         "understeer du typisk ud af svingen."),
        ("🔶 ABSActive",
         "Sand/falsk — om ABS-systemet aktiverede. Mange ABS-indgreb tyder på for sent "
         "eller for hårdt indbremset. Målet er at være tæt på grænsen uden at ramme den."),
        ("⚙️ Gas+bremse overlap",
         "Andelen af tid hvor begge pedaler er aktive. Et lille overlap er intentionelt "
         "(trail-braking i indgangen), men for meget overlap koster bremse-effektivitet "
         "og er ofte et tegn på panik eller usikkerhed."),
    ]:
        st.markdown(
            f"<div class='learn-card'><h4>{title}</h4><p>{text}</p></div>",
            unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 · SESSION LOG
# ══════════════════════════════════════════════════════════════════════════════
with t4:
    if not st.session_state.log:
        st.info("Ingen analyser endnu — kør en analyse i de andre faner.")
    else:
        hd, cl = st.columns([4,1])
        hd.markdown("### 📋 Session log")
        if cl.button("🗑️ Ryd log"):
            st.session_state.log = []
            st.rerun()
        for entry in reversed(st.session_state.log):
            with st.expander(f"[{entry['time']}] {entry['type']} — {entry['track']}"):
                st.markdown(entry["content"])
        full = "\n\n".join(
            f"--- [{e['time']}] {e['type']} · {e['track']} ---\n{e['content']}"
            for e in st.session_state.log
        )
        st.download_button("📥 Download rapport", data=full,
                           file_name="garage61_coaching.txt", mime="text/plain")
