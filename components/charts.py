"""
components/charts.py
────────────────────
Plotly multi-panel telemetry chart with Garage 61 colour palette.

Layout (top → bottom, all sharing the distance X-axis)
───────────────────────────────────────────────────────
  Row 1 – Speed      (km/h)
  Row 2 – Time Delta (seconds, zero-reference line)
  Row 3 – Throttle   (%)
  Row 4 – Brake      (%)
  Row 5 – G-Sum      (G)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ── Garage 61 colour palette ───────────────────────────────────────────────────
COLOR_USER  = "#1C83E1"   # blue  – user lap
COLOR_REF   = "#FF4B4B"   # red   – reference lap
COLOR_DELTA_POS = "#FF4B4B"   # losing time
COLOR_DELTA_NEG = "#00C853"   # gaining time

BG_MAIN   = "#0e0e0e"
BG_PAPER  = "#0e0e0e"
GRID_COL  = "#1e1e1e"
AXIS_COL  = "#3a3a3a"
TEXT_COL  = "#a0a0a0"
FONT_FAM  = "Inter, Roboto Mono, monospace"


# ── Panel configuration ────────────────────────────────────────────────────────
PANELS = [
    {"title": "Speed (km/h)",     "col": "speed",    "row_h": 0.24},
    {"title": "Delta (s)",         "col": "delta",    "row_h": 0.16},
    {"title": "Throttle (%)",      "col": "throttle", "row_h": 0.18},
    {"title": "Brake (%)",         "col": "brake",    "row_h": 0.18},
    {"title": "G-Sum (G)",         "col": "g_sum",    "row_h": 0.18},
]
N_ROWS = len(PANELS)


def _shared_axis_style() -> dict:
    return dict(
        showgrid=True,
        gridcolor=GRID_COL,
        gridwidth=1,
        zeroline=False,
        color=TEXT_COL,
        tickfont=dict(family=FONT_FAM, size=10, color=TEXT_COL),
        linecolor=AXIS_COL,
        linewidth=1,
    )


def _add_trace(
    fig: go.Figure,
    x: np.ndarray,
    y: np.ndarray,
    name: str,
    color: str,
    row: int,
    show_legend: bool = True,
    fill: str | None = None,
    line_width: int = 1,
) -> None:
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            name=name,
            mode="lines",
            line=dict(color=color, width=line_width),
            fill=fill,
            fillcolor=color.replace(")", ", 0.08)").replace("rgb", "rgba")
                if fill and color.startswith("rgb") else None,
            legendgroup=name,
            showlegend=show_legend,
            hovertemplate=f"<b>{name}</b><br>Dist: %{{x:.0f}} m<br>Value: %{{y:.3f}}<extra></extra>",
        ),
        row=row, col=1,
    )


def _add_delta_traces(
    fig: go.Figure,
    user_df: pd.DataFrame,
    row: int,
) -> None:
    """
    Delta panel: colour-coded fill (red above zero = losing, green below = gaining).
    Uses two masked scatter traces so the fills don't bleed across the zero line.
    """
    x  = user_df["distance"].to_numpy()
    y  = user_df["delta"].to_numpy()

    # ── zero baseline ─────────────────────────────────────────────────────────
    fig.add_hline(
        y=0,
        line_dash="dot",
        line_color="#555555",
        line_width=1,
        row=row, col=1,
    )

    # ── positive (losing time) ────────────────────────────────────────────────
    y_pos = np.where(y > 0, y, 0.0)
    fig.add_trace(
        go.Scatter(
            x=x, y=y_pos,
            name="Delta (losing)",
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(255,75,75,0.20)",
            line=dict(color=COLOR_DELTA_POS, width=1),
            showlegend=False,
            hovertemplate="Dist: %{x:.0f} m | Δ: +%{y:.3f} s<extra></extra>",
        ),
        row=row, col=1,
    )

    # ── negative (gaining time) ───────────────────────────────────────────────
    y_neg = np.where(y < 0, y, 0.0)
    fig.add_trace(
        go.Scatter(
            x=x, y=y_neg,
            name="Delta (gaining)",
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(0,200,83,0.20)",
            line=dict(color=COLOR_DELTA_NEG, width=1),
            showlegend=False,
            hovertemplate="Dist: %{x:.0f} m | Δ: %{y:.3f} s<extra></extra>",
        ),
        row=row, col=1,
    )

    # ── main delta line (on top) ──────────────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=x, y=y,
            name="Delta",
            mode="lines",
            line=dict(color="#FFFFFF", width=1.5),
            showlegend=False,
            hovertemplate="Dist: %{x:.0f} m | Δ: %{y:.3f} s<extra></extra>",
        ),
        row=row, col=1,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def create_telemetry_chart(
    user_df: pd.DataFrame,
    ref_df:  pd.DataFrame,
) -> go.Figure:
    """
    Build and return a full Garage-61-style multi-panel Plotly figure.

    Parameters
    ----------
    user_df : Physics-processed user lap DataFrame.
    ref_df  : Physics-processed reference lap DataFrame.

    Returns
    -------
    plotly.graph_objects.Figure
    """
    row_heights = [p["row_h"] for p in PANELS]

    fig = make_subplots(
        rows=N_ROWS,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=[p["title"] for p in PANELS],
    )

    x_user = user_df["distance"].to_numpy()
    x_ref  = ref_df["distance"].to_numpy()

    for row_idx, panel in enumerate(PANELS, start=1):
        col = panel["col"]

        if col == "delta":
            _add_delta_traces(fig, user_df, row=row_idx)
        else:
            # Reference lap
            if col in ref_df.columns:
                _add_trace(
                    fig, x_ref, ref_df[col].to_numpy(),
                    name="Reference",
                    color=COLOR_REF,
                    row=row_idx,
                    show_legend=(row_idx == 1),
                    line_width=1,
                )

            # User lap (drawn on top)
            if col in user_df.columns:
                _add_trace(
                    fig, x_user, user_df[col].to_numpy(),
                    name="You",
                    color=COLOR_USER,
                    row=row_idx,
                    show_legend=(row_idx == 1),
                    line_width=1,
                )

        # Y-axis per panel
        y_axis_opts = _shared_axis_style()

        # Clamp throttle/brake to 0-100
        if col in ("throttle", "brake"):
            y_axis_opts.update(range=[0, 105])

        fig.update_yaxes(
            **y_axis_opts,
            title_text="",
            row=row_idx, col=1,
        )

    # ── Shared X-axis (bottom panel only) ─────────────────────────────────────
    fig.update_xaxes(
        **_shared_axis_style(),
        title_text="Distance (m)",
        row=N_ROWS, col=1,
    )

    # X-axes for upper panels (no label, no tick labels except bottom)
    for r in range(1, N_ROWS):
        fig.update_xaxes(showticklabels=False, row=r, col=1)

    # ── Global layout ──────────────────────────────────────────────────────────
    fig.update_layout(
        height=820,
        paper_bgcolor=BG_PAPER,
        plot_bgcolor=BG_MAIN,
        margin=dict(l=60, r=20, t=40, b=60),
        font=dict(family=FONT_FAM, color=TEXT_COL, size=11),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color="#e0e0e0"),
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1a1a1a",
            bordercolor="#333333",
            font=dict(family=FONT_FAM, size=11, color="#e0e0e0"),
        ),
    )

    # Style subplot title annotations (the small grey labels above each panel)
    for ann in fig.layout.annotations:
        ann.font.color  = "#666666"
        ann.font.size   = 10
        ann.font.family = FONT_FAM

    return fig
