import pandas as pd
import numpy as np

def calculate_physics_delta(user_df: pd.DataFrame, ref_df: pd.DataFrame) -> pd.DataFrame:
    """
    Physics-First calculation. Calculates spatial delta by integrating time 
    from speed over distance (dt = dx / v). 
    """
    try:
        # --- AUTO-HEAL PERCENTAGE DISTANCES ---
        if user_df['distance'].max() <= 1.05:
            if 'time' in user_df.columns and 'time' in ref_df.columns:
                # Convert Speed from km/h to m/s, multiply by time diff, and sum to get meters
                user_df['distance'] = ((user_df['speed'] / 3.6) * user_df['time'].diff().fillna(0)).cumsum()
                ref_df['distance'] = ((ref_df['speed'] / 3.6) * ref_df['time'].diff().fillna(0)).cumsum()
            else:
                # FALLBACK: If time is truly missing, assume an average track length of 4000 meters.
                # This guarantees the app won't crash and the delta shape remains mathematically valid.
                user_df['distance'] = user_df['distance'] * 4000.0
                ref_df['distance'] = ref_df['distance'] * 4000.0

        # Create a common spatial vector (distance)
        max_dist = min(user_df['distance'].max(), ref_df['distance'].max())
        common_dist = np.linspace(0, max_dist, 1000)

        # Interpolate speeds onto the common spatial grid (convert to m/s assuming km/h input)
        # Enforce a min speed of 1 km/h to prevent division by zero
        v_user = np.maximum(np.interp(common_dist, user_df['distance'], user_df['speed']), 1.0) / 3.6
        v_ref = np.maximum(np.interp(common_dist, ref_df['distance'], ref_df['speed']), 1.0) / 3.6

        # Calculate time steps (dt = dx / v)
        dx = np.diff(common_dist, prepend=0)
        t_user = np.cumsum(dx / v_user)
        t_ref = np.cumsum(dx / v_ref)

        # Delta = User Time - Ref Time
        delta_time = t_user - t_ref
        
        return pd.DataFrame({'distance': common_dist, 'delta': delta_time})
    except Exception as e:
        raise ValueError(f"Physics integration failed. Check telemetry spatial data. Err: {e}")
