import numpy as np
import pandas as pd

def calculate_physics_metrics(user_df, ref_df):
    # Ensure distance is in meters
    if user_df["distance"].max() <= 1.05: user_df["distance"] *= 4000.0
    
    user_max_dist = user_df["distance"].max()
    if ref_df["distance"].max() <= 1.05: ref_df["distance"] *= user_max_dist

    # Interpolate Reference to match User distance samples
    ref_speed_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["speed"])
    ref_throttle_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["throttle"])
    ref_brake_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["brake"])
    ref_lat_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["lataccel"])
    ref_lon_interp = np.interp(user_df["distance"], ref_df["distance"], ref_df["longaccel"])

    # Build an aligned reference dataframe
    aligned_ref = pd.DataFrame({
        "distance": user_df["distance"],
        "speed": ref_speed_interp,
        "throttle": ref_throttle_interp,
        "brake": ref_brake_interp,
        "lataccel": ref_lat_interp,
        "longaccel": ref_lon_interp
    })

    # Time Delta Calculation
    user_time = np.cumsum(np.diff(user_df["distance"], prepend=0) / np.maximum(user_df["speed"]/3.6, 0.5))
    ref_time = np.cumsum(np.diff(aligned_ref["distance"], prepend=0) / np.maximum(aligned_ref["speed"]/3.6, 0.5))
    user_df["delta"] = user_time - ref_time
    
    # G-Sum
    user_df["g_sum"] = np.sqrt(user_df["lataccel"]**2 + user_df["longaccel"]**2)
    aligned_ref["g_sum"] = np.sqrt(aligned_ref["lataccel"]**2 + aligned_ref["longaccel"]**2)
    
    return user_df, aligned_ref

def get_sector_analysis(df):
    sectors = []
    step = df["distance"].max() / 10
    for i in range(10):
        start, end = i * step, (i + 1) * step
        sub = df[(df["distance"] >= start) & (df["distance"] < end)]
        if not sub.empty:
            sectors.append({
                "Sector": f"S{i+1}",
                "Range": f"{int(start)}m - {int(end)}m",
                "Avg G": f"{sub['g_sum'].mean():.2f} G",
                "Max Speed": f"{sub['speed'].max():.1f}"
            })
    return pd.DataFrame(sectors)

def get_coach_insights(user_df, ref_df):
    insights = []
    # Logic: Hesitant throttle
    throttle_gap = (ref_df["throttle"] > 80) & (user_df["throttle"] < 50)
    if throttle_gap.sum() > 10:
        insights.append({"Category": "Corner Exit", "Observation": "Late throttle application.", "Advice": "You're waiting too long to get back to power. Trust the grip."})
    
    # Logic: Braking potential
    if user_df["g_sum"].mean() < ref_df["g_sum"].mean() * 0.9:
        insights.append({"Category": "Braking", "Observation": "Under-utilizing tires.", "Advice": "The reference car is pulling more Gs. You can brake deeper or carry more entry speed."})
    
    return pd.DataFrame(insights) if insights else pd.DataFrame([{"Category":"General", "Observation":"Good lap", "Advice":"Keep it up!"}])
