"""
Garage 61 · Telemetry Coach
Understøtter:
  - Session XLSX  (Overview + Session - Practice/Qualify/Race sheets)
  - Lap CSV       (Speed, LapDistPct, Throttle, Brake, RPM, Gear, …)
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
C_GRAY     = "#444444"

LAYOUT_BASE = dict(
    paper_bgcolor="#0D0D0D", plot_bgcolor="#111",
    font=dict(color="#F0F0F0", family="Inter"),
    legend=dict(bgcolor="#0D0D0D", bordercolor="#333", borderwidth=1),
    margin=dict(l=50, r=20, t=40, b=40),
)

SESSION_SHEETS = ["Session - Practice", "Session - Qualify", "Session - Race"]
SESSION_LABELS = {"Session - Practice": "🔧 Practice",
                  "Session - Qualify":  "⏱️ Kval",
                  "Session - Race":     "🏁 Race"}
SESSION_COLOURS = {"Session - Practice": C_SPEED,
                   "Session - Qualify":  C_YELLOW,
                   "Session - Race":     C_ORANGE}

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

# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS — SESSION XLSX
# ═════════════════════════════════════════════════════════════════════════════
def td_to_s(series: pd.Series) -> pd.Series:
    return pd.to_timedelta(series, errors="coerce").dt.total_seconds()


def fmt_s(s) -> str:
    """Seconds → M:SS.mmm string"""
    try:
        s = float(s)
        if pd.isna(s) or s <= 0:
            return "—"
        return f"{int(s//60)}:{s%60:06.3f}"
    except Exception:
        return "—"


COMPASS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]

def _wind_compass(rad: float) -> str:
    deg = float(rad) * 180 / np.pi
    return COMPASS[int((deg + 11.25) / 22.5) % 16]


def _overview_val(ov: pd.DataFrame, label: str) -> str:
    """Find a value in the Overview sheet (label in col 2, value in col 3 one row below)."""
    for i in range(len(ov) - 1):
        if str(ov.iloc[i, 2]).strip() == label:
            v = ov.iloc[i + 1, 3]
            return str(v).strip() if pd.notna(v) else ""
    return ""


@st.cache_data(show_spinner=False)
def load_session_xlsx(data: bytes) -> tuple[dict[str, pd.DataFrame], dict]:
    """Load all session sheets + metadata from a Garage 61 XLSX export."""
    all_sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
    # ── Overview metadata ─────────────────────────────────────────────────────
    ov   = all_sheets.get("Overview", pd.DataFrame())
    meta = {
        "car":    _overview_val(ov, "Car"),
        "track":  _overview_val(ov, "Track"),
        "driver": _overview_val(ov, "Driver"),
        "date":   _overview_val(ov, "Session date"),
    }
    # ── Session sheets ────────────────────────────────────────────────────────
    # Re-read with headers for session sheets
    all_sheets_hdr = pd.read_excel(io.BytesIO(data), sheet_name=None)
    result = {}
    cond   = {}
    for sheet in SESSION_SHEETS:
        if sheet not in all_sheets_hdr:
            continue
        df = all_sheets_hdr[sheet].copy()
        df["LapSec"] = td_to_s(df["Lap time"])
        sec_cols = [c for c in df.columns if c.startswith("Sector ") and not c.endswith("_sec")]
        for col in sec_cols:
            df[col + "_sec"] = td_to_s(df[col])
        df["LapIndex"] = range(1, len(df) + 1)
        df["LapStr"]   = df["LapSec"].apply(fmt_s)
        result[sheet]  = df
        # Extract conditions from first row of first session found
        if not cond and len(df) > 0:
            row = df.iloc[0]
            cond = {
                "track_temp": round(float(row.get("Track temp", 0)), 1),
                "air_temp":   round(float(row.get("Air temperature", 0)), 1),
                "humidity":   round(float(row.get("Relative humidity", 0)) * 100, 1),
                "wind_kmh":   round(float(row.get("Wind velocity", 0)) * 3.6, 1),
                "wind_dir":   _wind_compass(row.get("Wind direction", 0)),
                "fog":        round(float(row.get("Fog level", 0)) * 100, 0),
                "precip":     round(float(row.get("Precipitation", 0)) * 100, 0),
                "track_wet":  round(float(row.get("Track Wetness", 0)) * 100, 0),
            }
    meta["conditions"] = cond
    return result, meta


def session_summary_text(df: pd.DataFrame, session_name: str, sec_cols: list) -> str:
    clean = df[df["Clean"] == 1]
    lines = [f"=== {session_name} ==="]
    lines.append(f"Omgange: {len(df)} total, {len(clean)} rene")
    if not clean.empty:
        best_idx = clean["LapSec"].idxmin()
        best     = clean.loc[best_idx]
        lines.append(f"Bedste omgang: {fmt_s(best['LapSec'])} (lap {int(best['LapIndex'])})")
        if len(clean) > 1:
            lines.append(f"Snit rene omgange: {fmt_s(clean['LapSec'].mean())}")
            lines.append(f"Konsistens (std): {clean['LapSec'].std():.3f}s")
    for col in sec_cols:
        scol = col + "_sec"
        if scol in df.columns:
            valid = clean[scol].dropna() if not clean.empty else df[scol].dropna()
            if not valid.empty:
                lines.append(f"{col} — bedste: {fmt_s(valid.min())} | snit: {fmt_s(valid.mean())}")
    if "Fuel used" in df.columns:
        lines.append(f"Brændstof brugt: {df['Fuel used'].sum():.2f} L")
    return "\n".join(lines)


def lap_time_chart(df: pd.DataFrame, label: str, colour: str) -> go.Figure:
    clean = df[df["Clean"] == 1]
    fig   = go.Figure()
    # All laps (faded)
    fig.add_trace(go.Scatter(
        x=df["LapIndex"], y=df["LapSec"],
        mode="lines+markers", name="Alle omgange",
        line=dict(color=C_GRAY, width=1),
        marker=dict(color=C_GRAY, size=5),
        text=df["LapStr"],
        hovertemplate="Lap %{x}: %{text}<extra></extra>",
    ))
    # Clean laps
    if not clean.empty:
        fig.add_trace(go.Scatter(
            x=clean["LapIndex"], y=clean["LapSec"],
            mode="markers", name="Ren omgang",
            marker=dict(color=colour, size=9, symbol="circle"),
            text=clean["LapStr"],
            hovertemplate="Lap %{x}: %{text} ✓<extra></extra>",
        ))
        # Best lap line
        best_s = clean["LapSec"].min()
        fig.add_hline(y=best_s, line_dash="dot", line_color=colour,
                      annotation_text=f"Best: {fmt_s(best_s)}",
                      annotation_font_color=colour)

    layout = dict(**LAYOUT_BASE)
    layout["title"]  = dict(text=f"Laptider — {label}", font=dict(color=colour, size=13))
    layout["height"] = 320
    layout["xaxis"]  = dict(title="Omgang #", gridcolor="#1e1e1e")
    layout["yaxis"]  = dict(title="Tid (s)", gridcolor="#1e1e1e")
    fig.update_layout(**layout)
    return fig


def sector_chart(df: pd.DataFrame, sec_cols: list, colour: str) -> go.Figure | None:
    clean = df[df["Clean"] == 1]
    src   = clean if not clean.empty else df
    data  = []
    for col in sec_cols:
        scol = col + "_sec"
        if scol in df.columns:
            vals = src[scol].dropna()
            if not vals.empty:
                data.append(dict(sector=col, best=vals.min(), mean=vals.mean()))
    if not data:
        return None
    sdf = pd.DataFrame(data)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sdf["sector"], y=sdf["best"],
        name="Bedste", marker_color=colour, opacity=0.9,
        text=[fmt_s(v) for v in sdf["best"]],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        x=sdf["sector"], y=sdf["mean"],
        name="Snit", marker_color=colour, opacity=0.4,
        text=[fmt_s(v) for v in sdf["mean"]],
        textposition="outside",
    ))
    layout = dict(**LAYOUT_BASE)
    layout["title"]     = dict(text="Sektor-tider", font=dict(color=colour, size=13))
    layout["height"]    = 300
    layout["barmode"]   = "group"
    layout["xaxis"]     = dict(gridcolor="#1e1e1e")
    layout["yaxis"]     = dict(title="Tid (s)", gridcolor="#1e1e1e")
    fig.update_layout(**layout)
    return fig


# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS — LAP CSV
# ═════════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def load_lap_csv(data: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(data))
    for col in ["Throttle","Brake","Speed","RPM","Gear","LapDistPct",
                "LatAccel","LongAccel","SteeringWheelAngle"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["ThrottlePct"] = df["Throttle"] * 100
    df["BrakePct"]    = df["Brake"]    * 100
    df["Speed"]       = df["Speed"]    * 3.6   # m/s → km/h
    if "LatAccel"  in df.columns: df["LatAccel"]  = df["LatAccel"]  / 9.81
    if "LongAccel" in df.columns: df["LongAccel"] = df["LongAccel"] / 9.81
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


def compute_lap_metrics(df: pd.DataFrame) -> dict:
    spd = df["Speed"];  thr = df["ThrottlePct"];  brk = df["BrakePct"]
    low = spd < spd.max() * 0.65
    m   = dict(
        speed_max          = round(spd.max(), 1),
        speed_mean         = round(spd.mean(), 1),
        corner_speed_min   = round(spd[low].min(), 1)  if low.any() else 0,
        corner_speed_mean  = round(spd[low].mean(), 1) if low.any() else 0,
        throttle_full_pct  = round((thr >= 95).mean() * 100, 1),
        throttle_zero_pct  = round((thr <= 5).mean()  * 100, 1),
        throttle_mean      = round(thr.mean(), 1),
        brake_max          = round(brk.max(), 1),
        brake_active_pct   = round((brk > 5).mean() * 100, 1),
        brake_mean_active  = round(brk[brk > 5].mean(), 1) if (brk > 5).any() else 0,
        overlap_pct        = round(((thr > 10) & (brk > 10)).mean() * 100, 1),
        gear_max           = int(df["Gear"].max()),
        gear_changes       = int(df["Gear"].diff().abs().fillna(0).astype(bool).sum()),
        lat_g_max          = round(df["LatAccel"].abs().max(), 2),
        long_g_min         = round(df["LongAccel"].min(), 2),
    )
    if "ABSActive" in df.columns:
        m["abs_interventions"] = int(df["ABSActive"].astype(int).diff().clip(lower=0).sum())
    else:
        m["abs_interventions"] = "N/A"
    return m


def lap_metrics_text(m: dict, label: str = "") -> str:
    return "\n".join([
        f"=== Telemetri nøgletal {label} ===",
        f"Tophastighed: {m['speed_max']} km/h | Snit: {m['speed_mean']} km/h",
        f"Min. svinghastighed: {m['corner_speed_min']} km/h | Snit i sving: {m['corner_speed_mean']} km/h",
        f"Gas — fuld gas: {m['throttle_full_pct']}% | nul gas: {m['throttle_zero_pct']}% | snit: {m['throttle_mean']}%",
        f"Bremse — max: {m['brake_max']}% | aktiv: {m['brake_active_pct']}% | snit under bremse: {m['brake_mean_active']}%",
        f"Gas+bremse overlap: {m['overlap_pct']}%",
        f"ABS-indgreb: {m['abs_interventions']}",
        f"Max lateral G: {m['lat_g_max']} | Hårdest bremse-G: {m['long_g_min']}",
        f"Gear skift: {m['gear_changes']} | Højeste gear: {m['gear_max']}",
    ])


def lap_chart(df: pd.DataFrame, title: str = "") -> go.Figure:
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
        ax = df.loc[df["ABSActive"], "LapDistPct"].values * 100
        ay = df.loc[df["ABSActive"], "Speed"].values
        fig.add_trace(go.Scatter(x=ax, y=ay, mode="markers", name="ABS aktiv",
            marker=dict(color=C_YELLOW, size=4)), row=1, col=1)
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
    layout["title"]  = dict(text=title, font=dict(color=C_ORANGE, size=13))
    layout["height"] = 700
    for r in range(1, 5):
        fig.update_xaxes(gridcolor="#1e1e1e", zerolinecolor="#333", row=r, col=1)
        fig.update_yaxes(gridcolor="#1e1e1e", zerolinecolor="#333", row=r, col=1)
    fig.update_xaxes(title_text="Rundeposition (%)", row=4, col=1)
    fig.update_layout(**layout)
    return fig


def compare_chart(dfa: pd.DataFrame, dfb: pd.DataFrame,
                  la: str, lb: str) -> go.Figure:
    ra = resample_to(dfa);  rb = resample_to(dfb)
    x  = ra["LapDistPct"].values * 100

    # Cumulative time delta: dt = d_dist / speed  (normalised — shape is exact, scale ~arbitrary)
    # Positive = lb is ahead (gaining time), negative = la is ahead
    d_dist   = np.diff(ra["LapDistPct"].values, prepend=ra["LapDistPct"].values[0])
    d_dist   = np.where(d_dist <= 0, 1e-9, d_dist)
    v_a      = np.where(ra["Speed"].values > 0, ra["Speed"].values, 1e-9)
    v_b      = np.where(rb["Speed"].values > 0, rb["Speed"].values, 1e-9)
    dt_a     = d_dist / v_a
    dt_b     = d_dist / v_b
    cum_delta = np.cumsum(dt_b - dt_a)
    # Scale so y-axis is in seconds (approximate — assumes 1 km/h normalisation)
    scale    = 3600.0
    cum_delta_s = cum_delta * scale

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.35, 0.25, 0.20, 0.20], vertical_spacing=0.035,
        subplot_titles=[
            "Speed overlay (km/h)",
            "Throttle & Brake (%)",
            f"Δ Speed: {lb} − {la}  (km/h)",
            f"Kumulativ tidsdelta  (positiv = {lb} er foran)",
        ],
    )
    # Speed overlay
    fig.add_trace(go.Scatter(x=x, y=ra["Speed"], name=f"Speed — {la}",
        line=dict(color=C_SPEED, width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=rb["Speed"], name=f"Speed — {lb}",
        line=dict(color=C_ORANGE, width=1.5, dash="dash")), row=1, col=1)
    # Pedals
    fig.add_trace(go.Scatter(x=x, y=ra["ThrottlePct"], name=f"Gas — {la}",
        line=dict(color=C_THROTTLE, width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=rb["ThrottlePct"], name=f"Gas — {lb}",
        line=dict(color=C_THROTTLE, width=1.2, dash="dash")), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=ra["BrakePct"], name=f"Bremse — {la}",
        line=dict(color=C_BRAKE, width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=x, y=rb["BrakePct"], name=f"Bremse — {lb}",
        line=dict(color=C_BRAKE, width=1.2, dash="dash")), row=2, col=1)
    # Delta speed (bar)
    delta  = rb["Speed"].values - ra["Speed"].values
    colors = [C_GREEN if d >= 0 else C_BRAKE for d in delta]
    fig.add_trace(go.Bar(x=x, y=delta, name="Δ Speed",
        marker_color=colors, marker_line_width=0), row=3, col=1)
    fig.add_hline(y=0, line_color="#444", row=3, col=1)
    # Cumulative delta time (line, filled)
    fig.add_trace(go.Scatter(
        x=x, y=cum_delta_s,
        name="Kumulativ delta",
        line=dict(color=C_YELLOW, width=2),
        fill="tozeroy",
        fillcolor=f"rgba(255,214,0,0.10)",
        hovertemplate="%{y:.3f}s<extra></extra>",
    ), row=4, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#555", row=4, col=1)

    layout = dict(**LAYOUT_BASE)
    layout["height"] = 900
    for r in range(1, 5):
        fig.update_xaxes(gridcolor="#1e1e1e", zerolinecolor="#333", row=r, col=1)
        fig.update_yaxes(gridcolor="#1e1e1e", zerolinecolor="#333", row=r, col=1)
    fig.update_yaxes(title_text="s", row=4, col=1)
    fig.update_xaxes(title_text="Rundeposition (%)", row=4, col=1)
    fig.update_layout(**layout)
    return fig


# ═════════════════════════════════════════════════════════════════════════════
#  GEMINI
# ═════════════════════════════════════════════════════════════════════════════
def call_ai(system: str, user: str) -> str:
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
    return model.generate_content(user).text


# ── No sidebar — settings moved inline ───────────────────────────────────────
# Fallback conditions string (used by CSV tabs when no XLSX is loaded)
cond_str = "Ukendt — upload en session XLSX for automatiske baneforhold"
car   = ""
track = ""

# ═════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ═════════════════════════════════════════════════════════════════════════════
if "log" not in st.session_state:
    st.session_state.log = []

# ═════════════════════════════════════════════════════════════════════════════
#  HEADER + INLINE CONTROLS
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("# 🏎️ Garage 61 · Telemetry Coach")
hc1, hc2 = st.columns([1, 1])
with hc1:
    skill = st.selectbox("🎓 Coaching-niveau",  list(LEVEL.keys()), label_visibility="visible")
with hc2:
    focus = st.selectbox("🔍 Analysefokus", list(FOCUS.keys()), label_visibility="visible")
st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════════
#  TABS
# ═════════════════════════════════════════════════════════════════════════════
t_guide, t_sess, t_single, t_cmp, t_learn, t_log = st.tabs([
    "🚀 Kom i gang",
    "📋 Session overview",
    "🏁 Enkelt omgang",
    "🔀 Sammenlign omgange",
    "📖 Lær telemetri",
    "📋 Session log",
])

# ─────────────────────────────────────────────────────────────────────────────
#  TAB: KOM I GANG
# ─────────────────────────────────────────────────────────────────────────────
with t_guide:
    st.markdown("## Velkommen til Garage 61 Telemetry Coach")
    st.markdown(
        "<div class='card'>Appen hjælper dig med at forstå dine iRacing-data fra Garage 61 — "
        "uden at du behøver at være ingeniør. Upload dine filer, og AI-coachen fortæller dig "
        "præcist hvad der sker og hvad du skal øve dig på.</div>",
        unsafe_allow_html=True)

    st.markdown("### 📁 Hvilke filer bruger jeg?")
    fc1, fc2 = st.columns(2, gap="large")
    with fc1:
        st.markdown("""<div class='learn-card'>
<h4>📋 Session XLSX — til Session overview</h4>
<p>Eksporter hele weekenden fra Garage 61:<br><br>
<b>Garage 61 → Sessions → vælg session → Export → Excel (.xlsx)</b><br><br>
Én fil indeholder Practice, Kval og Race samlet.
Appen henter automatisk bil, bane, kørernavn og baneforhold — du skal ikke taste noget selv.</p>
</div>""", unsafe_allow_html=True)

    with fc2:
        st.markdown("""<div class='learn-card'>
<h4>🏁 Lap CSV — til enkelt omgang og sammenligning</h4>
<p>Eksporter en enkelt omgang fra Garage 61:<br><br>
<b>Garage 61 → Sessions → vælg omgang → Export → CSV</b><br><br>
CSV-filen indeholder ~14.000 datapunkter per omgang med fuld sensor-data:
speed, gas, bremse, gear, G-kræfter og ABS.</p>
</div>""", unsafe_allow_html=True)

    st.markdown("### 🗺️ Faneoversigt")
    tabs_info = [
        ("📋 Session overview",   "Upload XLSX. Få laptider, sektortider og AI-analyse af hele weekenden — Practice, Kval og Race i separate faner."),
        ("🏁 Enkelt omgang",      "Upload én lap CSV. Se fuld telemetri-trace (speed, gas, bremse, gear, G-kræfter) og få AI-coaching baseret på præcise nøgletal."),
        ("🔀 Sammenlign omgange", "Upload to lap CSVs. Se speed overlay og delta-graf der viser præcist hvor på banen du er hurtigere eller langsommere end referencen."),
        ("📖 Lær telemetri",      "Forklaringer på alle kanaler — hvad betyder speed trace, throttle, brake, lateral G osv. Godt udgangspunkt hvis du er ny."),
        ("📋 Session log",        "Alle AI-analyser fra sessionen gemmes her. Download dem som en samlet rapport når du er færdig."),
    ]
    for tab_name, desc in tabs_info:
        st.markdown(
            f"<div class='learn-card'><h4>{tab_name}</h4><p>{desc}</p></div>",
            unsafe_allow_html=True)

    st.markdown("### 🎓 Indstillinger")
    st.markdown(
        "<div class='card'>"
        "<b>Coaching-niveau</b> styrer sproget i AI-svarene — Begynder bruger hverdagsord og analogier, "
        "Avanceret er teknisk og præcis.<br><br>"
        "<b>Analysefokus</b> fortæller AI'en hvad den skal prioritere — bremse, gas, speed trace eller alt på én gang."
        "</div>", unsafe_allow_html=True)

    st.markdown(
        f"<div style='text-align:center;color:#444;font-size:.8rem;margin-top:2rem'>"
        f"© {datetime.date.today().year} Garage 61 · Powered by Gemini 3.1 Flash Lite</div>",
        unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB: SESSION OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
with t_sess:
    xlsx_up = st.file_uploader(
        "Upload XLSX-session fra Garage 61 (indeholder Practice, Kval og/eller Race)",
        type=["xlsx"], key="sess_xlsx")

    if xlsx_up:
        with st.spinner("Indlæser session…"):
            sessions, meta = load_session_xlsx(xlsx_up.read())

        if not sessions:
            st.error("Ingen kendte session-sheets fundet i filen.")
        else:
            # ── Session metadata card ─────────────────────────────────────────
            cond = meta.get("conditions", {})
            cond_auto = (
                f"Bane: {cond.get('track_temp','?')}°C, "
                f"Luft: {cond.get('air_temp','?')}°C, "
                f"Fugt: {cond.get('humidity','?')}%, "
                f"Vind: {cond.get('wind_kmh','?')} km/h {cond.get('wind_dir','?')}, "
                f"Regn: {cond.get('precip','?')}%, "
                f"Bane-våd: {cond.get('track_wet','?')}%"
            )
            st.markdown(
                f"<div class='card'>"
                f"🏎️ <b>{meta.get('car','—')}</b> &nbsp;·&nbsp; "
                f"📍 <b>{meta.get('track','—')}</b> &nbsp;·&nbsp; "
                f"👤 <b>{meta.get('driver','—')}</b><br>"
                f"🌤️ {cond_auto}"
                f"</div>", unsafe_allow_html=True)

            # ── Create inner tabs ─────────────────────────────────────────────
            inner_labels = [SESSION_LABELS[s] for s in SESSION_SHEETS if s in sessions]
            inner_keys   = [s for s in SESSION_SHEETS if s in sessions]
            inner_tabs   = st.tabs(inner_labels)

            for tab, key in zip(inner_tabs, inner_keys):
                with tab:
                    df     = sessions[key]
                    colour = SESSION_COLOURS[key]
                    clean  = df[df["Clean"] == 1]
                    sec_cols = [c for c in df.columns
                                if c.startswith("Sector ") and not c.endswith("_sec")]
                    driver = meta.get("driver") or (df["Driver"].iloc[0] if "Driver" in df.columns else "—")

                    # ── Metrics row ───────────────────────────────────────────
                    st.markdown(f"#### {SESSION_LABELS[key]} — {driver}")
                    c1, c2, c3, c4 = st.columns(4)
                    best_s = clean["LapSec"].min() if not clean.empty else None
                    c1.metric("Bedste omgang",    fmt_s(best_s) if best_s else "—")
                    c2.metric("Rene omgange",     f"{len(clean)} / {len(df)}")
                    std_s = clean["LapSec"].std() if len(clean) > 1 else None
                    c3.metric("Konsistens (std)", f"{std_s:.3f}s" if std_s else "—")
                    fuel = df["Fuel used"].sum() if "Fuel used" in df.columns else 0
                    c4.metric("Brændstof brugt",  f"{fuel:.2f} L")

                    # ── Charts ────────────────────────────────────────────────
                    ch1, ch2 = st.columns([3, 2], gap="medium")
                    with ch1:
                        st.plotly_chart(lap_time_chart(df, SESSION_LABELS[key], colour),
                                        use_container_width=True)
                    with ch2:
                        sfig = sector_chart(df, sec_cols, colour)
                        if sfig:
                            st.plotly_chart(sfig, use_container_width=True)
                        else:
                            st.info("Ingen sektortider tilgængelige.")

                    # ── Lap table ─────────────────────────────────────────────
                    with st.expander("📄 Lap-tabel"):
                        show_cols = (["LapIndex","LapStr","Clean"]
                                     + [c + "_sec" for c in sec_cols if c + "_sec" in df.columns]
                                     + (["Fuel used"] if "Fuel used" in df.columns else []))
                        tbl = df[show_cols].copy()
                        tbl.columns = (["#","Laptid","Ren"]
                                       + [c.replace("Sector ","S").replace("_sec","") for c in sec_cols]
                                       + (["Fuel brugt (L)"] if "Fuel used" in df.columns else []))
                        # Format sector seconds
                        for c in tbl.columns:
                            if c.startswith("S") and c[1:].isdigit():
                                tbl[c] = tbl[c].apply(fmt_s)
                        st.dataframe(tbl, use_container_width=True, hide_index=True)

                    # ── AI coaching ───────────────────────────────────────────
                    st.markdown("#### 🤖 AI Session-analyse")
                    if st.button(f"Analysér {SESSION_LABELS[key]} med AI",
                                 key=f"btn_sess_{key}"):
                        sys_p = f"""Du er en erfaren iRacing race engineer og driver coach fra Garage 61.
Du modtager session-nøgletal (laptider, sektortider, brændstof) og skal give konkret feedback.

NIVEAU: {LEVEL[skill]}
FOKUS: {FOCUS[focus]}

Svar ALTID på dansk. Strukturér svaret præcis sådan:

## 📊 Sessionsbillede
[Overordnet vurdering af sessionen — tempo, konsistens, progression]

## ✅ Det går godt
[1-2 konkrete styrker]

## ⚠️ Her er tid at hente
[2-3 konkrete svagheder med forklaring]

## 🎯 Fokuspunkter til næste session
[3 nummererede, konkrete øvelser]
"""
                        auto_car   = meta.get("car")   or car
                        auto_track = meta.get("track") or track or "ukendt"
                        user_msg = (
                            f"Bil: {auto_car}\nBane: {auto_track}\nForhold: {cond_auto}\n\n"
                            + session_summary_text(df, SESSION_LABELS[key], sec_cols)
                        )
                        with st.spinner("Analyserer…"):
                            result = call_ai(sys_p, user_msg)
                        st.session_state.log.append({
                            "time": datetime.datetime.now().strftime("%H:%M"),
                            "type": f"Session: {SESSION_LABELS[key]}",
                            "track": track or "—",
                            "content": result,
                        })
                        st.markdown(result)
    else:
        st.markdown(
            "<div class='card'>Upload en XLSX-fil eksporteret fra Garage 61. "
            "Filen kan indeholde Practice, Kval og/eller Race — alle sessions vises automatisk.</div>",
            unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB: ENKELT OMGANG
# ─────────────────────────────────────────────────────────────────────────────
with t_single:
    csv_up = st.file_uploader(
        "Upload CSV fra Garage 61 (én omgang)", type=["csv"], key="t1_csv")
    if csv_up:
        with st.spinner("Indlæser data…"):
            df = load_lap_csv(csv_up.read())
        m = compute_lap_metrics(df)

        st.markdown("### 📊 Nøgletal")
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("Tophastighed",       f"{m['speed_max']} km/h")
        c2.metric("Fuld gas",           f"{m['throttle_full_pct']}%")
        c3.metric("Bremse aktiv",       f"{m['brake_active_pct']}%")
        c4.metric("Max bremsetryk",     f"{m['brake_max']}%")
        c5.metric("ABS-indgreb",        str(m['abs_interventions']))
        c6.metric("Gas+bremse overlap", f"{m['overlap_pct']}%")

        st.markdown("### 📈 Telemetri-trace")
        st.plotly_chart(lap_chart(df, f"{car} · {track or 'ukendt bane'}"),
                        use_container_width=True)

        st.markdown("### 🤖 AI Coaching")
        if st.button("🚀 Analysér med AI", key="btn_single"):
            sys_p = f"""Du er en erfaren iRacing race engineer og driver coach fra Garage 61.
Du modtager præcise telemetri-nøgletal beregnet direkte fra CSV-data.

NIVEAU: {LEVEL[skill]}
FOKUS: {FOCUS[focus]}

Svar ALTID på dansk. Strukturér svaret præcis sådan:

## 📊 Hvad fortæller tallene
[Fortolk nøgletallene — hvad ser vi samlet set?]

## ✅ Det går godt
[1-2 konkrete styrker]

## ⚠️ Her er tid at hente
[2-3 konkrete svagheder med forklaring af HVORFOR det koster tid]

## 🎯 Øvelser til næste stint
[3 nummererede, meget konkrete øvelser]
"""
            user_msg = (f"Bil: {car}\nBane: {track or 'ukendt'}\nForhold: {cond_str}\n\n"
                        + lap_metrics_text(m))
            with st.spinner("Coachen analyserer…"):
                result = call_ai(sys_p, user_msg)
            st.session_state.log.append({
                "time": datetime.datetime.now().strftime("%H:%M"),
                "type": "Enkelt omgang", "track": track or "—", "content": result,
            })
            st.markdown(result)
    else:
        st.markdown("<div class='card'>Upload en CSV-fil eksporteret fra Garage 61.</div>",
                    unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB: SAMMENLIGN OMGANGE
# ─────────────────────────────────────────────────────────────────────────────
with t_cmp:
    st.markdown("Upload to CSV-filer for at sammenligne speed, pedaler og delta.")
    ca2, cb2 = st.columns(2, gap="large")
    with ca2:
        st.markdown("#### 🔵 Omgang A")
        fa = st.file_uploader("CSV — lap A", type=["csv"], key="t2a")
        la = st.text_input("Navn", value="Mit lap", key="la")
    with cb2:
        st.markdown("#### 🟠 Omgang B — reference")
        fb = st.file_uploader("CSV — lap B", type=["csv"], key="t2b")
        lb = st.text_input("Navn", value="Reference", key="lb")

    if fa and fb:
        with st.spinner("Indlæser begge laps…"):
            dfa = load_lap_csv(fa.read())
            dfb = load_lap_csv(fb.read())
        ma = compute_lap_metrics(dfa)
        mb = compute_lap_metrics(dfb)

        st.markdown("### 📊 Sammenligning")
        c1,c2,c3,c4 = st.columns(4)
        def d(a, b): s = round(b-a,1); return f"{'+' if s>0 else ''}{s}"
        c1.metric("Tophastighed",
                  f"{ma['speed_max']} / {mb['speed_max']} km/h",
                  d(ma['speed_max'], mb['speed_max']))
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
        if st.button("🔀 Analysér forskel med AI", key="btn_cmp"):
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
                + lap_metrics_text(ma, f"({la})") + "\n\n"
                + lap_metrics_text(mb, f"({lb})")
            )
            with st.spinner("Sammenligner…"):
                result = call_ai(sys_p, user_msg)
            st.session_state.log.append({
                "time": datetime.datetime.now().strftime("%H:%M"),
                "type": f"Sammenligning: {la} vs {lb}",
                "track": track or "—", "content": result,
            })
            st.markdown(result)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB: LÆR TELEMETRI
# ─────────────────────────────────────────────────────────────────────────────
with t_learn:
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
         "Den blødeste overgang fra negativ til positiv = det bedste trail-braking-punkt."),
        ("🟡 LatAccel (lateral G)",
         "Sidelæns G-kraft. Høj lateral G = god kurveudnyttelse. "
         "Hvis den falder mens du giver gas, understeer du typisk ud af svingen."),
        ("🔶 ABSActive",
         "Sand/falsk — om ABS aktiverede. Mange indgreb tyder på for sent eller for hårdt "
         "indbremset. Målet er at ligge tæt på grænsen uden at ramme den."),
        ("⚙️ Gas+bremse overlap",
         "Andelen af tid hvor begge pedaler er aktive samtidigt. Et lille overlap er intentionelt "
         "(trail-braking i indgangen), men for meget overlap koster bremse-effektivitet."),
        ("📋 Session XLSX — Sektor-tider",
         "Garage 61 opdeler runden i sektorer. Sektortider er nøglen til at finde præcist "
         "HVOR på banen du taber tid — ikke bare om du er hurtig eller langsom samlet set. "
         "Sammenlign dine sektor-snit med dit bedste sektortid for at se konsistensproblemet."),
    ]:
        st.markdown(
            f"<div class='learn-card'><h4>{title}</h4><p>{text}</p></div>",
            unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  TAB: SESSION LOG
# ─────────────────────────────────────────────────────────────────────────────
with t_log:
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
