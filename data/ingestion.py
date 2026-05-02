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

    rename_map: dict[str, str] = {}   # original_col → target_col
    used_cols:  set[str]       = set()

    for target, aliases in SCHEMA.items():
        matched = _match_column(target, aliases, available)
        if matched and matched not in used_cols:
            rename_map[matched] = target
            used_cols.add(matched)

    # Remember the *original* speed column name BEFORE renaming (for unit hint)
    speed_src_col = next((k for k, v in rename_map.items() if v == "speed"), "")

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

    # ── Throttle / Brake: normalise 0–1 → 0–100 ──────────────────────────────
    if df["throttle"].max() <= 1.05:
        df["throttle"] = df["throttle"] * 100.0
    if df["brake"].max() <= 1.05:
        df["brake"] = df["brake"] * 100.0

    # ── Speed → always store internally as km/h ───────────────────────────────
    #
    # Detection waterfall (first match wins):
    #
    #   1. Column name contains 'mph'         → it's mph  → × 1.60934
    #   2. Column name contains 'm/s'         → it's m/s  → × 3.6
    #   3. max value < 100                    → almost certainly m/s
    #                                            (iRacing SDK exports m/s)  → × 3.6
    #   4. 100 ≤ max < 250 AND no 'km' hint   → treat as mph → × 1.60934
    #      Rationale: real race cars regularly exceed 200 km/h but rarely
    #      exceed 200 mph, so a max <250 with no explicit km/h label is safer
    #      to treat as mph.
    #   5. max ≥ 250 OR name contains 'km'    → already km/h, leave alone.
    #
    # The detected unit label is stored in df.attrs for display in the UI.

    max_spd       = df["speed"].max()
    spd_name_low  = speed_src_col.lower()

    if "mph" in spd_name_low:
        df["speed"] = df["speed"] * 1.60934
        df.attrs["speed_unit"] = "mph"
    elif "m/s" in spd_name_low or spd_name_low.endswith("ms"):
        df["speed"] = df["speed"] * 3.6
        df.attrs["speed_unit"] = "m/s"
    elif max_spd < 100.0:
        # iRacing telemetry SDK default: Speed in m/s
        df["speed"] = df["speed"] * 3.6
        df.attrs["speed_unit"] = "m/s"
    elif max_spd < 250.0 and "km" not in spd_name_low:
        # Below 250 without an explicit km/h marker → assume mph
        df["speed"] = df["speed"] * 1.60934
        df.attrs["speed_unit"] = "mph"
    else:
        df.attrs["speed_unit"] = "km/h"

    return df


# ── Public Loader ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_and_process_data(
    file_bytes,
    downsample: bool = True,
    downsample_step: int = 3,
    row_threshold: int = 5_000,
    speed_unit_override: str = "Auto-detect",
) -> pd.DataFrame:
    """
    Safe CSV loader with:
      • Encoding fallback (UTF-8 → Latin-1)
      • Comment / metadata row stripping (lines starting with '#' or ';')
      • Configurable downsampling for Plotly performance
      • Full column normalisation via normalize_telemetry()
      • Manual speed unit override

    Parameters
    ----------
    file_bytes           : Streamlit UploadedFile or file-like object.
    downsample           : Whether to apply stride downsampling.
    downsample_step      : Keep every Nth row when downsampling.
    row_threshold        : Minimum row count that triggers downsampling.
    speed_unit_override  : One of the sidebar selectbox options.

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

        df = normalize_telemetry(df)

        # Apply manual override AFTER auto-detection (undoes conversion then reapplies)
        if speed_unit_override != "Auto-detect":
            detected = df.attrs.get("speed_unit", "km/h")
            # First undo whatever auto-detect did
            if detected == "mph":
                df["speed"] = df["speed"] / 1.60934
            elif detected in ("m/s", "m/s→km/h"):
                df["speed"] = df["speed"] / 3.6

            # Now apply the override
            if speed_unit_override == "mph → km/h":
                df["speed"] = df["speed"] * 1.60934
                df.attrs["speed_unit"] = "mph (manual)"
            elif speed_unit_override == "m/s → km/h":
                df["speed"] = df["speed"] * 3.6
                df.attrs["speed_unit"] = "m/s (manual)"
            else:  # km/h no conversion
                df.attrs["speed_unit"] = "km/h (manual)"

        return df

    except (KeyError, ValueError):
        raise
    except pd.errors.EmptyDataError:
        raise ValueError("The uploaded CSV is empty or corrupted.")
    except Exception as exc:
        raise ValueError(f"Failed to read CSV: {exc}") from exc
