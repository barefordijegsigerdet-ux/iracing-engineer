import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # 1. Create a common distance baseline based on the user's lap
    common_dist = np.linspace(0, user_df['distance'].max(), len(user_df))
    
    # 2. Interpolate the Reference lap to match Your distance points
    # ADD 'lat' and 'lon' to this list!
    ref_interp = pd.DataFrame({'distance': common_dist})
    cols_to_sync = ['speed', 'throttle', 'brake', 'lataccel', 'longaccel', 'lat', 'lon']
    
    for col in cols_to_sync:
        if col in ref_df.columns:
            ref_interp[col] = np.interp(common_dist, ref_df['distance'], ref_df[col])
    
    # 3. Calculate G-Sum for both (using the unit-corrected Gs)
    user_df['g_sum'] = np.sqrt(user_df['lataccel']**2 + user_df['longaccel']**2)
    ref_interp['g_sum'] = np.sqrt(ref_interp['lataccel']**2 + ref_interp['longaccel']**2)
    
    # 4. Calculate Time Delta
    # We use (speed / 3.6) to convert km/h back to m/s for accurate time math
    user_speed_ms = user_df['speed'] / 3.6
    ref_speed_ms = ref_interp['speed'] / 3.6
    
    # Cumulative time = sum of (distance_step / speed)
    # We'll use a simple diff for distance steps
    dist_steps = np.diff(common_dist, prepend=0)
    
    user_time = np.cumsum(dist_steps / np.clip(user_speed_ms, 0.1, None))
    ref_time = np.cumsum(dist_steps / np.clip(ref_speed_ms, 0.1, None))
    
    user_df['delta'] = user_time - ref_time

    return user_df, ref_interp

def get_coach_insights(user_df, ref_df):
    insights = []
    # Identify the point of maximum time loss
    user_df['delta_diff'] = user_df['delta'].diff().fillna(0)
    max_loss_idx = user_df['delta_diff'].idxmax()
    # Convert pct to meters for the display
    loss_dist = int(user_df.iloc[max_loss_idx]['distance'] * 4259)

    insights.append({
        "Category": "Time Loss",
        "Observation": f"Significant time loss detected near {loss_dist} meters.",
        "Advice": "Look at the Speed trace in Telemetry. If the red line is higher, you are likely braking too early or over-slowing the car."
    })
    return pd.DataFrame(insights)
