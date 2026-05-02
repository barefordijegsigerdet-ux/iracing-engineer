import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # Simple distance normalization
    user_max_dist = user_df["distance"].max()
    
    # Interpolate Reference to match User distance samples exactly
    ref_speed_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["speed"])
    ref_throttle_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["throttle"])
    ref_brake_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["brake"])
    ref_lat_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["lataccel"])
    ref_lon_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["longaccel"])

    aligned_ref = pd.DataFrame({
        "distance": user_df["distance"],
        "speed": ref_speed_interp,
        "throttle": ref_throttle_interp,
        "brake": ref_brake_interp,
        "lataccel": ref_lat_interp,
        "longaccel": ref_lon_interp,
        "g_sum": np.sqrt(ref_lat_interp**2 + ref_lon_interp**2)
    })

    # Delta Calculation
    user_time = np.cumsum(np.diff(user_df["distance"], prepend=0) / np.maximum(user_df["speed"]/3.6, 1.0))
    ref_time = np.cumsum(np.diff(aligned_ref["distance"], prepend=0) / np.maximum(aligned_ref["speed"]/3.6, 1.0))
    user_df["delta"] = user_time - ref_time
    user_df["g_sum"] = np.sqrt(user_df["lataccel"]**2 + user_df["longaccel"]**2)
    
    return user_df, aligned_ref

def get_coach_insights(user_df, ref_df):
    insights = []
    # Identify specific distance of max time loss
    user_df['delta_diff'] = user_df['delta'].diff()
    max_loss_idx = user_df['delta_diff'].idxmax()
    loss_dist = int(user_df.iloc[max_loss_idx]['distance'])

    insights.append({
        "Category": "Time Loss",
        "Observation": f"Significant time loss detected at {loss_dist} meters.",
        "Advice": "Check this location in the Telemetry tab. Compare your brake release vs the reference."
    })

    if user_df["g_sum"].mean() < ref_df["g_sum"].mean() * 0.9:
        insights.append({
            "Category": "Grip",
            "Observation": "Lower average G-Sum than reference.",
            "Advice": "You are under-driving the tires. Carry more entry speed into the corners."
        })
    return pd.DataFrame(insights)
