import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # Mapping based on Garage 61 columns
    channels = ["speed", "throttle", "brake", "lataccel", "longaccel", "lat", "lon"]
    interp_data = {}

    # Use 'distance' (which we mapped from LapDistPct) for alignment
    for col in channels:
        if col in ref_df.columns:
            interp_data[col] = np.interp(user_df["distance"], ref_df["distance"], ref_df[col])
        else:
            interp_data[col] = 0.0

    aligned_ref = pd.DataFrame(interp_data)
    aligned_ref["distance"] = user_df["distance"]
    
    # Calculate G-Sum for tire usage
    user_df["g_sum"] = np.sqrt(user_df["lataccel"]**2 + user_df["longaccel"]**2)
    aligned_ref["g_sum"] = np.sqrt(aligned_ref["lataccel"]**2 + aligned_ref["longaccel"]**2)

    # Convert 0-1 percentage to estimated meters for Zandvoort (~4259m)
    track_length = 4259 
    u_dist_m = user_df["distance"] * track_length
    r_dist_m = aligned_ref["distance"] * track_length
    
    # Calculate time delta in seconds
    user_time = np.cumsum(np.diff(u_dist_m, prepend=0) / np.maximum(user_df["speed"]/3.6, 1.0))
    ref_time = np.cumsum(np.diff(r_dist_m, prepend=0) / np.maximum(aligned_ref["speed"]/3.6, 1.0))
    
    user_df["delta"] = user_time - ref_time
    
    return user_df, aligned_ref

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
