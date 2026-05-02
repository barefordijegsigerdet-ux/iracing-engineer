import pandas as pd
import numpy as np

def calculate_physics_metrics(user_df: pd.DataFrame, ref_df: pd.DataFrame):
    """Calculates interpolated live delta and tire G-Sum."""
    try:
        # --- 1. SPATIAL/TIME RECONSTRUCTION ---
        # If distance is LapDistPct (0 to 1), scale to a standard 4000m track
        if user_df['distance'].max() <= 1.05:
            user_df['distance'] = user_df['distance'] * 4000.0
            ref_df['distance'] = ref_df['distance'] * 4000.0

        v_user = np.maximum(user_df['speed'] / 3.6, 1.0)
        v_ref = np.maximum(ref_df['speed'] / 3.6, 1.0)

        # If time is missing (dummy zeros), derive it physically: t = dx/v
        if user_df['time'].max() == 0.0:
            user_df['time'] = np.cumsum(np.diff(user_df['distance'], prepend=0) / v_user)
        if ref_df['time'].max() == 0.0:
            ref_df['time'] = np.cumsum(np.diff(ref_df['distance'], prepend=0) / v_ref)

        # --- 2. LIVE DELTA FIX (np.interp) ---
        # Align Reference Lap's time to User Lap's spatial distance
        ref_time_interp = np.interp(user_df['distance'], ref_df['distance'], ref_df['time'])
        
        # Delta: Positive means User is slower (losing time)
        user_df['delta'] = user_df['time'] - ref_time_interp

        # --- 3. G-SUM CALCULATION ---
        # G61 exports Accel in m/s^2. If max > 5.0, convert to Gs (divide by 9.81)
        for df in [user_df, ref_df]:
            lat, lon = df['lataccel'], df['longaccel']
            if lat.abs().max() > 5.0 or lon.abs().max() > 5.0:
                lat, lon = lat / 9.81, lon / 9.81
            
            # G-Sum Vector Math
            df['g_sum'] = np.sqrt(lat**2 + lon**2)

        return user_df, ref_df
    except Exception as e:
        raise ValueError(f"Physics engine failure: {e}")
