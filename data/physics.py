import pandas as pd
import numpy as np

def calculate_physics_delta(user_df: pd.DataFrame, ref_df: pd.DataFrame) -> pd.DataFrame:
    """
    Physics-First calculation. Calculates spatial delta by integrating time 
    from speed over distance (dt = dx / v). 
    """
    try:
        # --- NEW: AUTO-HEAL PERCENTAGE DISTANCES ---
        # If distance maxes at ~1.0, it's LapDistPct. We must reconstruct absolute meters.
        # Formula: dx = v * dt  -->  Distance = Cumulative Sum of (Speed_m/s * Delta_Time)
        if user_df['distance'].max() <= 1.05:
            if 'time' in user_df.columns:
                # Convert Speed from km/h to m/s, multiply by time diff, and sum
                user_df['distance'] = ((user_df['speed'] / 3.6) * user_df['time'].diff().fillna(0)).cumsum()
                ref_df['distance'] = ((ref_df['speed'] / 3.6) * ref_df['time'].diff().fillna(0)).cumsum()
            else:
                raise ValueError("Telemetry distance is a percentage (0-1), but no 'Time' column was found to calculate actual track length.")
        # -------------------------------------------

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
