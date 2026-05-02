import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # 1. Create common distance baseline
    common_dist = np.linspace(0, user_df['distance'].max(), len(user_df))
    
    # 2. Interpolate Ref to match User distance
    ref_interp = pd.DataFrame({'distance': common_dist})
    cols_to_sync = ['speed', 'throttle', 'brake', 'lataccel', 'longaccel', 'lat', 'lon']
    
    for col in cols_to_sync:
        if col in ref_df.columns:
            ref_interp[col] = np.interp(common_dist, ref_df['distance'], ref_df[col])
    
    # 3. G-Sum calculation
    user_df['g_sum'] = np.sqrt(user_df['lataccel']**2 + user_df['longaccel']**2)
    ref_interp['g_sum'] = np.sqrt(ref_interp['lataccel']**2 + ref_interp['longaccel']**2)
    
    # 4. Time Delta Calculation
    u_speed_ms = np.clip(user_df['speed'] / 3.6, 0.1, None)
    r_speed_ms = np.clip(ref_interp['speed'] / 3.6, 0.1, None)
    dist_steps = np.diff(common_dist, prepend=0)
    
    user_time = np.cumsum(dist_steps / u_speed_ms)
    ref_time = np.cumsum(dist_steps / r_speed_ms)
    user_df['delta'] = user_time - ref_time

    return user_df, ref_interp

def get_coach_insights(user_df, ref_df):
    insights = []
    user_df['delta_diff'] = user_df['delta'].diff().fillna(0)
    max_loss_idx = user_df['delta_diff'].idxmax()
    loss_dist = int(user_df.iloc[max_loss_idx]['distance'] * 4259) # Approx Zandvoort length

    insights.append({
        "Category": "Time Loss",
        "Observation": f"Significant time loss detected near {loss_dist} meters.",
        "Advice": "Look at the Speed trace. If the red line is higher, you are over-slowing the car or braking too early."
    })
    return pd.DataFrame(insights)
