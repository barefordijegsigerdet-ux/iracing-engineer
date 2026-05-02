import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # Distance scaling
    if user_df["distance"].max() <= 1.05:
        user_df["distance"] *= 4000.0 # Default track scale
    
    user_max = user_df["distance"].max()
    if ref_df["distance"].max() <= 1.05:
        ref_df["distance"] *= user_max

    # Align ref to user distance
    ref_time_interp = np.interp(user_df["distance"], ref_df["distance"], 
                                np.cumsum(np.diff(ref_df["distance"], prepend=0) / np.maximum(ref_df["speed"]/3.6, 0.5)))
    user_time = np.cumsum(np.diff(user_df["distance"], prepend=0) / np.maximum(user_df["speed"]/3.6, 0.5))
    
    user_df["delta"] = user_time - ref_time_interp
    user_df["g_sum"] = np.sqrt(user_df["lataccel"]**2 + user_df["longaccel"]**2)
    ref_df["g_sum"] = np.sqrt(ref_df["lataccel"]**2 + ref_df["longaccel"]**2)
    
    return user_df, ref_df

def get_sector_analysis(df):
    sectors = []
    # Logic: Split lap into 10 equal distance segments
    step = df["distance"].max() / 10
    for i in range(10):
        start, end = i * step, (i + 1) * step
        mask = (df["distance"] >= start) & (df["distance"] < end)
        sub = df[mask]
        if not sub.empty:
            sectors.append({
                "Sector": f"S{i+1}",
                "Range": f"{int(start)}m - {int(end)}m",
                "Avg G-Sum": f"{sub['g_sum'].mean():.2f} G",
                "Max Speed": f"{sub['speed'].max():.1f} km/h"
            })
    return pd.DataFrame(sectors)
