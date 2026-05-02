"""
data/physics.py
───────────────
Distance-based physics engine.

Key operations
──────────────
1. Distance normalisation  – handles LapDistPct (0-1) or raw metres.
2. Time derivation          – integrates t = ∫(1/v) dx when 'time' is absent.
3. Live delta (np.interp)   – aligns reference lap to user's distance axis.
4. G-Sum                    – vector magnitude of lateral + longitudinal accel,
                              with automatic m/s² → G conversion.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ── Constants ──────────────────────────────────────────────────────────────────
G_CONSTANT        = 9.80665       # m/s²  per G
TRACK_SCALE       = 4_000.0       # metres – default if LapDistPct is supplied
MIN_SPEED_MS      = 0.5           # m/s   – lower clamp to avoid division by zero
ACCEL_SI_THRESH   = 4.0           # G threshold: if abs(accel) > this, assume m/s²


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ensure_sorted_distance(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by distance and drop any exact-duplicate distance entries."""
    df = df.sort_values("distance").drop_duplicates(subset=["distance"])
    return df.reset_index(drop=True)


def _scale_distance(df: pd.DataFrame, reference_max: float | None = None) -> pd.DataFrame:
    """
    If distance looks like a 0–1 fraction (LapDistPct), multiply by TRACK_SCALE.
    When processing the second lap we use the first lap's already-scaled max so
    both laps end at the same notional distance.
    """
    if df["distance"].max() <= 1.05:
        scale = reference_max if reference_max is not None else TRACK_SCALE
        df = df.copy()
        df["distance"] = df["distance"] * scale
    return df


def _derive_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive cumulative lap time from speed and distance via:

        t_i = t_{i-1} + Δd_i / v_i

    This is the discrete approximation of  t = ∫ (1/v) dx.

    Only applied when the 'time' column is all-zero (i.e. a dummy column
    injected by ingestion.py because the CSV had no time channel).
    """
    if df["time"].max() != 0.0:
        return df   # real time data present – keep it

    df = df.copy()
    v_ms  = np.maximum(df["speed"].to_numpy() / 3.6, MIN_SPEED_MS)   # km/h → m/s
    d_arr = df["distance"].to_numpy()

    # Δd at each sample (first element = 0)
    delta_d = np.diff(d_arr, prepend=d_arr[0])

    # t = cumulative sum of Δd / v
    df["time"] = np.cumsum(delta_d / v_ms)
    return df


def _convert_accel_to_g(series: pd.Series) -> pd.Series:
    """
    Convert acceleration channel to G-force if the data appears to be in m/s².
    Heuristic: if the absolute maximum exceeds ACCEL_SI_THRESH Gs it is almost
    certainly in m/s².
    """
    if series.abs().max() > ACCEL_SI_THRESH:
        return series / G_CONSTANT
    return series


def _compute_g_sum(df: pd.DataFrame) -> pd.DataFrame:
    """
    G-Sum = √(LatAccel² + LonAccel²)

    Both channels are converted to G-force first.
    The result is stored in-place in df['g_sum'].
    """
    df = df.copy()
    lat_g = _convert_accel_to_g(df["lataccel"])
    lon_g = _convert_accel_to_g(df["longaccel"])
    df["g_sum"] = np.sqrt(lat_g ** 2 + lon_g ** 2)
    return df


# ── Public API ─────────────────────────────────────────────────────────────────

def calculate_physics_metrics(
    user_df: pd.DataFrame,
    ref_df:  pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Full physics pipeline.  Returns (user_df, ref_df) with new columns:
      • 'distance' (metres, sorted, de-duplicated)
      • 'time'     (seconds, derived if absent)
      • 'delta'    (seconds, positive = user is slower; only on user_df)
      • 'g_sum'    (G-force magnitude, both DataFrames)

    Parameters
    ----------
    user_df : Normalised user-lap DataFrame (from ingestion.py).
    ref_df  : Normalised reference-lap DataFrame.

    Raises
    ------
    ValueError on any physics computation failure.
    """
    try:
        # ── 1. Distance normalisation ─────────────────────────────────────────
        user_df = _scale_distance(user_df)
        # Use user lap's max so both laps share the same distance axis.
        user_max = user_df["distance"].max()
        ref_df   = _scale_distance(ref_df, reference_max=user_max)

        # Sort & de-duplicate (essential for np.interp monotonicity)
        user_df = _ensure_sorted_distance(user_df)
        ref_df  = _ensure_sorted_distance(ref_df)

        # ── 2. Time derivation ────────────────────────────────────────────────
        user_df = _derive_time(user_df)
        ref_df  = _derive_time(ref_df)

        # ── 3. Live delta (distance-aligned) ─────────────────────────────────
        #   Interpolate the reference time onto the user's distance axis.
        #   np.interp requires xp (ref distance) to be strictly increasing –
        #   guaranteed by _ensure_sorted_distance above.
        ref_time_at_user_dist = np.interp(
            user_df["distance"].to_numpy(),
            ref_df["distance"].to_numpy(),
            ref_df["time"].to_numpy(),
        )
        user_df = user_df.copy()
        user_df["delta"] = user_df["time"].to_numpy() - ref_time_at_user_dist

        # ── 4. G-Sum ──────────────────────────────────────────────────────────
        user_df = _compute_g_sum(user_df)
        ref_df  = _compute_g_sum(ref_df)

        return user_df, ref_df

    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Physics engine failure: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Unexpected physics error: {exc}") from exc
