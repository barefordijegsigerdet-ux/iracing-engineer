import pandas as pd
import numpy as np

def calculate_physics_delta(user_df: pd.DataFrame, ref_df: pd.DataFrame) -> pd.DataFrame:
    """
    Physics-First calculation. If delta is missing, calculates it by integrating time 
    from speed over distance (dt = dx / v). Interpolates to a common spatial grid.
    """
    try:
        # Create a common spatial vector (distance)
        max_dist = min(user_df['distance'].max(), ref_df['distance'].max())
        common_dist = np.linspace(0, max_dist, 1000)

        # Interpolate speeds onto the common spatial grid (convert to m/s assuming km/h input)
        # We enforce a min speed of 1 km/h to prevent division by zero in tight hairpins/spins.
        v_user = np.maximum(np.interp(common_dist, user_df['distance'], user_df['speed']), 1.0) / 3.6
        v_ref = np.maximum(np.interp(common_dist, ref_df['distance'], ref_df['speed']), 1.0) / 3.6

        # Calculate time steps (dt = dx / v)
        dx = np.diff(common_dist, prepend=0)
        t_user = np.cumsum(dx / v_user)
        t_ref = np.cumsum(dx / v_ref)

        # Delta = User Time - Ref Time (Positive means user is slower/losing time)
        delta_time = t_user - t_ref
        
        return pd.DataFrame({'distance': common_dist, 'delta': delta_time})
    except Exception as e:
        raise ValueError(f"Physics integration failed. Check telemetry spatial data. Err: {e}")
