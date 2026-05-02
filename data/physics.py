import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # Since Garage 61 uses 0-1 percentage, we use that for interpolation directly
    channels = ["speed", "throttle", "brake", "lataccel", "longaccel", "lat", "lon"]
    interp_data = {}

    for col in channels:
        interp_data[col] = np.interp(user_df["distance"], ref_df["distance"], ref_df[col])

    aligned_ref = pd.DataFrame(interp_data)
    aligned_ref["distance"] = user_df["distance"]
    
    # Calculate G-Sum
    user_df["g_sum"] = np.sqrt(user_df["lataccel"]**2 + user_df["longaccel"]**2)
    aligned_ref["g_sum"] = np.sqrt(aligned_ref["lataccel"]**2 + aligned_ref["longaccel"]**2)

    # Simplified Delta for Percentage-based distance
    # We assume a standard track length for Zandvoort (~4259m) to make the delta readable in seconds
    track_length = 4259 
    user_time = np.cumsum((np.diff(user_df["distance"], prepend=0) * track_length) / np.maximum(user_df["speed"]/3.6, 1.0))
    ref_time = np.cumsum((np.diff(aligned_ref["distance"], prepend=0) * track_length) / np.maximum(aligned_ref["speed"]/3.6, 1.0))
    
    user_df["delta"] = user_time - ref_time
    
    return user_df, aligned_ref
