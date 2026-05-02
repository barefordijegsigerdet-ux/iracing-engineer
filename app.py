import streamlit as st
import numpy as np

from data.ingestion import load_and_process_data
from data.physics import calculate_physics_metrics
from components.charts import create_telemetry_chart

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Telemetry Analysis",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS – Garage 61 dark aesthetic ────────────────────────────────────
st.markdown(
    """
    <style>
      /* Dark background */
      .stApp { background-color: #0e0e0e; color: #e0e0e0; }

      /* Sidebar */
      section[data-testid="stSidebar"] { background-color: #161616; }

      /* Metric cards */
      div[data-testid="metric-container"] {
          background: #1a1a1a;
          border: 1px solid #2a2a2a;
          border-radius: 8px;
          padding: 12px 16px;
      }

      /* Divider */
      hr { border-color: #2a2a2a; }

      /* Upload widget */
      div[data-testid="stFileUploader"] { background: #1a1a1a; border-radius: 8px; }

      /* Spinner text */
      .stSpinner > div { color: #1C83E1 !important; }

      h1, h2, h3, h4 { color: #f0f0f0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🏎️ &nbsp; Professional Telemetry Analysis")
st.caption("Distance-based lap comparison · G-Sum tire utilization · Live delta")
st.divider()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 &nbsp; Lap Files")
    user_file = st.file_uploader(
        "Your Lap (CSV)", type=["csv"], key="user_lap",
        help="iRacing or Garage 61 export — any common header format accepted.",
    )
    ref_file = st.file_uploader(
        "Reference Lap (CSV)", type=["csv"], key="ref_lap",
        help="Target lap to compare against (e.g. fastest lap / pro reference).",
    )

    st.divider()
    st.markdown("### ⚙️ &nbsp; Options")
    downsample = st.checkbox("Downsample large files (>5 000 rows)", value=True)
    show_raw   = st.checkbox("Show raw DataFrame preview", value=False)

    st.divider()
    st.markdown("### 🔧 &nbsp; Speed Unit Override")
    st.caption("Only change if the speed trace looks wrong.")
    speed_unit_override = st.selectbox(
        "Force speed unit",
        options=["Auto-detect", "km/h (no conversion)", "mph → km/h", "m/s → km/h"],
        index=0,
    )


# ── Main Pipeline ─────────────────────────────────────────────────────────────
if user_file and ref_file:
    try:
        # 1 ── Ingest & normalise
        with st.spinner("Parsing & normalising CSVs …"):
            user_df = load_and_process_data(user_file, downsample=downsample,
                                            speed_unit_override=speed_unit_override)
            ref_df  = load_and_process_data(ref_file,  downsample=downsample,
                                            speed_unit_override=speed_unit_override)

        # Show detected speed unit so user knows if override is needed
        detected = user_df.attrs.get("speed_unit", "unknown")
        with st.sidebar:
            st.info(f"⚡ Speed detected as: **{detected}**\n\nIf the speed chart looks wrong, change the override above.", icon="ℹ️")

        if show_raw:
            with st.expander("Raw data preview (first 200 rows)"):
                c1, c2 = st.columns(2)
                c1.dataframe(user_df.head(200), use_container_width=True)
                c2.dataframe(ref_df.head(200),  use_container_width=True)

        # 2 ── Physics engine
        with st.spinner("Deriving time, computing delta & G-Sum …"):
            user_df, ref_df = calculate_physics_metrics(user_df, ref_df)

        # 3 ── Chart
        st.subheader("Lap Comparison")
        fig = create_telemetry_chart(user_df, ref_df)
        st.plotly_chart(fig, use_container_width=True)

        # 4 ── KPI cards
        st.divider()
        st.subheader("Technical Summary")

        total_delta   = user_df["delta"].iloc[-1]
        avg_g_user    = user_df["g_sum"].mean()
        avg_g_ref     = ref_df["g_sum"].mean()
        max_speed_usr = user_df["speed"].max()
        max_speed_ref = ref_df["speed"].max()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Lap Delta",
            f"{total_delta:+.3f} s",
            delta_color="inverse",
            help="Positive = your lap is slower",
        )
        k2.metric(
            "G-Sum (you / ref)",
            f"{avg_g_user:.2f} G",
            delta=f"{avg_g_user - avg_g_ref:+.2f} G vs ref",
            delta_color="normal",
        )
        k3.metric("Peak Speed – You",  f"{max_speed_usr:.1f} km/h")
        k4.metric("Peak Speed – Ref",  f"{max_speed_ref:.1f} km/h")

        # 5 ── Engineer observations
        st.divider()
        st.subheader("Engineer Observations")

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**🔵 Tire Utilisation (G-Sum)**")
            diff_g = avg_g_user - avg_g_ref
            if diff_g < -0.10:
                st.error(
                    f"Under-driving detected. Your average G-Sum ({avg_g_user:.2f} G) "
                    f"is {abs(diff_g):.2f} G below the reference ({avg_g_ref:.2f} G). "
                    "You are not fully loading the tyres — push deeper into the corners."
                )
            elif diff_g > 0.10:
                st.warning(
                    f"Over-driving detected. Your average G-Sum ({avg_g_user:.2f} G) "
                    f"exceeds the reference by {diff_g:.2f} G. "
                    "You may be fighting the car — smoother inputs could be faster."
                )
            else:
                st.success(
                    f"✅ Tyre utilisation is well-matched to the reference "
                    f"({avg_g_user:.2f} G vs {avg_g_ref:.2f} G)."
                )

        with col_b:
            st.markdown("**🔴 Time Delta Trend**")
            # Identify the distance where you lose the most time
            delta_gain = user_df["delta"].diff().fillna(0)
            worst_idx  = delta_gain.idxmax()
            worst_dist = user_df.loc[worst_idx, "distance"]
            worst_loss = delta_gain[worst_idx]

            if worst_loss > 0.01:
                st.warning(
                    f"Largest single-sample time loss of **{worst_loss:.3f} s** "
                    f"at **{worst_dist:.0f} m**. "
                    "Inspect that section in the chart above."
                )
            else:
                st.success("✅ No single dominant area of time loss detected.")

    except Exception as exc:
        st.error(f"❌ Pipeline error: {exc}")
        st.exception(exc)          # full traceback in expander

else:
    # ── Empty state ─────────────────────────────────────────────────────────
    st.info(
        "👈 &nbsp; Upload your lap CSV and a reference lap CSV in the sidebar to begin.",
        icon="📂",
    )
    st.markdown(
        """
        **Supported column names (any alias is auto-detected):**

        | Channel | Common aliases |
        |---|---|
        | Distance | `LapDistPct`, `distance`, `dist`, `lap_distance` |
        | Speed | `speed`, `Speed (km/h)`, `velocity` |
        | Throttle | `throttle`, `Throttle %`, `gas` |
        | Brake | `brake`, `Brake %`, `brake_pedal` |
        | Lat Accel | `lataccel`, `LatAccel`, `g_lat` |
        | Lon Accel | `longaccel`, `LonAccel`, `g_lon` |
        | Time | `time`, `SessionTime`, `elapsed_time` *(optional — derived if absent)* |
        """
    )
