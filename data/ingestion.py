"""
data/ingestion.py
─────────────────
CSV ingest, header normalisation, unit scaling, and safe downsampling.
"""
from __future__ import annotations

import difflib
import io
import streamlit as st
import pandas as pd
import numpy as np

# Schema aliases (shortened for brevity, keep your full SCHEMA dictionary here)
SCHEMA: dict[str, list[str]] = {
    "distance": ["distance", "distance (m)", "dist", "lapdist", "lapdistpct"],
    "speed": ["speed", "speed (km/h)", "speed (mph)", "velocity", "v"],
    "throttle": ["throttle", "throttle %", "gas", "accel"],
    "brake": ["brake", "brake %", "brake_pedal"],
    "time": ["time", "sessiontime", "laptime"],
    "lataccel": ["lataccel", "lateral_acceleration", "g_lat"],
    "longaccel": ["longaccel", "longitudinal_acceleration", "g_lon"],
    "steer": ["steer", "steering"],
    "gear": ["gear", "currentgear"],
}

ESSENTIAL_COLS = ["distance", "speed", "throttle", "brake"]
OPTIONAL_COLS  = ["time", "lataccel", "longaccel", "steer", "gear"]

def _match_column(target: str, aliases: list[str], available: list[str]) -> str | None:
    alias_set = set(aliases)
    for col in available:
        if col in alias_set: return col
    for col in available:
        if target in col: return col
    matches = difflib.get_close_matches(target, available, n=1, cutoff=0.65)
    return matches[0] if matches else None

def normalize_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    available = list(df.columns)
    rename_map: dict[str, str] = {}
    used_cols: set[str] = set()

    for target, aliases in SCHEMA.items():
        matched = _match_column(target, aliases, available)
        if matched and matched not in used_cols:
            rename_map[matched] = target
            used_cols.add(matched)

    speed_src_col = next((k for k, v in rename_map.items() if v == "speed"), "")
    df = df.rename(columns=rename_map)

    # Missing column guard
    missing = [c for c in ESSENTIAL_COLS if c not in df.columns]
    if missing: raise KeyError(f"Missing required channel(s): {missing}")

    for opt in OPTIONAL_COLS:
        if opt not in df.columns: df[opt] = 0.0

    # Unit Normalization: Throttle/Brake
    if df["throttle"].max() <= 1.05: df["throttle"] *= 100.0
    if df["brake"].max() <= 1.05: df["brake"] *= 100.0

    # Unit Normalization: Speed (Auto-detect)
    max_spd = df["speed"].max()
    spd_name_low = speed_src_col.lower()

    if "mph" in spd_name_low:
        df["speed"] *= 1.60934
        df.attrs["speed_unit"] = "mph"
    elif "m/s" in spd_name_low or spd_name_low.endswith("ms") or max_spd < 100.0:
        df["speed"] *= 3.6
        df.attrs["speed_unit"] = "m/s"
    elif max_spd < 250.0 and "km" not in spd_name_low:
        df["speed"] *= 1.60934
        df.attrs["speed_unit"] = "mph"
    else:
        df.attrs["speed_unit"] = "km/h"
    
    return df

@st.cache_data(show_spinner=False)
def load_and_process_data(
    file_bytes,
    downsample: bool = True,
    downsample_step: int = 3,
    row_threshold: int = 5_000,
    speed_unit_override: str = "Auto-detect",
) -> pd.DataFrame:
    raw = file_bytes.read()
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError: continue
    else: raise ValueError("Unsupported CSV encoding.")

    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(("#", ";"))]
    df = pd.read_csv(io.StringIO("\n".join(lines)))

    if downsample and len(df) > row_threshold:
        df = df.iloc[::downsample_step].reset_index(drop=True)

    df = normalize_telemetry(df)

    # ── Speed Override Logic ──
    if speed_unit_override != "Auto-detect":
        detected = df.attrs.get("speed_unit", "km/h")
        # Undo auto-detection
        if detected == "mph": df["speed"] /= 1.60934
        elif detected == "m/s": df["speed"] /= 3.6
            
        # Apply manual override
        if speed_unit_override == "mph → km/h":
            df["speed"] *= 1.60934
            df.attrs["speed_unit"] = "mph (forced)"
        elif speed_unit_override == "m/s → km/h":
            df["speed"] *= 3.6
            df.attrs["speed_unit"] = "m/s (forced)"
        else:
            df.attrs["speed_unit"] = "km/h (forced)"

    return df
