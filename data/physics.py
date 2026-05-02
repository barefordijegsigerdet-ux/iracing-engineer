import numpy as np

def calculate_physics_metrics(user_df, ref_df):
    """
    Beregner avancerede metrics som G-sum for at analysere dækkets udnyttelse.
    """
    for df in [user_df, ref_df]:
        # Beregn G-Sum (kombineret lateral og longitudinal kraft)
        if 'lataccel' in df.columns and 'longaccel' in df.columns:
            df['g_sum'] = np.sqrt(df['lataccel']**2 + df['longaccel']**2)
        else:
            df['g_sum'] = 0
        
        # Beregn dækslip-estimat (baseret på fart og rat-vinkel)
        if 'steer' in df.columns and 'speed' in df.columns:
            df['slip_est'] = (df['steer'].abs() * df['speed']) / 1000
        else:
            df['slip_est'] = 0

    return user_df, ref_df
