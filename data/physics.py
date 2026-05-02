import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # 1. Create a common distance baseline (0 to 100% of the lap)
    common_dist = np.linspace(0, user_df['distance'].max(), len(user_df))
    
    # 2. Interpolate the Reference lap to match Your distance points
    # This "stretches" or "shrinks" the ref lap to align perfectly with yours
    ref_interp = pd.DataFrame({'distance': common_dist})
    for col in ['speed', 'throttle', 'brake', 'lataccel', 'longaccel']:
        ref_interp[col] = np.interp(common_dist, ref_df['distance'], ref_df[col])
    
    # 3. Calculate G-Sum for both
    user_df['g_sum'] = np.sqrt(user_df['lataccel']**2 + user_df['longaccel']**2)
    ref_interp['g_sum'] = np.sqrt(ref_interp['lataccel']**2 + ref_interp['longaccel']**2)
    
    # 4. Calculate real-time Delta (time lost/gained)
    # Time = Distance / Speed. We calculate the cumulative difference.
    user_time = np.cumsum(1.0 / (user_df['speed'] / 3.6)) 
    ref_time = np.cumsum(1.0 / (ref_interp['speed'] / 3.6))
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
