import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # Interpolate Reference to match User distance samples
    # We add 'lat' and 'lon' here to ensure they exist in the final ref_df
    channels = ["speed", "throttle", "brake", "lataccel", "longaccel", "lat", "lon"]
    interp_data = {}

    for col in channels:
        if col in ref_df.columns:
            interp_data[col] = np.interp(user_df["distance"], ref_df["distance"], ref_df[col])
        else:
            interp_data[col] = 0.0 # Safety fallback

    aligned_ref = pd.DataFrame(interp_data)
    aligned_ref["distance"] = user_df["distance"]
    aligned_ref["g_sum"] = np.sqrt(aligned_ref["lataccel"]**2 + aligned_ref["longaccel"]**2)

    # Time Delta Calculation
    user_time = np.cumsum(np.diff(user_df["distance"], prepend=0) / np.maximum(user_df["speed"]/3.6, 1.0))
    ref_time = np.cumsum(np.diff(aligned_ref["distance"], prepend=0) / np.maximum(aligned_ref["speed"]/3.6, 1.0))
    user_df["delta"] = user_time - ref_time
    user_df["g_sum"] = np.sqrt(user_df["lataccel"]**2 + user_df["longaccel"]**2)
    
    return user_df, aligned_ref
