"""
data/ingestion.py
─────────────────
CSV ingest, header normalisation, unit scaling, and safe downsampling.

Handles common iRacing / Garage 61 / MoTeC / AiM export formats.
"""
from __future__ import annotations

import difflib
import io
import streamlit as st
import pandas as pd
import numpy as np


# ── Schema: target_name → list[known_aliases] ─────────────────────────────────
#   All aliases are stored lower-case; matching is case-insensitive.
SCHEMA: dict[str, list[str]] = {
    "distance": [
        "distance", "distance (m)", "dist", "lapdist", "lap_distance",
        "lapdistpct", "lap_dist_pct", "trackposition", "track_position",
    ],
    "speed": [
        "speed", "speed (km/h)", "speed (mph)", "speed_kmh", "velocity",
        "v", "gps_speed", "spd",
    ],
    "throttle": [
        "throttle", "throttle %", "throttle_pct", "throttle_raw",
        "gas", "accel", "throttleraw", "tps",
    ],
    "brake": [
        "brake", "brake %", "brake_pct", "brake_raw", "dec",
        "brake_pedal", "brakeraw", "bps",
    ],
    "time": [
        "time", "sessiontime", "laptime", "lap_time", "current_time",
        "elapsed_time", "timestamp", "t",
    ],
    "lataccel": [
        "lataccel", "lateral_acceleration", "lat_accel", "g_lat",
        "lateralaccel", "lat_g", "ay",
    ],
    "longaccel": [
        "longaccel", "longitudinal_acceleration", "lon_accel", "long_accel",
        "g_lon", "longitudinalaccel", "lon_g", "ax",
    ],
    "steer": [
        "steer", "steering", "steeringwheelangle", "steering_angle",
        "steer_angle",
    ],
    "gear": [
        "gear", "currentgear", "current_gear",
    ],
}

ESSENTIAL_COLS = ["distance", "speed", "throttle", "brake"]
OPTIONAL_COLS  = ["time", "lataccel", "longaccel", "steer", "gear"]


# ── Normalisation ──────────────────────────────────────────────────────────────

def _match_column(target: str, aliases: list[str], available: list[str]) -> str | None:
    """
    Three-pass column resolution:
      1. Exact match against aliases list.
      2. Substring containment (target word inside column name).
      3. Fuzzy difflib match (cutoff 0.65).
    Returns the matched column name from `available`, or None.
    """
    # Pass 1 – exact alias
    alias_set = set(aliases)
    for col in available:
        if col in alias_set:
            return col

    # Pass 2 – substring
    for col in available:
        if target in col:
            return col

    # Pass 3 – fuzzy
    matches = difflib.get_close_matches(target, available, n=1, cutoff=0.65)
    return matches[0] if matches else None


def normalize_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise an arbitrary telemetry DataFrame to the canonical schema.

    Steps
    ─────
    1. Lowercase & strip all column names.
    2. Resolve aliases (exact → substring → fuzzy).
    3. Raise on missing essential columns.
    4. Inject zero-filled dummies for missing optional columns.
    5. Enforce units:
       - Speed → km/h   (auto-detects mph via heuristic > 180 km/h ceiling)
       - Throttle/Brake → 0–100 scale
    """
    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    available   = list(df.columns)

    rename_map: dict[str, str] = {}
    used_cols:  set[str]       = set()

    for target, aliases in SCHEMA.items():
        matched = _match_column(target, aliases, available)
        if matched and matched not in used_cols:
            rename_map[matched] = target
            used_cols.add(matched)

    df = df.rename(columns=rename_map)

    # ── Essential columns guard ───────────────────────────────────────────────
    missing_essential = [c for c in ESSENTIAL_COLS if c not in df.columns]
    if missing_essential:
        raise KeyError(
            f"CSV is missing required channel(s): {missing_essential}. "
            "Check your export settings or add a column alias to SCHEMA."
        )

    # ── Inject optional dummies ───────────────────────────────────────────────
    for opt in OPTIONAL_COLS:
        if opt not in df.columns:
            df[opt] = 0.0

    # ── Coerce all target columns to float ───────────────────────────────────
    numeric_targets = ESSENTIAL_COLS + OPTIONAL_COLS
    for col in numeric_targets:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # ── Unit scaling ──────────────────────────────────────────────────────────
    # Throttle / Brake: normalise 0–1 → 0–100
    if df["throttle"].max() <= 1.05:
        df["throttle"] = df["throttle"] * 100.0
    if df["brake"].max() <= 1.05:
        df["brake"] = df["brake"] * 100.0

    # Speed: if values look like mph (max plausibly < 230 mph but > 180 km/h
    # threshold), convert to km/h.  We use a simple heuristic: if the declared
    # max is suspiciously low for km/h (< 80) assume it may be mph.
    # A safer check: if any alias contained 'mph', always convert.
    if df["speed"].max() < 80.0 and df["speed"].max() > 5.0:
        # Likely mph – convert
        df["speed"] = df["speed"] * 1.60934

    return df


# ── Public Loader ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_and_process_data(
    file_bytes,
    downsample: bool = True,
    downsample_step: int = 3,
    row_threshold: int = 5_000,
) -> pd.DataFrame:
    """
    Safe CSV loader with:
      • Encoding fallback (UTF-8 → Latin-1)
      • Comment / metadata row stripping (lines starting with '#' or ';')
      • Configurable downsampling for Plotly performance
      • Full column normalisation via normalize_telemetry()

    Parameters
    ----------
    file_bytes      : Streamlit UploadedFile or file-like object.
    downsample      : Whether to apply stride downsampling.
    downsample_step : Keep every Nth row when downsampling.
    row_threshold   : Minimum row count that triggers downsampling.

    Returns
    -------
    pd.DataFrame with canonical column names, ready for physics pipeline.
    """
    try:
        raw = file_bytes.read()

        # Encoding detection
        for encoding in ("utf-8", "latin-1", "cp1252"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Cannot decode CSV – unsupported encoding.")

        # Strip leading comment/metadata lines
        lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(("#", ";"))]
        clean_text = "\n".join(lines)

        df = pd.read_csv(io.StringIO(clean_text))

        if df.empty:
            raise ValueError("The uploaded CSV contains no data rows.")

        # Downsample
        if downsample and len(df) > row_threshold:
            df = df.iloc[::downsample_step].reset_index(drop=True)

        return normalize_telemetry(df)

    except (KeyError, ValueError):
        raise   # re-raise domain errors with their messages intact
    except pd.errors.EmptyDataError:
        raise ValueError("The uploaded CSV is empty or corrupted.")
    except Exception as exc:
        raise ValueError(f"Failed to read CSV: {exc}") from exc
