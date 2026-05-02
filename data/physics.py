import numpy as np

def calculate_physics_metrics(user_df, ref_df):
    """
    Beregner G-kræfter og slip-estimater uden at crashe.
    """
    for df in [user_df, ref_df]:
        # Tjek om vi har accelerationstallene fra Garage 61
        if 'lataccel' in df.columns and 'longaccel' in df.columns:
            # G-sum formel: sqrt(Lat^2 + Long^2)
            df['g_sum'] = np.sqrt(df['lataccel']**2 + df['longaccel']**2)
        else:
            df['g_sum'] = 0
            
        # Simpelt slip-estimat baseret på ratvinkel og fart
        if 'steer' in df.columns and 'speed' in df.columns:
            df['slip_est'] = (df['steer'].abs() * df['speed']) / 1000
        else:
            df['slip_est'] = 0

    return user_df, ref_df
