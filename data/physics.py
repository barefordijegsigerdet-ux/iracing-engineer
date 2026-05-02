import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # Define channels to align from reference to user distance
    channels = ["speed", "throttle", "brake", "lataccel", "longaccel", "lat", "lon"]
    interp_data = {}

    for col in channels:
        if col in ref_df.columns:
            interp_data[col] = np.interp(user_df["distance"], ref_df["distance"], ref_df[col])
        else:
            interp_data[col] = 0.0

    aligned_ref = pd.DataFrame(interp_data)
    aligned_ref["distance"] = user_df["distance"]
    aligned_ref["g_sum"] = np.sqrt(aligned_ref["lataccel"]**2 + aligned_ref["longaccel"]**2)

    # Time Delta Calculation (v is in km/h, convert to m/s by / 3.6)
    user_time = np.cumsum(np.diff(user_df["distance"], prepend=0) / np.maximum(user_df["speed"]/3.6, 1.0))
    ref_time = np.cumsum(np.diff(aligned_ref["distance"], prepend=0) / np.maximum(aligned_ref["speed"]/3.6, 1.0))
    
    user_df["delta"] = user_time - ref_time
    user_df["g_sum"] = np.sqrt(user_df["lataccel"]**2 + user_df["longaccel"]**2)
    
    return user_df, aligned_ref

def get_coach_insights(user_df, ref_df):
    insights = []
    # Find exact distance of the biggest time loss
    user_df['delta_diff'] = user_df['delta'].diff()
    max_loss_idx = user_df['delta_diff'].idxmax()
    loss_dist = int(user_df.iloc[max_loss_idx]['distance'])

    insights.append({
        "Category": "Time Loss",
        "Observation": f"Biggest time loss detected at {loss_dist} meters.",
        "Advice": "Review the Telemetry tab at this distance. Focus on your brake-to-throttle transition compared to the red line."
    })

    if user_df["g_sum"].mean() < ref_df["g_sum"].mean() * 0.95:
        insights.append({
            "Category": "Grip",
            "Observation": "You are utilizing less total grip than the reference.",
            "Advice": "Look at the Friction Circle. If your blue dots are clustered in the center, you need to carry more entry speed."
        })
    return pd.DataFrame(insights)
