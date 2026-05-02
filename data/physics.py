import numpy as np

def calculate_physics_metrics(user_df, ref_df):
    """
    Beregner metrics som G-sum. 
    Hvis data mangler, returneres df uændret for at undgå crash.
    """
    for df in [user_df, ref_df]:
        # Tjek om vi har de nødvendige accelerationstal
        if 'lataccel' in df.columns and 'longaccel' in df.columns:
            # np.sqrt(a^2 + b^2)
            df['g_sum'] = np.sqrt(df['lataccel']**2 + df['longaccel']**2)
        else:
            df['g_sum'] = 0
            
        if 'steer' in df.columns and 'speed' in df.columns:
            df['slip_est'] = (df['steer'].abs() * df['speed']) / 1000
        else:
            df['slip_est'] = 0

    return user_df, ref_df
